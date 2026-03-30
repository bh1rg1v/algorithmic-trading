import pandas as pd
import numpy as np
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, confusion_matrix, accuracy_score
import joblib
import os
import glob
import warnings
from datetime import datetime
import logging
import time
warnings.filterwarnings('ignore')

# Configuration
MAX_STOCKS = 25
N_ESTIMATORS = 200
TEST_SIZE = 0.3
RANDOM_STATE = 42
MIN_DATA_POINTS = 100
LEARNING_RATE = 0.1
MAX_DEPTH = 6

# Trading thresholds
BUY_THRESHOLD = 0.025
SELL_THRESHOLD = -0.025
HOLD_DAYS = [5, 10, 20]

# Technical indicator periods
SMA_PERIODS = [5, 10, 20, 50]
EMA_PERIODS = [12, 26]
RSI_PERIOD = 14
BB_PERIOD = 20
BB_STD = 2
STOCH_PERIOD = 14
STOCH_SMOOTH = 3
ATR_PERIOD = 14
MOMENTUM_PERIODS = [5, 10, 20]
ROLLING_WINDOW = 252
RECENT_DAYS = 30
TOP_FEATURES = 15
TOP_PREDICTIONS = MAX_STOCKS

def setup_logging(results_dir):
    """Setup logging configuration"""
    log_file = os.path.join(results_dir, 'bt_ml_gb.log')
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger(__name__)

def time_it(func):
    """Decorator to time function execution"""
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        execution_time = end_time - start_time
        logging.info(f"{func.__name__} completed in {execution_time:.2f} seconds")
        return result, execution_time
    return wrapper

@time_it
def calculate_technical_indicators(df):
    """Calculate comprehensive technical indicators"""
    # Price-based features
    df['returns'] = df['Close'].pct_change()
    df['high_low_pct'] = (df['High'] - df['Low']) / df['Close']
    df['open_close_pct'] = (df['Close'] - df['Open']) / df['Open']
    
    # Moving averages
    for period in SMA_PERIODS:
        df[f'sma_{period}'] = df['Close'].rolling(period).mean()
        df[f'price_sma_{period}_ratio'] = df['Close'] / df[f'sma_{period}']
        df[f'volume_sma_{period}'] = df['Volume'].rolling(period).mean()
    
    # Exponential moving averages
    for period in EMA_PERIODS:
        df[f'ema_{period}'] = df['Close'].ewm(span=period).mean()
    
    # MACD
    df['macd'] = df[f'ema_{EMA_PERIODS[0]}'] - df[f'ema_{EMA_PERIODS[1]}']
    df['macd_signal'] = df['macd'].ewm(span=9).mean()
    df['macd_histogram'] = df['macd'] - df['macd_signal']
    
    # RSI
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=RSI_PERIOD).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=RSI_PERIOD).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))
    
    # Bollinger Bands
    df['bb_middle'] = df['Close'].rolling(BB_PERIOD).mean()
    bb_std = df['Close'].rolling(BB_PERIOD).std()
    df['bb_upper'] = df['bb_middle'] + (bb_std * BB_STD)
    df['bb_lower'] = df['bb_middle'] - (bb_std * BB_STD)
    df['bb_position'] = (df['Close'] - df['bb_lower']) / (df['bb_upper'] - df['bb_lower'])
    
    # Stochastic Oscillator
    low_stoch = df['Low'].rolling(STOCH_PERIOD).min()
    high_stoch = df['High'].rolling(STOCH_PERIOD).max()
    df['stoch_k'] = 100 * (df['Close'] - low_stoch) / (high_stoch - low_stoch)
    df['stoch_d'] = df['stoch_k'].rolling(STOCH_SMOOTH).mean()
    
    # Williams %R
    df['williams_r'] = -100 * (high_stoch - df['Close']) / (high_stoch - low_stoch)
    
    # Average True Range (ATR)
    df['tr1'] = df['High'] - df['Low']
    df['tr2'] = abs(df['High'] - df['Close'].shift())
    df['tr3'] = abs(df['Low'] - df['Close'].shift())
    df['tr'] = df[['tr1', 'tr2', 'tr3']].max(axis=1)
    df['atr'] = df['tr'].rolling(ATR_PERIOD).mean()
    
    # Volume indicators
    df['volume_ratio'] = df['Volume'] / df[f'volume_sma_{BB_PERIOD}']
    df['price_volume'] = df['Close'] * df['Volume']
    
    # Momentum indicators
    for period in MOMENTUM_PERIODS:
        df[f'momentum_{period}'] = df['Close'] / df['Close'].shift(period) - 1
        df[f'volatility_{period}'] = df['returns'].rolling(period).std()
    
    # Support/Resistance levels
    df[f'high_{BB_PERIOD}'] = df['High'].rolling(BB_PERIOD).max()
    df[f'low_{BB_PERIOD}'] = df['Low'].rolling(BB_PERIOD).min()
    df['price_position'] = (df['Close'] - df[f'low_{BB_PERIOD}']) / (df[f'high_{BB_PERIOD}'] - df[f'low_{BB_PERIOD}'])
    
    # Rolling Sharpe Ratio
    rolling_returns = df['returns'].rolling(ROLLING_WINDOW)
    df[f'rolling_sharpe_{ROLLING_WINDOW}'] = rolling_returns.mean() / rolling_returns.std() * np.sqrt(ROLLING_WINDOW)
    
    # Rolling Sortino Ratio
    downside_returns = df['returns'].where(df['returns'] < 0, 0)
    downside_std = downside_returns.rolling(ROLLING_WINDOW).std()
    df[f'rolling_sortino_{ROLLING_WINDOW}'] = rolling_returns.mean() / downside_std * np.sqrt(ROLLING_WINDOW)
    
    # Drawdown calculation
    cumulative_returns = (1 + df['returns']).cumprod()
    running_max = cumulative_returns.expanding().max()
    df['drawdown'] = (cumulative_returns - running_max) / running_max
    df[f'max_drawdown_{ROLLING_WINDOW}'] = df['drawdown'].rolling(ROLLING_WINDOW).min()
    
    return df

@time_it
def create_swing_trading_labels(df, hold_days=HOLD_DAYS):
    """Create swing trading labels based on forward returns"""
    labels = []
    
    for i in range(len(df)):
        if i >= len(df) - max(hold_days):
            labels.append(0)
            continue
        
        current_price = df['Close'].iloc[i]
        future_returns = []
        
        for days in hold_days:
            if i + days < len(df):
                future_price = df['Close'].iloc[i + days]
                future_return = (future_price - current_price) / current_price
                future_returns.append(future_return)
        
        if not future_returns:
            labels.append(0)
            continue
        
        best_return = max(future_returns)
        
        if best_return > BUY_THRESHOLD:
            labels.append(1)
        elif best_return < SELL_THRESHOLD:
            labels.append(-1)
        else:
            labels.append(0)
    
    return labels

@time_it
def load_and_process_data(data_dir):
    """Load and process all stock data"""
    csv_files = glob.glob(os.path.join(data_dir, "*.csv"))
    all_data = []
    
    if not csv_files:
        print(f"No CSV files found in {data_dir}")
        raise FileNotFoundError(f"No CSV files found in {data_dir}")
    
    print(f"Processing {min(len(csv_files), MAX_STOCKS)} out of {len(csv_files)} stock files...")
    
    for file in csv_files[:MAX_STOCKS]:
        try:
            df = pd.read_csv(file)
            df['Date'] = pd.to_datetime(df['Date'])
            df = df.sort_values('Date').reset_index(drop=True)
            
            stock_name = os.path.basename(file).split('_')[1].split('.')[0]
            df['Stock'] = stock_name
            
            df, _ = calculate_technical_indicators(df)
            labels, _ = create_swing_trading_labels(df)
            df['target'] = labels
            df = df.dropna()
            
            if len(df) > MIN_DATA_POINTS:
                all_data.append(df)
                print(f"Processed {stock_name}: {len(df)} samples")
                
        except Exception as e:
            print(f"Error processing {file}: {e}")
            continue
    
    if not all_data:
        raise ValueError("No valid stock data found after processing")
    
    return pd.concat(all_data, ignore_index=True)

@time_it
def prepare_features(df):
    """Prepare feature matrix"""
    feature_cols = [col for col in df.columns if col not in 
                   ['Date', 'Stock', 'target', 'tr1', 'tr2', 'tr3', 'tr']]
    numeric_cols = df[feature_cols].select_dtypes(include=[np.number]).columns
    
    X = df[numeric_cols].copy()
    
    # Clean data: replace inf and very large values
    X = X.replace([np.inf, -np.inf], np.nan)
    X = X.fillna(X.median())
    
    # Cap extreme values at 99th percentile
    for col in X.columns:
        upper_limit = X[col].quantile(0.99)
        lower_limit = X[col].quantile(0.01)
        X[col] = X[col].clip(lower=lower_limit, upper=upper_limit)
    
    return X, df['target']

def main():
    start_time = time.time()
    
    # Create unique result folder
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    script_name = os.path.splitext(os.path.basename(__file__))[0]
    results_dir = f"backtestresults/ml/{script_name}/gb_run_{timestamp}"
    os.makedirs(results_dir, exist_ok=True)
    
    # Setup logging
    logger = setup_logging(results_dir)
    logger.info(f"Starting Gradient Boosting ML Backtesting Run - {timestamp}")
    logger.info(f"Configuration: MAX_STOCKS={MAX_STOCKS}, N_ESTIMATORS={N_ESTIMATORS}")
    logger.info(f"Trading thresholds: BUY={BUY_THRESHOLD}, SELL={SELL_THRESHOLD}")
    
    # Find data directory
    data_dir = r"data\storage\processed\equity\zerodha\2015\day"
    
    if not os.path.exists(data_dir):
        logger.error("Data directory not found")
        return
    
    logger.info(f"Using data directory: {data_dir}")
    
    # Load and process data
    df, load_time = load_and_process_data(data_dir)
    target_dist = df['target'].value_counts()
    logger.info(f"Total samples: {len(df)}, Target distribution: {target_dist.to_dict()}")
    
    # Prepare features
    (X, y), prep_time = prepare_features(df)
    logger.info(f"Features: {X.shape[1]}")
    
    # Split data
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=TEST_SIZE, random_state=RANDOM_STATE, stratify=y
    )
    logger.info(f"Training: {len(X_train)}, Testing: {len(X_test)}")
    
    # Train model
    logger.info(f"Training Gradient Boosting with {N_ESTIMATORS} estimators...")
    train_start = time.time()
    gb_model = GradientBoostingClassifier(
        n_estimators=N_ESTIMATORS,
        learning_rate=LEARNING_RATE,
        max_depth=MAX_DEPTH,
        random_state=RANDOM_STATE
    )
    gb_model.fit(X_train, y_train)
    train_time = time.time() - train_start
    logger.info(f"Training completed in {train_time:.2f} seconds")
    
    # Make predictions
    pred_start = time.time()
    y_pred = gb_model.predict(X_test)
    y_pred_proba = gb_model.predict_proba(X_test)
    pred_time = time.time() - pred_start
    
    # Performance metrics
    accuracy = accuracy_score(y_test, y_pred)
    logger.info(f"Accuracy: {accuracy:.4f}")
    
    print("\n" + "="*50)
    print("MODEL PERFORMANCE METRICS")
    print("="*50)
    print(f"Accuracy: {accuracy:.4f}")
    
    target_names = ['Sell (-1)', 'Hold (0)', 'Buy (1)']
    class_report = classification_report(y_test, y_pred, target_names=target_names)
    print(f"\nClassification Report:\n{class_report}")
    logger.info(f"Classification Report:\n{class_report}")
    
    cm = confusion_matrix(y_test, y_pred)
    print(f"\nConfusion Matrix:\n{cm}")
    logger.info(f"Confusion Matrix:\n{cm}")
    
    # Feature importance
    feature_importance = pd.DataFrame({
        'feature': X.columns,
        'importance': gb_model.feature_importances_
    }).sort_values('importance', ascending=False)
    
    print(f"\nTop {TOP_FEATURES} Most Important Features:")
    print(feature_importance.head(TOP_FEATURES).to_string(index=False))
    logger.info(f"Top features: {feature_importance.head(TOP_FEATURES)['feature'].tolist()}")
    
    # Save files
    model_path = os.path.join(results_dir, "swing_trading_gb_model.pkl")
    joblib.dump(gb_model, model_path)
    
    feature_names_path = os.path.join(results_dir, "feature_names.pkl")
    joblib.dump(list(X.columns), feature_names_path)
    
    feature_importance.to_csv(os.path.join(results_dir, "feature_importance.csv"), index=False)
    
    # Recent predictions
    print("\n" + "="*50)
    print("RECENT PREDICTIONS")
    print("="*50)
    
    recent_predictions = []
    stocks = df['Stock'].unique()[:TOP_PREDICTIONS]
    
    for stock in stocks:
        stock_data = df[df['Stock'] == stock].tail(RECENT_DAYS)
        if len(stock_data) > 0:
            stock_features = stock_data[X.columns]
            predictions = gb_model.predict(stock_features)
            probabilities = gb_model.predict_proba(stock_features)
            
            latest_pred = predictions[-1]
            latest_proba = probabilities[-1]
            signal_map = {-1: 'SELL', 0: 'HOLD', 1: 'BUY'}
            
            recent_predictions.append({
                'Stock': stock,
                'Date': stock_data['Date'].iloc[-1],
                'Price': stock_data['Close'].iloc[-1],
                'Signal': signal_map[latest_pred],
                'Confidence': max(latest_proba)
            })
    
    recent_df = pd.DataFrame(recent_predictions)
    print(recent_df.to_string(index=False))
    
    predictions_path = os.path.join(results_dir, 'recent_predictions.csv')
    recent_df.to_csv(predictions_path, index=False)
    
    # Log final stats
    signal_dist = recent_df['Signal'].value_counts()
    total_time = time.time() - start_time
    
    logger.info(f"Signal distribution: {signal_dist.to_dict()}")
    logger.info(f"Total execution time: {total_time:.2f} seconds")
    logger.info(f"Timing - Load: {load_time:.2f}s, Prep: {prep_time:.2f}s, Train: {train_time:.2f}s, Pred: {pred_time:.2f}s")
    
    # Save execution stats
    stats = {
        'timestamp': timestamp,
        'total_samples': len(df),
        'training_samples': len(X_train),
        'testing_samples': len(X_test),
        'num_features': X.shape[1],
        'accuracy': accuracy,
        'total_time': total_time,
        'load_time': load_time,
        'prep_time': prep_time,
        'train_time': train_time,
        'pred_time': pred_time,
        'target_distribution': target_dist.to_dict(),
        'signal_distribution': signal_dist.to_dict(),
        'config': {
            'max_stocks': MAX_STOCKS,
            'n_estimators': N_ESTIMATORS,
            'learning_rate': LEARNING_RATE,
            'max_depth': MAX_DEPTH,
            'buy_threshold': BUY_THRESHOLD,
            'sell_threshold': SELL_THRESHOLD,
            'hold_days': HOLD_DAYS
        }
    }
    
    pd.DataFrame([stats]).to_csv(os.path.join(results_dir, 'execution_stats.csv'), index=False)
    
    print("\n" + "="*50)
    print("ANALYSIS COMPLETE")
    print("="*50)
    print(f"All files saved to: {results_dir}")
    print("Files created:")
    print("1. swing_trading_gb_model.pkl - Trained model")
    print("2. feature_names.pkl - Feature names")
    print("3. feature_importance.csv - Feature importance")
    print("4. recent_predictions.csv - Latest predictions")
    print("5. bt_ml_gb.log - Execution log")
    print("6. execution_stats.csv - Performance statistics")
    
    logger.info("Gradient Boosting ML Backtesting Run completed successfully")

if __name__ == "__main__":
    main()