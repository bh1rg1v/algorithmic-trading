"""Equity data fetcher using Kite API."""
import os
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta

import pandas as pd
import requests

# Configuration

# Kite session token - we have update this for every session
ENCTOKEN = ("8RwRDlGprV9FTb4Plccp5FPHHyJzO6Wd8XPOm1Ah2LfusnQEwU+tTsRtUW1RvKBPbTW7l4N+PHI7DNvMPKbE4AQBg5M56MSWWplRfP9KjpB+WQlrhIhxnA==")
START_DATE = datetime(2014, 1, 1)  # Data start date
END_DATE = datetime.today()        # Data end date
TIMEFRAME = "minute"                  # Data timeframe - Available: minute, 5minute, 30minute, 60minute, 3hour, day, etc.
LIMIT = 5000                     # Max symbols to process
MAX_WORKERS = 3                  # Concurrent symbols; keep low to stay within Kite's rate limit
REQUEST_INTERVAL = 0.5           # Minimum seconds between any API call across all threads (max ~2 req/s globally)


class RateLimiter:
    """Thread-safe rate limiter that spaces API requests across all threads."""
    def __init__(self, min_interval: float):
        self._lock = threading.Lock()
        self._last_call = 0.0
        self.min_interval = min_interval

    def wait(self):
        with self._lock:
            now = time.time()
            elapsed = now - self._last_call
            if elapsed < self.min_interval:
                time.sleep(self.min_interval - elapsed)
            self._last_call = time.time()


_print_lock = threading.Lock()

def safe_print(*args, **kwargs):
    """Thread-safe print to avoid garbled output from concurrent workers."""
    with _print_lock:
        print(*args, **kwargs)


def _fetch_symbol(counter, token, symbol, save_path, rate_limiter):
    """Fetch and save data for a single symbol. Returns per-symbol metrics dict."""
    result = {
        'total_processed': 0,
        'successfully_fetched': 0,
        'skipped_existing': 0,
        'insufficient_data': 0,
        'rate_limited': 0,
        'api_errors': 0,
        'json_errors': 0,
    }

    filename = os.path.join(save_path, f"{counter:04d}_{symbol}.csv")

    # Check if file exists and get last date — read only last line for speed
    file_start_date = START_DATE
    if os.path.exists(filename):
        try:
            with open(filename, 'rb') as f:
                # Seek to end and read last non-empty line
                f.seek(0, 2)
                file_size = f.tell()
                if file_size > 0:
                    pos = file_size - 1
                    while pos > 0:
                        f.seek(pos)
                        char = f.read(1)
                        if char == b'\n' and pos != file_size - 1:
                            break
                        pos -= 1
                    last_line = f.read().decode('utf-8').strip()
                    if last_line:
                        last_date_str = last_line.split(',')[0]
                        # Parse date (format: 2015-04-01T09:15:00+0530)
                        last_date = datetime.strptime(last_date_str[:10], '%Y-%m-%d')
                        file_start_date = last_date + timedelta(days=1)

                        if file_start_date > END_DATE:
                            safe_print(f"File {filename} already up to date. Skipping.")
                            result['skipped_existing'] += 1
                            return result

                        safe_print(f"Updating {filename} from {file_start_date.strftime('%Y-%m-%d')}")
        except Exception as e:
            safe_print(f"Error reading existing file {filename}: {e}. Re-fetching from start.")
            file_start_date = START_DATE

    result['total_processed'] += 1

    # Each thread gets its own session (requests.Session is not thread-safe when shared)
    session = requests.Session()
    header = {"Authorization": f"enctoken {ENCTOKEN}"}

    # Collect chunks in a list, concat once at end
    chunks = []
    start_iter = file_start_date
    rate_limit_retries = 0

    # Fetch data in 60-day chunks
    while start_iter <= END_DATE:
        period_end = start_iter + timedelta(days=59)
        if period_end > END_DATE:
            period_end = END_DATE

        # Build API request
        url = (f"https://kite.zerodha.com/oms/instruments/historical/"
               f"{token}/{TIMEFRAME}")
        params = {
            "oi": 0,
            "from": start_iter.strftime('%Y-%m-%d'),
            "to": period_end.strftime('%Y-%m-%d')
        }

        # Enforce global rate limit before every request
        rate_limiter.wait()

        # Make API call with timeout to avoid hanging indefinitely
        response = session.get(url, params=params, headers=header, timeout=10)

        # Handle rate limiting
        if response.status_code == 429:
            # Sleep longer here since multiple threads are collectively hitting the API
            safe_print(f"\nRate limit exceeded for {symbol}. Waiting 10 seconds...")
            result['rate_limited'] += 1
            time.sleep(10)
            chunks = []  # Reset and restart from where this symbol began
            start_iter = file_start_date
            rate_limit_retries += 1
            if rate_limit_retries > 3:
                safe_print(f"Too many rate limit retries for {symbol}. Skipping.")
                break
            continue

        # Handle API errors
        elif response.status_code != 200:
            safe_print(f"\nError {response.status_code} for token {token}: "
                      f"{response.text}\n")
            result['api_errors'] += 1
            break

        # Parse response data
        try:
            data = response.json().get("data", {}).get("candles", [])
        except Exception as e:
            safe_print(f"JSON parsing error for token {token}: {e}")
            safe_print(f"Raw response: {response.text}")
            result['json_errors'] += 1
            break

        # Collect chunk
        temp_df = pd.DataFrame(data, columns=["Date", "Open", "High",
                                               "Low", "Close", "Volume"])
        if not temp_df.empty:
            chunks.append(temp_df)

        # Move to next period
        start_iter = period_end + timedelta(days=1)

    # Merge all chunks into one DataFrame
    df = pd.concat(chunks, ignore_index=True) if chunks else pd.DataFrame()

    # Save or append data if sufficient
    if len(df) > 0:
        if os.path.exists(filename) and file_start_date > START_DATE:
            # Append to existing file
            df.to_csv(filename, mode='a', header=False, index=False)
            safe_print(f"Appended {len(df)} rows to {filename}")
        else:
            # Create new file
            df.to_csv(filename, index=False)
            safe_print(f"Saved {filename} with {len(df)} rows, "
                      f"starting from {df.iloc[0, 0][:10]}")
        result['successfully_fetched'] += 1

    elif file_start_date == START_DATE:
        # Only log insufficient data for new files
        safe_print(f"Skipping {filename}: Insufficient data, "
                  f"got {len(df)} rows.")
        result['insufficient_data'] += 1

    return result


def fetch_equity_data():
    """Fetch historical equity data from Kite API."""
    start_time = time.time()
    
    # Initialize metrics tracking
    metrics = {
        'total_processed': 0,
        'successfully_fetched': 0,
        'skipped_existing': 0,
        'insufficient_data': 0,
        'rate_limited': 0,
        'api_errors': 0,
        'json_errors': 0
    }
    
    # Load symbols from CSV
    equity_df = pd.read_csv(r"D:\github\algorithmic-trading\data\storage\tokens.csv")
    equity_df = equity_df.dropna(subset=["KITE_ID"])

    # to get data for INDIAVIX, added the symbol with kite id in the csv
    equity_df = equity_df.tail(1)

    # Create output directory
    # save_path = os.path.join("data/storage/raw/equity/zerodha/", f"{START_DATE.year}-{END_DATE.year}", TIMEFRAME)

    local_output = r"D:\github\algorithmic-trading\data\storage\equity"
    drive_output = r"G:\My Drive\public\paid\data\equity"

    save_path = os.path.join(local_output, TIMEFRAME)
    # save_path = os.path.join(drive_output, TIMEFRAME)
    os.makedirs(save_path, exist_ok=True)

    rate_limiter = RateLimiter(min_interval=REQUEST_INTERVAL)

    # Slice to LIMIT before submitting
    rows = list(equity_df.itertuples(index=True))[:LIMIT]

    futures = {}
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        for row in rows:
            counter = row.Index + 1
            token = int(row.KITE_ID)
            symbol = row.SYMBOL
            future = executor.submit(_fetch_symbol, counter, token, symbol, save_path, rate_limiter)
            futures[future] = symbol

        for future in as_completed(futures):
            symbol = futures[future]
            try:
                result = future.result()
                for key in metrics:
                    metrics[key] += result[key]

                # Batch processing delay
                if metrics['successfully_fetched'] % 100 == 0 and metrics['successfully_fetched'] > 0:
                    print(f"\nFetched {metrics['successfully_fetched']} files, sleeping for 3 seconds...\n")
                    time.sleep(3)

            except Exception as e:
                safe_print(f"Unhandled error for {symbol}: {e}")
                metrics['api_errors'] += 1

    # Display final summary
    end_time = time.time()
    elapsed_time = end_time - start_time
    
    print("\n" + "="*50)
    print("PROCESSING SUMMARY")
    print("="*50)
    print(f"Total symbols in CSV: {len(equity_df)}")
    print(f"Symbols processed: {metrics['total_processed']}")
    print(f"Successfully fetched: {metrics['successfully_fetched']}")
    print(f"Skipped (existing files): {metrics['skipped_existing']}")
    print(f"Insufficient data: {metrics['insufficient_data']}")
    print(f"Rate limited requests: {metrics['rate_limited']}")
    print(f"API errors: {metrics['api_errors']}")
    print(f"JSON parsing errors: {metrics['json_errors']}")
    print(f"Processing time: {elapsed_time:.2f} seconds")
    print(f"Average time per symbol: {elapsed_time/max(metrics['total_processed'], 1):.2f} seconds")
    print("="*50 + "\n")


def main():
    """Main function to execute equity data fetching."""
    fetch_equity_data()


if __name__ == "__main__":
    main()
