import os
import pandas as pd
import time
from datetime import datetime, timedelta
from glob import glob
from multiprocessing import Pool, cpu_count

# ==============================
# CONFIG VARIABLES
# ==============================

SPOT_DATA_PATH = r"D:\github\algorithmic-trading\data\storage\index\NIFTY.csv"
OPTIONS_DATA_PATH = r"D:\github\algorithmic-trading\data\storage\options\index\nifty"
ROUND_STRIKE = 50
NUM_PROCESSES = cpu_count() - 2
RESULTS_BASE_PATH = r"D:\github\algorithmic-trading\backtesting\rv_iv_analysis\results"


# ==============================
# GLOBAL CACHES
# ==============================

SPOT_DF = None
SPOT_LOOKUP = None

OPTION_DATA_CACHE = {}
OPTION_FILE_CACHE = {}

EXPIRY_DAY_CACHE = {}

TIME_WINDOW_CACHE = {}

# ==============================
# HELPERS
# ==============================

def round_to_step(value, step):
    return int(round(value / step) * step)


def get_expiry_list(options_path):
    return sorted(os.listdir(options_path))


def get_next_day_of_previous_expiry(expiries, index):

    if index == 0:
        return None

    prev_expiry = datetime.strptime(
        expiries[index - 1],
        "%Y-%m-%d"
    )

    return prev_expiry + timedelta(days=1)


def load_spot_data(spot_path):

    global SPOT_DF
    global SPOT_LOOKUP

    if SPOT_DF is not None:
        return SPOT_DF

    print("Loading spot data...")

    df = pd.read_csv(
        spot_path,
        parse_dates=["Date"]
    )

    df["DateOnly"] = df["Date"].dt.date

    df["ltp"] = (
        df["Open"]
        + df["High"]
        + df["Low"]
        + df["Close"]
    ) / 4

    SPOT_DF = df

    SPOT_LOOKUP = {
        date: group
        for date, group in df.groupby("DateOnly")
    }

    print(
        f"Spot data loaded "
        f"({len(df):,} rows)"
    )

    return SPOT_DF


def get_day_data(trade_day):

    global SPOT_LOOKUP

    if SPOT_LOOKUP is None:
        return None

    return SPOT_LOOKUP.get(trade_day)


from multiprocessing import Pool

count = 0

def load_expiry_data(args):
    """
    Worker function for loading a single expiry folder.
    """

    expiry, expiry_folder = args

    expiry_cache = {}
    loaded_count = 0

    csv_files = glob(
        os.path.join(
            expiry_folder,
            "*.csv"
        )
    )

    print(
        f"Loading {expiry} "
        f"({len(csv_files)} files)"
    )

    for file_path in csv_files:

        try:

            filename = os.path.basename(
                file_path
            )

            parts = filename.replace(
                ".csv",
                ""
            ).split("_")

            if len(parts) < 3:
                continue

            strike = int(parts[1])
            option_type = parts[2]

            # Load only required columns
            df = pd.read_csv(
                file_path,
                usecols=[
                    "timestamp",
                    "close"
                ],
                parse_dates=[
                    "timestamp"
                ]
            )

            df.set_index(
                "timestamp",
                inplace=True,
                drop=False
            )

            expiry_cache[
                (strike, option_type)
            ] = df

            loaded_count += 1

        except Exception as e:

            print(
                f"Failed loading "
                f"{file_path}"
            )

            print(e)

    # count += 1

    # if (count % 100) == 0:
    #     print(F"Loaded {count} files into cache")

    return (
        expiry,
        expiry_cache,
        loaded_count
    )


def preload_option_files(
    options_path,
    expiry_limit=None
):

    global OPTION_DATA_CACHE

    if OPTION_DATA_CACHE:
        return

    expiries = get_expiry_list(
        options_path
    )

    if expiry_limit:
        expiries = expiries[
            -expiry_limit:
        ]

    print(
        f"\nPreloading option files "
        f"for {len(expiries)} expiries "
        f"using {NUM_PROCESSES} processes...\n"
    )

    args_list = []

    for expiry in expiries:

        expiry_folder = os.path.join(
            options_path,
            expiry
        )

        args_list.append(
            (
                expiry,
                expiry_folder
            )
        )

    total_loaded = 0

    with Pool(
        processes=NUM_PROCESSES
    ) as pool:

        results = pool.map(
            load_expiry_data,
            args_list
        )

    for (
        expiry,
        expiry_cache,
        loaded_count
    ) in results:

        OPTION_DATA_CACHE[
            expiry
        ] = expiry_cache

        total_loaded += loaded_count

    print(
        f"\nLoaded "
        f"{total_loaded:,} "
        f"option files into memory"
    )

    print(
        f"Cached "
        f"{len(OPTION_DATA_CACHE):,} "
        f"expiries\n"
    )


def load_option_file(
    expiry,
    strike,
    option_type
):

    expiry_cache = OPTION_DATA_CACHE.get(
        expiry
    )

    if expiry_cache is None:
        return None

    return expiry_cache.get(
        (strike, option_type)
    )


def get_price_at_time(
    option_df,
    timestamp
):

    try:
        return option_df.at[
            timestamp,
            "close"
        ]
    except KeyError:
        return None
    
def get_window_times(
    start_str,
    finish_str
):

    key = (
        start_str,
        finish_str
    )

    if key not in TIME_WINDOW_CACHE:

        TIME_WINDOW_CACHE[key] = (
            datetime.strptime(
                start_str,
                "%H:%M"
            ).time(),

            datetime.strptime(
                finish_str,
                "%H:%M"
            ).time()
        )

    return TIME_WINDOW_CACHE[key]


def track_trade(
    option_df_ce,
    option_df_pe,
    entry_time,
    ce_target,
    pe_target
):

    ce_filtered = option_df_ce.loc[
        entry_time:
    ][["timestamp", "close"]].values

    pe_filtered = option_df_pe.loc[
        entry_time:
    ][["timestamp", "close"]].values

    ce_hits = (
        ce_filtered[:, 1]
        >= ce_target
    )

    pe_hits = (
        pe_filtered[:, 1]
        >= pe_target
    )

    if ce_hits.any():

        idx = ce_hits.argmax()

        ce_exit_time = ce_filtered[idx, 0]
        ce_sell_price = ce_filtered[idx, 1]
        ce_target_hit = True

    else:

        ce_exit_time = ce_filtered[-1, 0]
        ce_sell_price = ce_filtered[-1, 1]
        ce_target_hit = False

    if pe_hits.any():

        idx = pe_hits.argmax()

        pe_exit_time = pe_filtered[idx, 0]
        pe_sell_price = pe_filtered[idx, 1]
        pe_target_hit = True

    else:

        pe_exit_time = pe_filtered[-1, 0]
        pe_sell_price = pe_filtered[-1, 1]
        pe_target_hit = False

    return (
        ce_exit_time,
        ce_sell_price,
        ce_target_hit,
        pe_exit_time,
        pe_sell_price,
        pe_target_hit
    )


def process_expiry(args):

    expiry, i, expiries, config = args

    # expiry_day = EXPIRY_DAY_CACHE[
    #     expiry
    # ]

    expiry_date = datetime.strptime(
        expiry,
        "%Y-%m-%d"
    )

    expiry_day = expiry_date.strftime(
        "%A"
    )

    trades = []
    analysis_data = []

    expiry_trades = 0
    expiry_profitable = 0

    next_day = get_next_day_of_previous_expiry(
        expiries,
        i
    )

    if next_day is None:
        return (
            trades,
            analysis_data,
            expiry_trades,
            expiry_profitable
        )

    trade_day = next_day.date()

    day_data = get_day_data(trade_day)

    if day_data is None:
        return (
            trades,
            analysis_data,
            expiry_trades,
            expiry_profitable
        )

    start_time, finish_time = (
        get_window_times(
            config["window_start"],
            config["window_finish"]
        )
    )

    strike_distance_pct = config[
        "strike_distance_pct"
    ]

    max_total_premium_pct = config[
        "max_total_premium_pct"
    ]

    target_multiplier = config[
        "target_multiplier"
    ]

    round_strike = config[
        "round_strike"
    ]

    limit_one_trade = config[
        "limit_one_trade"
    ]

    for row in day_data.itertuples(index=False):

        timestamp = row.Date

        trade_time = timestamp.time()

        if trade_time < start_time:
            continue

        if trade_time > finish_time:
            continue

        ltp = row.ltp

        ce_strike = round_to_step(
            ltp * (
                1 + strike_distance_pct
            ),
            round_strike
        )

        pe_strike = round_to_step(
            ltp * (
                1 - strike_distance_pct
            ),
            round_strike
        )

        ce_df = load_option_file(
            expiry,
            ce_strike,
            "CE"
        )

        pe_df = load_option_file(
            expiry,
            pe_strike,
            "PE"
        )

        if ce_df is None or pe_df is None:
            continue

        ce_price = get_price_at_time(
            ce_df,
            timestamp
        )

        if ce_price is None:
            print(
                "CE timestamp miss:",
                timestamp,
                ce_strike
            )
            continue

        pe_price = get_price_at_time(
            pe_df,
            timestamp
        )

        if ce_price is None:
            continue

        if pe_price is None:
            continue

        total_cost = (
            ce_price + pe_price
        )

        cost_pct = (
            total_cost / ltp
        ) * 100

        current_day = timestamp.strftime(
            "%A"
        )

        analysis_data.append({
            "timestamp": timestamp,
            "expiry": expiry,
            "expiry_day": expiry_day,
            "current_day": current_day,
            "open": row.Open,
            "high": row.High,
            "low": row.Low,
            "close": row.Close,
            "volume": row.Volume,
            "ltp": ltp,
            "pe_strike": pe_strike,
            "ce_strike": ce_strike,
            "pe_cost": pe_price,
            "ce_cost": ce_price,
            "total_cost": total_cost,
            "cost_pct": cost_pct
        })

        if total_cost > (
            ltp *
            max_total_premium_pct
        ):
            continue

        target = (
            total_cost *
            target_multiplier
        )

        (
            ce_exit_time,
            ce_sell_price,
            ce_target_hit,
            pe_exit_time,
            pe_sell_price,
            pe_target_hit
        ) = track_trade(
            ce_df,
            pe_df,
            timestamp,
            target,
            target
        )

        expiry_trades += 1

        if (
            ce_target_hit
            or
            pe_target_hit
        ):
            expiry_profitable += 1

        ce_pnl = (
            ce_sell_price -
            ce_price
        )

        pe_pnl = (
            pe_sell_price -
            pe_price
        )

        trades.append({
            "entry_time": timestamp,
            "timestamp": timestamp,
            "expiry": expiry,
            "expiry_day": expiry_day,
            "current_day": current_day,
            "open": row.Open,
            "high": row.High,
            "low": row.Low,
            "close": row.Close,
            "volume": row.Volume,
            "ltp": ltp,
            "option_type": "CE",
            "strike": ce_strike,
            "buy_price": ce_price,
            "target_price": target,
            "exit_time": ce_exit_time,
            "sell_price": ce_sell_price,
            "target_hit": ce_target_hit,
            "pnl": ce_pnl,
            "pnl_pct": (
                ce_pnl / ce_price
            ) * 100
        })

        trades.append({
            "entry_time": timestamp,
            "timestamp": timestamp,
            "expiry": expiry,
            "expiry_day": expiry_day,
            "current_day": current_day,
            "open": row.Open,
            "high": row.High,
            "low": row.Low,
            "close": row.Close,
            "volume": row.Volume,
            "ltp": ltp,
            "option_type": "PE",
            "strike": pe_strike,
            "buy_price": pe_price,
            "target_price": target,
            "exit_time": pe_exit_time,
            "sell_price": pe_sell_price,
            "target_hit": pe_target_hit,
            "pnl": pe_pnl,
            "pnl_pct": (
                pe_pnl / pe_price
            ) * 100
        })

        if limit_one_trade:
            break

    return (
        trades,
        analysis_data,
        expiry_trades,
        expiry_profitable
    )


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

    # Process expiries sequentially
    results = []

    for args in args_list:

        results.append(
            process_expiry(args)
        )
    
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

    expiries = get_expiry_list(
        OPTIONS_DATA_PATH
    )

    for expiry in expiries:

        expiry_date = datetime.strptime(
            expiry,
            "%Y-%m-%d"
        )

        EXPIRY_DAY_CACHE[expiry] = (
            expiry_date.strftime("%A")
        )

    from itertools import product
    
    # Config arrays for grid testing
    STRIKE_DISTANCE_PCT_ARRAY = [0.0025, 0.00375, 0.005, 0.0075, 0.01]
    MAX_TOTAL_PREMIUM_PCT_ARRAY = [0.0050, 0.0055, 0.0065, 0.0075]
    TARGET_MULTIPLIER_ARRAY = [1.5, 2, 2.5, 3]
    TRADING_WINDOW_DURATION_MINUTES = 60
    EXPIRY_LIMIT = 100
    LIMIT_ONE_TRADE_PER_EXPIRY = 1

    # STRIKE_DISTANCE_PCT_ARRAY = [0.005]
    # MAX_TOTAL_PREMIUM_PCT_ARRAY = [0.0065]
    # TARGET_MULTIPLIER_ARRAY = [2.5, 3]
    # TRADING_WINDOW_DURATION_MINUTES = 30
    # EXPIRY_LIMIT = 10000
    # LIMIT_ONE_TRADE_PER_EXPIRY = 1
    
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
    print("Loading spot and option data...\n")
    
    load_spot_data(
        SPOT_DATA_PATH
    )

    preload_option_files(
        OPTIONS_DATA_PATH,
        EXPIRY_LIMIT
    )

    total_option_files = sum(
        len(v)
        for v in OPTION_DATA_CACHE.values()
    )

    print(
        f"Cached "
        f"{total_option_files:,} "
        f"option files"
    )
    
    processed_count = 0
    
    for idx, (strike_dist, max_premium, target_mult, (win_start, win_finish)) in enumerate(combinations, 1):
        
        # Check if config already processed
        if not existing_configs.empty:
            already_processed = (
                (existing_configs['strike_distance_pct'] == strike_dist) &
                (existing_configs['max_total_premium_pct'] == max_premium) &
                (existing_configs['target_multiplier'] == target_mult) &
                (existing_configs['window_start'] == win_start) &
                (existing_configs['window_finish'] == win_finish) & 
                (existing_configs['limit_one_trade'] == LIMIT_ONE_TRADE_PER_EXPIRY)
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
        
        config_start_time = datetime.now()
        
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
        
        config_end_time = datetime.now()
        config_duration = (config_end_time - config_start_time).total_seconds()
        
        print(f"\nConfiguration processed in {config_duration:.2f} seconds ({config_duration/60:.2f} minutes)\n")
        
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
            # time.sleep(180)


if __name__ == "__main__":
    main()
    print("\n" + "="*60)
    print("All combinations processed!")
    print(f"Config log saved to: {os.path.join(RESULTS_BASE_PATH, 'config_log.csv')}")
    print("="*60)