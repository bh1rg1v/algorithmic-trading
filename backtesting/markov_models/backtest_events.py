# Backtest minute-level executions for milestone events
# Usage: put this script in a directory, set DATA_DIR to your minute CSV files folder
# and EVENTS_CSV to the CSV that contains the event definitions (the example you provided).

"""
Assumptions & behavior
- Minute CSVs contain columns: ['Date', 'Timestamp', 'Open', 'High', 'Low', 'Close', 'Volume']
  where 'Date' is in a parseable format (e.g., '4/1/2015') and 'Timestamp' is optional.
- The events CSV must have columns: Event, Probability, Count, Symbol, Filename
  The `Event` column follows the pattern produced earlier, e.g.
  "4.0% < Prev_Low | Low_Broken, Last Red, 3.5 Reached"
- For each trading day in minute data (starting from second calendar day), the script:
  1) computes previous trading day's High/Low and previous day's candle color
  2) if previous day's candle color matches the Event requirement and a break (Prev_High/Prev_Low) happens,
     it looks for the minute where the milestone `base` is reached and opens a trade at the base price
  3) closes the trade when the `next` milestone is reached, or at day-close if not reached
- Entry price is taken as the milestone level (i.e., exact level like prev_low * (1 - base/100)).
  Exit price is taken as the exact `next` level if reached; otherwise the day's close.
- Shorts: profit = (entry - exit) / entry. Longs: profit = (exit - entry) / entry.
- Simple slippage and commission can be applied (percentage or per-trade fixed commission).

Notes on realism
- This script treats intraday minute bars as having immediate execution at the milestone level
  (it does not model partial fills or order queuing). That is consistent with the statistical
  nature of your earlier analysis but may be optimistic for real trading.
"""

import os
import re
import math
import glob
import pandas as pd
from datetime import datetime

data = r"data\storage\processed\equity\zerodha\2015\minute"
events= r"backtestresults\markov\run_markov_analysis\markov_run_20250904_193226\markov_combined_sorted.csv"

# Configuration

DATA_DIR = data                 # directory containing minute CSV files (one per symbol)
EVENTS_CSV = events             # CSV listing events (Event,Probability,Count,Symbol,Filename)
EVENTS_LIMIT = 5                # number of events to process
NEUTRAL_THRESHOLD = 0.001       # 0.1% threshold for neutral candle
SLIPPAGE_PCT = 0.0000           # 0.05% slippage assumed for entry/exit
COMM_PER_TRADE = 0.0            # flat commission per trade in absolute price units (set 0 if not used)
STOP_LOSS_PCT = 0.5             # 0.5% stop loss on both sides
DATE_COL = "Date"               # name of the date column in minute CSVs


def parse_event_string(event_str):
    """Parse the event string and return a dict with elements:
    - ref: 'Prev_High' or 'Prev_Low'
    - broken: 'High_Broken' or 'Low_Broken'
    - last_candle: 'Last Red' / 'Last Green' / 'Last Neutral'
    - base: base pct (float)
    - next: next pct (float)
    - side: 'long' or 'short' (derived from ref)
    """
    # Example event: "4.0% < Prev_Low | Low_Broken, Last Red, 3.5 Reached"
    # Regex to capture "4.0% < Prev_Low" and the rest
    event = event_str.strip().strip('"')

    # capture the move descriptor (like 4.0% < Prev_Low)
    m_move = re.match(
        r"([0-9\.]+)%\s*([<>])\s*(Prev_High|Prev_Low)", event
    )
    if not m_move:
        raise ValueError(f"Couldn't parse move part of Event: {event}")
    move_pct = float(m_move.group(1))
    direction = m_move.group(2)
    ref = m_move.group(3)

    # side: if ref is Prev_High and direction is '>' => long
    # if ref is Prev_Low and direction is '<' => short
    side = ('long' if (ref == 'Prev_High' and direction == '>')
            else 'short')

    # extract last candle and base reached percent (the tail after the comma)
    # find "Last ..." and final "X Reached"
    m_tail = re.search(
        r"(Last\s+(Red|Green|Neutral))\s*,\s*([0-9\.]+)\s*Reached",
        event,
        re.IGNORECASE
    )
    if not m_tail:
        raise ValueError(f"Couldn't parse tail of Event: {event}")

    last_candle = m_tail.group(1).title()  # normalize, e.g., "Last Red"
    base_pct = float(m_tail.group(3))

    # Compute 'next' as the first percentage in the start of the event (move_pct)
    next_pct = move_pct

    return {
        'event_raw': event,
        'ref': ref,
        'direction': direction,
        'side': side,
        'last_candle': last_candle,
        'base': base_pct,
        'next': next_pct
    }


def read_minute_csv(path):
    df = pd.read_csv(path)
    # Ensure Date column is datetime
    if DATE_COL in df.columns:
        df[DATE_COL] = pd.to_datetime(df[DATE_COL], errors='coerce')
    else:
        # try infer from Timestamp if combined
        if 'Timestamp' in df.columns:
            df['Datetime'] = pd.to_datetime(df['Timestamp'], errors='coerce')
            df[DATE_COL] = df['Datetime'].dt.date
            df[DATE_COL] = pd.to_datetime(df[DATE_COL])
        else:
            raise ValueError(
                f"No '{DATE_COL}' or 'Timestamp' column found in {path}"
            )

    # Lowercase column names for flexibility
    df.rename(columns={c: c.strip() for c in df.columns}, inplace=True)
    # Ensure numeric types
    for col in ['Open', 'High', 'Low', 'Close']:
        if col not in df.columns:
            raise ValueError(
                f"Minute CSV missing required column '{col}' in {path}"
            )
        df[col] = pd.to_numeric(df[col], errors='coerce')

    # Create a copy of date-only for grouping
    df['__date'] = pd.to_datetime(df[DATE_COL]).dt.normalize()
    return df


def prev_day_stats(df_day):
    """Given minute rows for a day, return day's High, Low, Open(first), Close(last) and candle color string."""
    day_high = df_day['High'].max()
    day_low = df_day['Low'].min()
    day_open = df_day.iloc[0]['Open']
    day_close = df_day.iloc[-1]['Close']
    if (day_open == 0 or
            abs(day_close - day_open) / day_open < NEUTRAL_THRESHOLD):
        candle = 'Last Neutral'
    else:
        candle = ('Last Green' if day_close > day_open
                  else 'Last Red')
    return {
        'High': day_high,
        'Low': day_low,
        'Open': day_open,
        'Close': day_close,
        'Candle': candle
    }


def backtest_event_on_df(df_min, event_def, verbose=False):
    """Backtest one parsed event on a minute-level DataFrame. Returns a results dict."""
    results = []  # list of trade dicts

    # group by date
    grouped = {d: g for d, g in df_min.groupby('__date')}
    sorted_dates = sorted(grouped.keys())

    # start from second trading day (since need previous day's stats)
    for i in range(1, len(sorted_dates)):
        prev_date = sorted_dates[i-1]
        date = sorted_dates[i]
        df_prev = grouped[prev_date]
        df_day = grouped[date]

        prev_stats = prev_day_stats(df_prev)
        # check previous day's candle requirement
        if prev_stats['Candle'] != event_def['last_candle']:
            continue

        prev_high = prev_stats['High']
        prev_low = prev_stats['Low']

        # ignore invalid
        if prev_high <= 0 or prev_low <= 0:
            continue

        # compute base & next levels
        if event_def['ref'] == 'Prev_High':
            base_level = prev_high * (1 + event_def['base']/100.0)
            next_level = prev_high * (1 + event_def['next']/100.0)
        else:
            base_level = prev_low * (1 - event_def['base']/100.0)
            next_level = prev_low * (1 - event_def['next']/100.0)

        broken_flag = False
        trade_taken = False  # Only one trade per day
        in_position = False
        trade = None

        # iterate minutes in chronological order
        for idx, minute in df_day.iterrows():
            high = minute['High']
            low = minute['Low']
            close = minute['Close']

            # update broken flag: has the prev high/low been breached yet?
            if event_def['ref'] == 'Prev_High' and high >= prev_high:
                broken_flag = True
            if event_def['ref'] == 'Prev_Low' and low <= prev_low:
                broken_flag = True

            # check for base reached (only if no trade taken today)
            if not in_position and not trade_taken and broken_flag:
                if (event_def['ref'] == 'Prev_High' and
                        high >= base_level and low <= base_level):
                    # open long - price must be within range
                    entry_price = base_level * (1 + SLIPPAGE_PCT)  # slippage hurts entry for longs
                    in_position = True
                    trade_taken = True
                    trade = {'entry_time': minute[DATE_COL], 'entry_timestamp': minute.get('Timestamp', ''), 'entry_price': entry_price, 'side': 'long', 'open_idx': idx, 'prev_date': prev_date}
                    if verbose:
                        print(f"{date.date()} OPEN LONG @ {entry_price:.4f} (base {base_level:.4f})")
                elif (event_def['ref'] == 'Prev_Low' and
                      low <= base_level and high >= base_level):
                    # open short - price must be within range
                    entry_price = base_level * (1 - SLIPPAGE_PCT)  # slippage hurts entry for shorts
                    in_position = True
                    trade_taken = True
                    trade = {'entry_time': minute[DATE_COL], 'entry_timestamp': minute.get('Timestamp', ''), 'entry_price': entry_price, 'side': 'short', 'open_idx': idx, 'prev_date': prev_date}
                    if verbose:
                        print(f"{date.date()} OPEN SHORT @ {entry_price:.4f} (base {base_level:.4f})")

            # If in position, check for exit
            if in_position:
                entry_price = trade['entry_price']
                if trade['side'] == 'long':
                    stop_loss_level = entry_price * (1 - STOP_LOSS_PCT/100)
                    # Skip if both target and stop loss hit in same bar
                    if low <= stop_loss_level and high >= next_level:
                        in_position = False
                        trade = None
                        if verbose:
                            print(f"{date.date()} SKIPPED LONG - both target and stop loss hit")
                        break
                    # Stop loss check
                    elif low <= stop_loss_level:
                        exit_price = stop_loss_level * (1 - SLIPPAGE_PCT)
                        trade.update({'exit_time': minute[DATE_COL], 'exit_timestamp': minute.get('Timestamp', ''), 'exit_price': exit_price, 'exit_idx': idx, 'exit_reason': 'stop_loss'})
                        results.append(trade)
                        in_position = False
                        trade = None
                        if verbose:
                            print(f"{date.date()} STOP LOSS LONG @ {exit_price:.4f}")
                        break
                    # Target exit
                    elif high >= next_level:
                        exit_price = next_level * (1 - SLIPPAGE_PCT)
                        trade.update({'exit_time': minute[DATE_COL], 'exit_timestamp': minute.get('Timestamp', ''), 'exit_price': exit_price, 'exit_idx': idx, 'exit_reason': 'target'})
                        results.append(trade)
                        in_position = False
                        trade = None
                        if verbose:
                            print(f"{date.date()} CLOSE LONG @ {exit_price:.4f} (next {next_level:.4f})")
                        break
                else:
                    stop_loss_level = entry_price * (1 + STOP_LOSS_PCT/100)
                    # Skip if both target and stop loss hit in same bar
                    if high >= stop_loss_level and low <= next_level:
                        in_position = False
                        trade = None
                        if verbose:
                            print(f"{date.date()} SKIPPED SHORT - both target and stop loss hit")
                        break
                    # Stop loss check
                    elif high >= stop_loss_level:
                        exit_price = stop_loss_level * (1 + SLIPPAGE_PCT)
                        trade.update({'exit_time': minute[DATE_COL], 'exit_timestamp': minute.get('Timestamp', ''), 'exit_price': exit_price, 'exit_idx': idx, 'exit_reason': 'stop_loss'})
                        results.append(trade)
                        in_position = False
                        trade = None
                        if verbose:
                            print(f"{date.date()} STOP LOSS SHORT @ {exit_price:.4f}")
                        break
                    # Target exit
                    elif low <= next_level:
                        exit_price = next_level * (1 + SLIPPAGE_PCT)
                        trade.update({'exit_time': minute[DATE_COL], 'exit_timestamp': minute.get('Timestamp', ''), 'exit_price': exit_price, 'exit_idx': idx, 'exit_reason': 'target'})
                        results.append(trade)
                        in_position = False
                        trade = None
                        if verbose:
                            print(f"{date.date()} CLOSE SHORT @ {exit_price:.4f} (next {next_level:.4f})")
                        break

        # day ended: if still in position, close at day close
        if in_position and trade is not None:
            exit_price = df_day.iloc[-1]['Close']
            # apply slippage on exit
            if trade['side'] == 'long':
                exit_price = exit_price * (1 - SLIPPAGE_PCT)
            else:
                exit_price = exit_price * (1 + SLIPPAGE_PCT)
            trade.update({'exit_time': df_day.iloc[-1][DATE_COL], 'exit_timestamp': df_day.iloc[-1].get('Timestamp', ''), 'exit_price': exit_price, 'exit_idx': df_day.index[-1], 'exit_reason': 'eod'})
            results.append(trade)

    # compute stats
    trades = []
    for t in results:
        entry = t['entry_price']
        exitp = t['exit_price']
        side = t['side']
        pnl = 0.0
        if side == 'long':
            pnl = (exitp - entry) / entry
        else:
            pnl = (entry - exitp) / entry
        # subtract commission (absolute) relative to entry price
        if COMM_PER_TRADE:
            pnl -= COMM_PER_TRADE / entry
        t['pnl'] = pnl
        trades.append(t)

    # aggregate
    if trades:
        wins = sum(1 for t in trades if t['pnl'] > 0)
        losses = sum(1 for t in trades if t['pnl'] <= 0)
        win_rate = wins / len(trades) * 100
        avg_pnl = sum(t['pnl'] for t in trades) / len(trades)
        cum_pnl = math.prod([1 + t['pnl'] for t in trades]) - 1
    else:
        wins = losses = 0
        win_rate = avg_pnl = cum_pnl = 0.0

    summary = {
        'trades': len(trades),
        'wins': wins,
        'losses': losses,
        'win_rate_pct': round(win_rate, 2),
        'avg_pnl_pct': round(avg_pnl * 100, 4) if trades else 0.0,
        'cum_pnl_pct': round(cum_pnl * 100, 4) if trades else 0.0,
        'trades_detail': trades
    }
    return summary


def backtest_events_folder(events_csv, data_dir):
    # Create results directory
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    script_name = os.path.splitext(os.path.basename(__file__))[0]
    results_dir = f"backtestresults/markov/{script_name}/backtest_run_{timestamp}"
    trade_data_dir = os.path.join(results_dir, "trade_data")
    os.makedirs(trade_data_dir, exist_ok=True)
    
    events_df = pd.read_csv(events_csv)
    events_df = events_df[:EVENTS_LIMIT]
    results_all = []
    all_trades_by_symbol = {}  # Collect all trades by symbol

    for idx, row in events_df.iterrows():
        try:
            ev = parse_event_string(row['Event'])
        except Exception as e:
            print(f"Skipping row {idx} - parse error: {e}")
            continue

        filename = row.get('Filename', None)
        if pd.isna(filename) or filename is None:
            print(f"Skipping row {idx} - no Filename provided")
            continue

        path = os.path.join(data_dir, filename)
        if not os.path.exists(path):
            print(f"Missing file for row {idx}: {path}")
            continue

        print(f"Backtesting Event on {filename}: {ev['event_raw']}")
        df_min = read_minute_csv(path)
        summary = backtest_event_on_df(df_min, ev)
        
        # Collect trade data for this event
        symbol = row.get('Symbol', '')
        if summary['trades_detail']:
            if symbol not in all_trades_by_symbol:
                all_trades_by_symbol[symbol] = []
            
            for trade in summary['trades_detail']:
                all_trades_by_symbol[symbol].append({
                    'Date': trade['entry_time'].strftime('%Y-%m-%d') if hasattr(trade['entry_time'], 'strftime') else str(trade['entry_time']),
                    'Symbol': symbol,
                    'Event': ev['event_raw'],
                    'Trade Type': trade['side'].upper(),
                    'Entry Price': round(trade['entry_price'], 4),
                    'Entry Time': trade['entry_timestamp'],
                    'Exit Price': round(trade['exit_price'], 4),
                    'Exit Time': trade['exit_timestamp'],
                    'P&L': round((trade['exit_price'] - trade['entry_price']) if trade['side'] == 'long' else (trade['entry_price'] - trade['exit_price']), 4),
                    'Return %': round(trade['pnl'] * 100, 4)
                })
        
        out = {
            'Event': ev['event_raw'],
            'Symbol': symbol,
            'Filename': filename,
            'Trades': summary['trades'],
            'Wins': summary['wins'],
            'Losses': summary['losses'],
            'Win Rate (%)': summary['win_rate_pct'],
            'Avg_PnL_Pct': summary['avg_pnl_pct'],
            'Cum_PnL_Pct': summary['cum_pnl_pct']
        }
        results_all.append(out)

    # Save deduplicated trade data by symbol
    for symbol, trades_data in all_trades_by_symbol.items():
        trades_df = pd.DataFrame(trades_data)
        trades_df = trades_df.drop_duplicates()
        trade_file = os.path.join(trade_data_dir, f"{symbol}.csv")
        trades_df.to_csv(trade_file, index=False)
    
    # Calculate summary results
    summary_df = pd.DataFrame(results_all)
    # summary_df = summary_df.sort_values('Win Rate (%)', ascending=False)
    
    # Calculate overall statistics
    total_trades = summary_df['Trades'].sum()
    total_wins = summary_df['Wins'].sum()
    total_losses = summary_df['Losses'].sum()
    overall_win_rate = (total_wins / total_trades * 100) if total_trades > 0 else 0
    avg_pnl = summary_df['Avg_PnL_Pct'].mean()
    
    # Save text summary
    summary_text = f"""BACKTEST SUMMARY REPORT
{'='*50}

CONFIGURATION:
- Data Directory: {DATA_DIR}
- Events CSV: {EVENTS_CSV}
- Events Limit: {EVENTS_LIMIT}
- Stop Loss: None
- Slippage: {SLIPPAGE_PCT*100}%
- Commission per Trade: {COMM_PER_TRADE}
- Date Column: {DATE_COL}

OVERALL STATISTICS:
- Total Events Processed: {len(results_all)}
- Total Trades: {total_trades}
- Total Wins: {total_wins}
- Total Losses: {total_losses}
- Overall Win Rate: {overall_win_rate:.2f}%
- Average P&L per Event: {avg_pnl:.4f}%

EVENT BREAKDOWN:
{summary_df.to_string(index=False)}
"""
    
    text_file = os.path.join(results_dir, "backtest_summary.txt")
    with open(text_file, 'w') as f:
        f.write(summary_text)
    
    print(f"\nResults saved to: {results_dir}")
    print(f"Trade data saved to: {trade_data_dir}")
    
    return summary_df


if __name__ == '__main__':
    # Example run
    print("Running backtest for events...\n")
    if not os.path.exists(EVENTS_CSV):
        print(f"Events CSV not found: {EVENTS_CSV}")
    else:
        df_results = backtest_events_folder(EVENTS_CSV, DATA_DIR)
        print("\nBacktest summary:\n")
        print(df_results.to_string(index=False))

# End of script