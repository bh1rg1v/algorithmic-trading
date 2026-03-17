import os
import pandas as pd
import time
from datetime import datetime, timedelta
from glob import glob
from multiprocessing import Pool, cpu_count

# ==============================
# CONFIG VARIABLES
# ==============================

SPOT_DATA_PATH = r"data\storage\raw\index\NIFTY.csv"
OPTIONS_DATA_PATH = r"data\storage\options\index\nifty"
ROUND_STRIKE = 50
NUM_PROCESSES = cpu_count() - 2
RESULTS_BASE_PATH = r"backtesting\rv_iv_analysis\results"


# ==============================
# HELPERS
# ==============================

def round_to_step(value, step):
    return int(round(value / step) * step)


def get_expiry_list(options_path):
    expiries = sorted(os.listdir(options_path))
    return expiries


def get_next_day_of_previous_expiry(expiries, index):
    if index == 0:
        return None

    prev_expiry = datetime.strptime(expiries[index - 1], "%Y-%m-%d")
    return prev_expiry + timedelta(days=1)


def compute_weighted_price(row):
    # You can change this logic
    return (row['Open'] + row['High'] + row['Low'] + row['Close']) / 4


def load_spot_data(spot_path):
    df = pd.read_csv(spot_path, parse_dates=['Date'])
    df['DateOnly'] = df['Date'].dt.date
    return df


def load_option_file(expiry_folder, strike, option_type):
    pattern = f"NIFTY_{strike}_{option_type}_*.csv"
    files = glob(os.path.join(expiry_folder, pattern))
    if not files:
        return None

    df = pd.read_csv(files[0], parse_dates=['timestamp'])
    return df


def get_price_at_time(option_df, timestamp):
    row = option_df[option_df['timestamp'] == timestamp]
    if row.empty:
        return None
    return row.iloc[0]['close']


def track_trade(option_df_ce, option_df_pe, entry_time, ce_target, pe_target):
    ce_filtered = option_df_ce[option_df_ce['timestamp'] >= entry_time][['timestamp', 'close']].values
    pe_filtered = option_df_pe[option_df_pe['timestamp'] >= entry_time][['timestamp', 'close']].values
    
    ce_exit_idx = None
    pe_exit_idx = None
    
    # Vectorized search for target hits
    ce_hits = ce_filtered[:, 1] >= ce_target
    pe_hits = pe_filtered[:, 1] >= pe_target
    
    if ce_hits.any():
        ce_exit_idx = ce_hits.argmax()
        ce_exit_time = ce_filtered[ce_exit_idx, 0]
        ce_sell_price = ce_filtered[ce_exit_idx, 1]
        ce_target_hit = True
    else:
        ce_exit_time = ce_filtered[-1, 0]
        ce_sell_price = ce_filtered[-1, 1]
        ce_target_hit = False
    
    if pe_hits.any():
        pe_exit_idx = pe_hits.argmax()
        pe_exit_time = pe_filtered[pe_exit_idx, 0]
        pe_sell_price = pe_filtered[pe_exit_idx, 1]
        pe_target_hit = True
    else:
        pe_exit_time = pe_filtered[-1, 0]
        pe_sell_price = pe_filtered[-1, 1]
        pe_target_hit = False
    
    return (ce_exit_time, ce_sell_price, ce_target_hit,
            pe_exit_time, pe_sell_price, pe_target_hit)


def process_expiry(args):
    """Process a single expiry - designed for multiprocessing"""
    expiry, i, expiries, config = args

    # print(f"Started processing: {expiry}")
    
    spot_df = load_spot_data(config['spot_path'])
    
    expiry_folder = os.path.join(config['options_path'], expiry)
    expiry_date = datetime.strptime(expiry, "%Y-%m-%d")
    expiry_day = expiry_date.strftime("%A")
    
    expiry_trades = 0
    expiry_profitable = 0
    trades = []
    analysis_data = []

    next_day = get_next_day_of_previous_expiry(expiries, i)
    if next_day is None:
        return trades, analysis_data, expiry_trades, expiry_profitable

    trade_day = next_day.date()
    day_data = spot_df[spot_df['DateOnly'] == trade_day]
    
    if day_data.empty:
        return trades, analysis_data, expiry_trades, expiry_profitable
    
    # Pre-parse time window once
    start_time = datetime.strptime(config['window_start'], "%H:%M").time()
    finish_time = datetime.strptime(config['window_finish'], "%H:%M").time()

    for _, row in day_data.iterrows():
        timestamp = row['Date']
        trade_time = timestamp.time()
        
        if not (start_time <= trade_time <= finish_time):
            continue
        
        current_day = timestamp.strftime("%A")
        ltp = compute_weighted_price(row)

        ce_strike = round_to_step(ltp * (1 + config['strike_distance_pct']), config['round_strike'])
        pe_strike = round_to_step(ltp * (1 - config['strike_distance_pct']), config['round_strike'])

        ce_df = load_option_file(expiry_folder, ce_strike, "CE")
        pe_df = load_option_file(expiry_folder, pe_strike, "PE")

        if ce_df is None or pe_df is None:
            continue

        ce_price = get_price_at_time(ce_df, timestamp)
        pe_price = get_price_at_time(pe_df, timestamp)

        if ce_price is None or pe_price is None:
            continue

        total_cost = ce_price + pe_price
        cost_pct = (total_cost / ltp) * 100

        analysis_data.append({
            "timestamp": timestamp,
            "expiry": expiry,
            "expiry_day": expiry_day,
            "current_day": current_day,
            "open": row['Open'],
            "high": row['High'],
            "low": row['Low'],
            "close": row['Close'],
            "volume": row['Volume'],
            "ltp": ltp,
            "pe_strike": pe_strike,
            "ce_strike": ce_strike,
            "pe_cost": pe_price,
            "ce_cost": ce_price,
            "total_cost": total_cost,
            "cost_pct": cost_pct
        })

        if total_cost <= ltp * config['max_total_premium_pct']:
            target = total_cost * config['target_multiplier']
            ce_target = target
            pe_target = target

            ce_exit_time, ce_sell_price, ce_target_hit, pe_exit_time, pe_sell_price, pe_target_hit = track_trade(
                ce_df, pe_df, timestamp, ce_target, pe_target
            )
            
            expiry_trades += 1
            if ce_target_hit or pe_target_hit:
                expiry_profitable += 1

            ce_pnl = ce_sell_price - ce_price
            ce_pnl_pct = (ce_pnl / ce_price) * 100

            trades.append({
                "entry_time": timestamp,
                "timestamp": timestamp,
                "expiry": expiry,
                "expiry_day": expiry_day,
                "current_day": current_day,
                "open": row['Open'],
                "high": row['High'],
                "low": row['Low'],
                "close": row['Close'],
                "volume": row['Volume'],
                "ltp": ltp,
                "option_type": "CE",
                "strike": ce_strike,
                "buy_price": ce_price,
                "target_price": ce_target,
                "exit_time": ce_exit_time,
                "sell_price": ce_sell_price,
                "target_hit": ce_target_hit,
                "pnl": ce_pnl,
                "pnl_pct": ce_pnl_pct
            })
            
            pe_pnl = pe_sell_price - pe_price
            pe_pnl_pct = (pe_pnl / pe_price) * 100

            trades.append({
                "entry_time": timestamp,
                "timestamp": timestamp,
                "expiry": expiry,
                "expiry_day": expiry_day,
                "current_day": current_day,
                "open": row['Open'],
                "high": row['High'],
                "low": row['Low'],
                "close": row['Close'],
                "volume": row['Volume'],
                "ltp": ltp,
                "option_type": "PE",
                "strike": pe_strike,
                "buy_price": pe_price,
                "target_price": pe_target,
                "exit_time": pe_exit_time,
                "sell_price": pe_sell_price,
                "target_hit": pe_target_hit,
                "pnl": pe_pnl,
                "pnl_pct": pe_pnl_pct
            })
            
            if config['limit_one_trade']:
                break
    
    return trades, analysis_data, expiry_trades, expiry_profitable


# ==============================
# MAIN ENGINE
# ==============================

def process_expiries(config):

    start_time = datetime.now()
    start_timestamp = start_time.strftime("%Y%m%d_%H%M%S")
    
    # Create results folder
    results_folder = os.path.join(config['results_base_path'], f"RV_IV_Analysis_{start_timestamp}")
    os.makedirs(results_folder, exist_ok=True)
    
    OUTPUT_FILE = os.path.join(results_folder, "trades.csv")
    ANALYSIS_FILE = os.path.join(results_folder, "analysis.csv")
    SUMMARY_FILE = os.path.join(results_folder, "summary.txt")
    
    expiries = get_expiry_list(config['options_path'])

    if config['expiry_limit']:
        expiries = expiries[-config['expiry_limit']:]

    trades = []
    analysis_data = []
    expiry_stats = {}
    total_trades = 0
    total_profitable = 0

    print(f"Processing {len(expiries)} expiries using {config['num_processes']} processes...\n")
    
    # Prepare arguments for multiprocessing
    args_list = [(expiry, i, expiries, config) for i, expiry in enumerate(expiries)]
    
    # Process expiries in parallel
    with Pool(processes=config['num_processes']) as pool:
        results = pool.map(process_expiry, args_list)
    
    # Aggregate results (optimized)
    for i, (expiry_trades_list, expiry_analysis, expiry_trade_count, expiry_profit_count) in enumerate(results):
        expiry = expiries[i]
        
        if expiry_trades_list:
            trades.extend(expiry_trades_list)
        if expiry_analysis:
            analysis_data.extend(expiry_analysis)
        
        total_trades += expiry_trade_count
        total_profitable += expiry_profit_count
        
        expiry_stats[expiry] = {
            "trades": expiry_trade_count,
            "profitable": expiry_profit_count
        }
        
        if expiry_trade_count > 0:
            print(f"Expiry {expiry}: {expiry_trade_count} trades, {expiry_profit_count} profitable")

    if trades:
        trades_df = pd.DataFrame(trades)
        while True:
            try:
                trades_df.to_csv(OUTPUT_FILE, index=False)
                break
            except PermissionError:
                print(f"\n⚠️  Permission denied: {OUTPUT_FILE} is open in another program")
                print("Waiting 10 seconds before retry...")
                time.sleep(10)
    
    if analysis_data:
        analysis_df = pd.DataFrame(analysis_data)
        while True:
            try:
                analysis_df.to_csv(ANALYSIS_FILE, index=False)
                break
            except PermissionError:
                print(f"\n⚠️  Permission denied: {ANALYSIS_FILE} is open in another program")
                print("Waiting 10 seconds before retry...")
                time.sleep(10)
    
    print(f"\nBacktest Complete.")
    print(f"Total expiries processed: {len(expiries)}")
    print(f"Total trades: {total_trades}")
    print(f"Total profitable trades: {total_profitable}")
    print(f"Trades saved to {OUTPUT_FILE}")
    print(f"Analysis saved to {ANALYSIS_FILE}")
    
    # Save summary to text file
    with open(SUMMARY_FILE, 'w') as f:
        f.write("="*60 + "\n")
        f.write("RV-IV ANALYSIS BACKTEST SUMMARY\n")
        f.write("="*60 + "\n\n")
        
        f.write("CONFIG VARIABLES:\n")
        f.write("-" * 40 + "\n")
        f.write(f"SPOT_DATA_PATH: {config['spot_path']}\n")
        f.write(f"OPTIONS_DATA_PATH: {config['options_path']}\n")
        f.write(f"STRIKE_DISTANCE_PCT: {config['strike_distance_pct']}\n")
        f.write(f"MAX_TOTAL_PREMIUM_PCT: {config['max_total_premium_pct']}\n")
        f.write(f"TARGET_MULTIPLIER: {config['target_multiplier']}\n")
        f.write(f"ROUND_STRIKE: {config['round_strike']}\n")
        f.write(f"EXPIRY_LIMIT: {config['expiry_limit']}\n")
        f.write(f"LIMIT_ONE_TRADE_PER_EXPIRY: {config['limit_one_trade']}\n")
        f.write(f"TRADING_WINDOW_START_TIME: {config['window_start']}\n")
        f.write(f"TRADING_WINDOW_FINISH_TIME: {config['window_finish']}\n")
        f.write(f"\nStart Time: {start_time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"End Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("\n" + "="*60 + "\n\n")

        traded_expiries = sum(1 for stats in expiry_stats.values() if stats['trades'] != 0)
        
        f.write("OVERALL STATISTICS:\n")
        f.write("-" * 40 + "\n")
        f.write(f"Total Expiries Processed: {len(expiries)}\n")
        f.write(f"Total Expiries Traded: {traded_expiries}\n")
        f.write(f"Total Trades: {total_trades}\n")
        f.write(f"Total Profitable Trades: {total_profitable}\n")
        if total_trades > 0:
            f.write(f"Profit Rate: {(total_profitable/total_trades)*100:.2f}%\n")
        f.write("\n" + "="*60 + "\n\n")

        # Add backtest metrics from trades
        if total_trades > 0 and trades:
            f.write("\n" + "="*60 + "\n\n")
            f.write("BACKTEST METRICS:\n")
            f.write("-" * 40 + "\n")
            
            f.write(f"Total PnL: {trades_df['pnl'].sum():.2f}\n")
            f.write(f"Average PnL: {trades_df['pnl'].mean():.2f}\n")
            f.write(f"Average PnL %: {trades_df['pnl_pct'].mean():.2f}%\n")
            f.write(f"Max PnL: {trades_df['pnl'].max():.2f}\n")
            f.write(f"Max PnL %: {trades_df['pnl_pct'].max():.2f}%\n")
            f.write(f"Min PnL: {trades_df['pnl'].min():.2f}\n")
            f.write(f"Min PnL %: {trades_df['pnl_pct'].min():.2f}%\n")
            f.write(f"Win Rate: {(trades_df['pnl'] > 0).sum() / len(trades_df) * 100:.2f}%\n")
            f.write(f"Target Hit Rate: {trades_df['target_hit'].sum() / len(trades_df) * 100:.2f}%\n")
        
        f.write("EXPIRY-WISE BREAKDOWN:\n")
        f.write("-" * 40 + "\n")

        f.write("Note: Expiries where there were no trades were not included in the breakdown below.")

        for expiry, stats in expiry_stats.items():

            if (stats['trades'] == 0):
                continue

            f.write(f"\nExpiry: {expiry}\n")
            f.write(f"  Trades: {stats['trades']}\n")
            f.write(f"  Profitable: {stats['profitable']}\n")
            if stats['trades'] > 0:
                f.write(f"  Profit Rate: {(stats['profitable']/stats['trades'])*100:.2f}%\n")
    
    print(f"Summary saved to {SUMMARY_FILE}")
    print(f"\nAll results saved in: {results_folder}")
    
    # Return results for logging
    result_metrics = {
        'results_folder': os.path.basename(results_folder),
        'total_trades': total_trades,
        'total_profitable': total_profitable,
        'profit_rate': (total_profitable/total_trades)*100 if total_trades > 0 else 0,
        'total_pnl': trades_df['pnl'].sum() if trades else 0,
        'avg_pnl_pct': trades_df['pnl_pct'].mean() if trades else 0,
        'win_rate': (trades_df['pnl'] > 0).sum() / len(trades_df) * 100 if trades else 0,
        'target_hit_rate': trades_df['target_hit'].sum() / len(trades_df) * 100 if trades else 0
    }
    
    return result_metrics


def main():
    from itertools import product
    
    # Config arrays for grid testing
    STRIKE_DISTANCE_PCT_ARRAY = [0.0025, 0.00375, 0.005, 0.0075, 0.01]
    MAX_TOTAL_PREMIUM_PCT_ARRAY = [0.0050, 0.0055, 0.0065, 0.0075]
    TARGET_MULTIPLIER_ARRAY = [1.5, 2, 2.5]
    TRADING_WINDOW_DURATION_MINUTES = 30
    EXPIRY_LIMIT = 10000
    LIMIT_ONE_TRADE_PER_EXPIRY = 0
    
    # Generate trading window intervals
    market_start = datetime.strptime("09:30", "%H:%M")
    market_end = datetime.strptime("15:30", "%H:%M")
    window_intervals = []
    
    current = market_start
    while current + timedelta(minutes=TRADING_WINDOW_DURATION_MINUTES) <= market_end:
        window_start = current.strftime("%H:%M")
        window_finish = (current + timedelta(minutes=TRADING_WINDOW_DURATION_MINUTES)).strftime("%H:%M")
        window_intervals.append((window_start, window_finish))
        current += timedelta(minutes=TRADING_WINDOW_DURATION_MINUTES)
    
    # Generate all combinations
    combinations = list(product(
        STRIKE_DISTANCE_PCT_ARRAY,
        MAX_TOTAL_PREMIUM_PCT_ARRAY,
        TARGET_MULTIPLIER_ARRAY,
        window_intervals
    ))
    
    # Config log file
    config_log_file = os.path.join(RESULTS_BASE_PATH, "config_log.csv")
    
    # Load existing configs if file exists
    if os.path.exists(config_log_file):
        existing_configs = pd.read_csv(config_log_file)
    else:
        existing_configs = pd.DataFrame()
    
    print(f"Total combinations to test: {len(combinations)}\n")
    
    processed_count = 0
    
    for idx, (strike_dist, max_premium, target_mult, (win_start, win_finish)) in enumerate(combinations, 1):
        
        # Check if config already processed
        if not existing_configs.empty:
            already_processed = (
                (existing_configs['strike_distance_pct'] == strike_dist) &
                (existing_configs['max_total_premium_pct'] == max_premium) &
                (existing_configs['target_multiplier'] == target_mult) &
                (existing_configs['window_start'] == win_start) &
                (existing_configs['window_finish'] == win_finish)
            ).any()
            
            if already_processed:
                print(f"\nSkipping combination {idx}/{len(combinations)} (already processed)")
                print(f"Strike Distance: {strike_dist}, Max Premium: {max_premium}, Target: {target_mult}x")
                print(f"Window: {win_start} - {win_finish}\n")
                continue
        
        print(f"\n{'='*60}")
        print(f"Testing combination {idx}/{len(combinations)}")
        print(f"Strike Distance: {strike_dist}, Max Premium: {max_premium}, Target: {target_mult}x")
        print(f"Window: {win_start} - {win_finish}")
        print(f"{'='*60}\n")
        
        config = {
            'spot_path': SPOT_DATA_PATH,
            'options_path': OPTIONS_DATA_PATH,
            'strike_distance_pct': strike_dist,
            'max_total_premium_pct': max_premium,
            'target_multiplier': target_mult,
            'round_strike': ROUND_STRIKE,
            'expiry_limit': EXPIRY_LIMIT,
            'limit_one_trade': LIMIT_ONE_TRADE_PER_EXPIRY,
            'window_start': win_start,
            'window_finish': win_finish,
            'num_processes': NUM_PROCESSES,
            'results_base_path': RESULTS_BASE_PATH
        }
        
        result_metrics = process_expiries(config)
        
        # Log config and results
        log_entry = {
            'strike_distance_pct': strike_dist,
            'max_total_premium_pct': max_premium,
            'target_multiplier': target_mult,
            'window_start': win_start,
            'window_finish': win_finish,
            'expiry_limit': EXPIRY_LIMIT,
            'limit_one_trade': LIMIT_ONE_TRADE_PER_EXPIRY,
            **result_metrics
        }
        
        log_df = pd.DataFrame([log_entry])
        
        while True:
            try:
                if os.path.exists(config_log_file):
                    log_df.to_csv(config_log_file, mode='a', header=False, index=False)
                else:
                    log_df.to_csv(config_log_file, mode='w', header=True, index=False)
                break
            except PermissionError:
                print(f"\n⚠️  Permission denied: {config_log_file} is open in another program")
                print("Waiting 10 seconds before retry...")
                time.sleep(10)
        
        # Reload existing configs for next iteration
        existing_configs = pd.read_csv(config_log_file)
        processed_count += 1
        
        # Sleep after every 50 processed combinations
        if processed_count % 50 == 0:
            print(f"\n{'='*60}")
            print(f"Processed {processed_count} combinations. Sleeping for 3 minutes...")
            print(f"{'='*60}\n")
            time.sleep(180)


if __name__ == "__main__":
    main()
    print("\n" + "="*60)
    print("All combinations processed!")
    print(f"Config log saved to: {os.path.join(RESULTS_BASE_PATH, 'config_log.csv')}")
    print("="*60)