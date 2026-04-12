import pandas as pd
import os
import numpy as np
from multiprocessing import Pool, cpu_count

def compute_state_transition_probs(
    df,
    x_list=[0.5, 1.0, 1.5],
    y_list=[0.5, 1.0],
    neutral_threshold=0.0025,
    max_holding_candles=375,
    slippage=0.0,
    show_progress=False,
    stock_name="",
    save_trades=False
):
    
    # --- Vectorized candle classification ---
    df["Candle_Type"] = np.where(
        df["Open"] <= 0, "Neutral",
        np.where(
            np.abs(df["Close"] - df["Open"]) / df["Open"] < neutral_threshold, "Neutral",
            np.where(df["Close"] > df["Open"], "Green", "Red")
        )
    )
    df["Prev_Candle"] = df["Candle_Type"].shift(1)

    # --- Daily grouping ---
    df["Trade_Date"] = pd.to_datetime(df.index).date

    daily = df.groupby("Trade_Date").agg({
        "Open": "first",
        "High": "max",
        "Low": "min",
        "Close": "last"
    })

    # Vectorized daily classification
    daily["Prev_Day_Type"] = np.where(
        daily["Open"] <= 0, "Neutral",
        np.where(
            np.abs(daily["Close"] - daily["Open"]) / daily["Open"] < neutral_threshold, "Neutral",
            np.where(daily["Close"] > daily["Open"], "Green", "Red")
        )
    )
    daily["Prev_Day_Type"] = daily["Prev_Day_Type"].shift(1)

    daily["Prev_Day_High"] = daily["High"].shift(1)
    daily["Prev_Day_Low"] = daily["Low"].shift(1)

    df = df.merge(
        daily[["Prev_Day_Type", "Prev_Day_High", "Prev_Day_Low"]],
        left_on="Trade_Date",
        right_index=True,
        how="left"
    )

    df["Open_Type"] = df["Candle_Type"]

    df["Prev_High"] = df["High"].shift(1)
    df["Prev_Low"] = df["Low"].shift(1)

    # Vectorized break detection
    df["Break_Type"] = np.where(
        df["High"] >= df["Prev_High"], "High_Broken",
        np.where(df["Low"] <= df["Prev_Low"], "Low_Broken", None)
    )
    df["Break_Type"] = df["Break_Type"].shift(1)

    # Add time column for filtering during processing
    df["Time"] = pd.to_datetime(df.index).time

    if len(df) == 0:
        return (pd.DataFrame(), pd.DataFrame()) if save_trades else pd.DataFrame()

    # --- Convert to numpy arrays for faster access ---
    highs = df["High"].values
    lows = df["Low"].values
    prev_day_highs = df["Prev_Day_High"].values
    prev_day_lows = df["Prev_Day_Low"].values
    break_types = df["Break_Type"].values
    prev_days = df["Prev_Day_Type"].values
    open_types = df["Open_Type"].values
    prev_candles = df["Prev_Candle"].values
    times = df["Time"].values
    original_index = df.index
    
    total_rows = len(df)
    progress_step = max(1, total_rows // 20)
    records = []
    trades = []

    for i in range(total_rows):
        
        if show_progress and i > 0 and i % progress_step == 0:
            progress_pct = (i / total_rows) * 100
            print(f"  │   Progress: {progress_pct:.0f}% ({i}/{total_rows} rows) - {stock_name}")

        # Skip 09:15 candles
        if times[i] == pd.Timestamp("09:15").time():
            continue

        # Skip invalid rows
        if pd.isna(prev_day_highs[i]) or pd.isna(break_types[i]):
            continue

        break_type = break_types[i]
        prev_day = prev_days[i]
        open_type = open_types[i]
        prev_candle = prev_candles[i]

        # =========================
        # LONG SETUP
        # =========================
        if break_type == "High_Broken":
            ref = prev_day_highs[i]

            for x in x_list:
                base_level = ref * (1 + x / 100)

                if lows[i] <= base_level <= highs[i]:
                    entry_price = base_level * (1 + slippage)

                    for y in y_list:
                        target = base_level * (1 + y / 100)
                        stop = base_level * (1 - y / 100)

                        # Vectorized forward simulation
                        end_idx = min(i + 1 + max_holding_candles, total_rows)
                        future_highs = highs[i+1:end_idx]
                        future_lows = lows[i+1:end_idx]

                        if len(future_highs) == 0:
                            outcome = 0
                            exit_idx = None
                            exit_price = None
                            holding_candles = 0
                        else:
                            # Find first hit using numpy
                            hit_target = future_highs >= target
                            hit_stop = future_lows <= stop
                            
                            target_idx = np.argmax(hit_target) if hit_target.any() else len(future_highs)
                            stop_idx = np.argmax(hit_stop) if hit_stop.any() else len(future_highs)
                            
                            if target_idx == stop_idx and target_idx < len(future_highs):
                                outcome = 0
                                exit_idx = i + 1 + target_idx
                                exit_price = stop
                                holding_candles = target_idx + 1
                            elif target_idx < stop_idx:
                                outcome = 1
                                exit_idx = i + 1 + target_idx
                                exit_price = target
                                holding_candles = target_idx + 1
                            elif stop_idx < target_idx:
                                outcome = 0
                                exit_idx = i + 1 + stop_idx
                                exit_price = stop
                                holding_candles = stop_idx + 1
                            else:
                                outcome = 0
                                exit_idx = None
                                exit_price = None
                                holding_candles = len(future_highs)

                        records.append({
                            "prev_day": prev_day,
                            "open": open_type,
                            "prev_candle": prev_candle,
                            "break": break_type,
                            "x": x,
                            "y": y,
                            "outcome": outcome
                        })
                        
                        if save_trades:
                            pnl = ((exit_price - entry_price) / entry_price * 100) if exit_price else 0
                            trades.append({
                                "stock": stock_name,
                                "entry_time": original_index[i],
                                "exit_time": original_index[exit_idx] if exit_idx else None,
                                "direction": "LONG",
                                "prev_day": prev_day,
                                "open": open_type,
                                "prev_candle": prev_candle,
                                "break": break_type,
                                "x": x,
                                "y": y,
                                "entry_price": round(entry_price, 2),
                                "target": round(target, 2),
                                "stop": round(stop, 2),
                                "exit_price": round(exit_price, 2) if exit_price else None,
                                "outcome": "WIN" if outcome == 1 else "LOSS",
                                "pnl_pct": round(pnl, 2),
                                "holding_candles": holding_candles
                            })

        # =========================
        # SHORT SETUP
        # =========================
        elif break_type == "Low_Broken":
            ref = prev_day_lows[i]

            for x in x_list:
                base_level = ref * (1 - x / 100)

                if lows[i] <= base_level <= highs[i]:
                    entry_price = base_level * (1 - slippage)

                    for y in y_list:
                        target = base_level * (1 - y / 100)
                        stop = base_level * (1 + y / 100)

                        # Vectorized forward simulation
                        end_idx = min(i + 1 + max_holding_candles, total_rows)
                        future_highs = highs[i+1:end_idx]
                        future_lows = lows[i+1:end_idx]

                        if len(future_lows) == 0:
                            outcome = 0
                            exit_idx = None
                            exit_price = None
                            holding_candles = 0
                        else:
                            # Find first hit using numpy
                            hit_target = future_lows <= target
                            hit_stop = future_highs >= stop
                            
                            target_idx = np.argmax(hit_target) if hit_target.any() else len(future_lows)
                            stop_idx = np.argmax(hit_stop) if hit_stop.any() else len(future_lows)
                            
                            if target_idx == stop_idx and target_idx < len(future_lows):
                                outcome = 0
                                exit_idx = i + 1 + target_idx
                                exit_price = stop
                                holding_candles = target_idx + 1
                            elif target_idx < stop_idx:
                                outcome = 1
                                exit_idx = i + 1 + target_idx
                                exit_price = target
                                holding_candles = target_idx + 1
                            elif stop_idx < target_idx:
                                outcome = 0
                                exit_idx = i + 1 + stop_idx
                                exit_price = stop
                                holding_candles = stop_idx + 1
                            else:
                                outcome = 0
                                exit_idx = None
                                exit_price = None
                                holding_candles = len(future_lows)

                        records.append({
                            "prev_day": prev_day,
                            "open": open_type,
                            "prev_candle": prev_candle,
                            "break": break_type,
                            "x": x,
                            "y": y,
                            "outcome": outcome
                        })
                        
                        if save_trades:
                            pnl = ((entry_price - exit_price) / entry_price * 100) if exit_price else 0
                            trades.append({
                                "stock": stock_name,
                                "entry_time": original_index[i],
                                "exit_time": original_index[exit_idx] if exit_idx else None,
                                "direction": "SHORT",
                                "prev_day": prev_day,
                                "open": open_type,
                                "prev_candle": prev_candle,
                                "break": break_type,
                                "x": x,
                                "y": y,
                                "entry_price": round(entry_price, 2),
                                "target": round(target, 2),
                                "stop": round(stop, 2),
                                "exit_price": round(exit_price, 2) if exit_price else None,
                                "outcome": "WIN" if outcome == 1 else "LOSS",
                                "pnl_pct": round(pnl, 2),
                                "holding_candles": holding_candles
                            })

    if not records:
        return (pd.DataFrame(), pd.DataFrame()) if save_trades else pd.DataFrame()

    df_events = pd.DataFrame(records)

    summary = (
        df_events
        .groupby(["prev_day", "open", "prev_candle", "break", "x", "y"])["outcome"]
        .agg(["mean", "count"])
        .reset_index()
    )

    summary.rename(columns={
        "mean": "WinRate",
        "count": "Trades"
    }, inplace=True)

    summary["WinRate"] = (summary["WinRate"] * 100).round(2)
    summary = summary.sort_values("WinRate", ascending=False).reset_index(drop=True)

    if save_trades:
        df_trades = pd.DataFrame(trades) if trades else pd.DataFrame()
        return summary, df_trades
    
    return summary


def process_single_file(args):
    """Process a single stock file - for multiprocessing"""
    file_path, stock_name, file_num, total_files, save_trades = args
    
    try:    
        print(f"\n[{file_num}/{total_files}] Processing: {stock_name}")
        
        df = pd.read_csv(file_path)
        print(f"  ├─ Loaded {len(df)} rows")
        
        df["Date"] = pd.to_datetime(df["Date"])
        df.set_index("Date", inplace=True)
        
        print(f"  ├─ Running probability model...")
        if save_trades:
            result, trades = compute_state_transition_probs(df, show_progress=True, stock_name=stock_name, save_trades=True)
        else:
            result = compute_state_transition_probs(df, show_progress=True, stock_name=stock_name, save_trades=False)
            trades = None
        
        if result.empty:
            print(f"  └─ ⚠ No valid events, skipping...")
            return None, None
        
        result.insert(0, "company", stock_name)
        print(f"  └─ ✓ Found {len(result)} state combinations")
        if save_trades and trades is not None and not trades.empty:
            print(f"      ✓ Captured {len(trades)} individual trades")
        
        return result, trades
        
    except Exception as e:
        print(f"  └─ ✗ Error processing {stock_name}: {str(e)}")
        return None, None


if __name__ == "__main__":

    from datetime import datetime

    data_dir = r"data\storage\raw\equity\minute"
    results_dir = r"backtestresults\markov\cond_prob"

    LIMIT = 500  
    BATCH_SIZE = 20
    USE_MULTIPROCESSING = True
    SAVE_TRADES = True
    NUM_PROCESSES = max(1, cpu_count() - 2)

    os.makedirs(results_dir, exist_ok=True)

    files = sorted([f for f in os.listdir(data_dir) if f.endswith(".csv")])
    files_to_process = files[:LIMIT]

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_folder = os.path.join(results_dir, timestamp)
    os.makedirs(results_folder, exist_ok=True)
    
    output_path = os.path.join(results_folder, "backtest_results.csv")
    trades_path = os.path.join(results_folder, "trades.csv")

    all_results = []
    all_trades = []
    total_files = len(files_to_process)
    num_batches = (total_files + BATCH_SIZE - 1) // BATCH_SIZE

    print(f"\nProcessing {total_files} files in {num_batches} batches of {BATCH_SIZE}")
    if USE_MULTIPROCESSING:
        print(f"Using multiprocessing with {NUM_PROCESSES} processes per batch")
    if SAVE_TRADES:
        print(f"Trade metadata will be saved\n")

    # Process in batches
    for batch_num in range(num_batches):
        start_idx = batch_num * BATCH_SIZE
        end_idx = min(start_idx + BATCH_SIZE, total_files)
        batch_files = files_to_process[start_idx:end_idx]
        
        print(f"\n{'='*60}")
        print(f"BATCH {batch_num + 1}/{num_batches} - Processing files {start_idx + 1} to {end_idx}")
        print(f"{'='*60}")

        batch_results = []

        if USE_MULTIPROCESSING and len(batch_files) > 1:
            file_args = []
            for i, file in enumerate(batch_files):
                file_path = os.path.join(data_dir, file)
                stock_name = file.split("_", 1)[-1].replace(".csv", "")
                global_file_num = start_idx + i + 1
                file_args.append((file_path, stock_name, global_file_num, total_files, SAVE_TRADES))
            
            with Pool(processes=NUM_PROCESSES) as pool:
                results = pool.map(process_single_file, file_args)
            
            for result, trades in results:
                if result is not None:
                    batch_results.append(result)
                if trades is not None and not trades.empty:
                    all_trades.append(trades)
            
        else:
            for i, file in enumerate(batch_files):
                file_path = os.path.join(data_dir, file)
                stock_name = file.split("_", 1)[-1].replace(".csv", "")
                global_file_num = start_idx + i + 1
                
                result, trades = process_single_file((file_path, stock_name, global_file_num, total_files, SAVE_TRADES))
                if result is not None:
                    batch_results.append(result)
                if trades is not None and not trades.empty:
                    all_trades.append(trades)

        all_results.extend(batch_results)
        
        print(f"\n✓ Batch {batch_num + 1} complete: {len(batch_results)} stocks processed successfully")
        print(f"  Total processed so far: {len(all_results)} stocks")

    # Combine and save all results
    print(f"\n{'='*60}")
    if all_results:
        final_df = pd.concat(all_results, ignore_index=True)
        final_df = final_df.sort_values(["WinRate", "Trades"], ascending=[False, False]).reset_index(drop=True)
        final_df.to_csv(output_path, index=False)
        print(f"✓ Saved all results → {output_path}")
        print(f"  Total combinations: {len(final_df)}")
        print(f"  Total stocks processed: {len(all_results)}")
    else:
        print("⚠ No results to save")
    
    if SAVE_TRADES and all_trades:
        final_trades = pd.concat(all_trades, ignore_index=True)
        
        # Filter trades: only save if WinRate >= 75% and Trades >= 10
        # First, calculate win rate for each combination
        trade_stats = final_trades.groupby(["stock", "prev_day", "open", "prev_candle", "break", "x", "y"]).agg({
            "outcome": lambda x: (x == "WIN").sum() / len(x) * 100,
            "stock": "count"
        }).rename(columns={"outcome": "calc_winrate", "stock": "calc_trades"}).reset_index()
        
        # Filter combinations with WinRate >= 75% and Trades >= 10
        filtered_stats = trade_stats[(trade_stats["calc_winrate"] >= 75) & (trade_stats["calc_trades"] >= 10)]
        
        # Merge to filter trades
        filtered_trades = final_trades.merge(
            filtered_stats[["stock", "prev_day", "open", "prev_candle", "break", "x", "y"]],
            on=["stock", "prev_day", "open", "prev_candle", "break", "x", "y"],
            how="inner"
        )
        
        if not filtered_trades.empty:
            filtered_trades = filtered_trades.sort_values("entry_time").reset_index(drop=True)
            filtered_trades.to_csv(trades_path, index=False)
            print(f"✓ Saved filtered trades → {trades_path}")
            print(f"  Total trades (WinRate >= 75%, Trades >= 10): {len(filtered_trades)}")
        else:
            print("⚠ No trades meet the criteria (WinRate >= 75%, Trades >= 10)")
