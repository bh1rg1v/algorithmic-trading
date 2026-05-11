"""Equity data fetcher using Kite API."""
import os
import time
from datetime import datetime, timedelta

import pandas as pd
import requests

# Configuration

# Kite session token - we have update this for every session
ENCTOKEN = ("2VGUR92sBSdVVgPceh0oBskZbVULNm6ReCUrRIrJpwLtHgtAfBl9mWTjx8y8IM/m1Qur2g1OedjuLFf2hxSnXdCyWJih/EtA12RxB0JBLMD3l9VJkwh37Q==")
START_DATE = datetime(2015, 4, 1)  # Data start date
END_DATE = datetime(2026, 5, 30)   # Data end date
TIMEFRAME = "minute"                  # Data timeframe - Available: minute, 5minute, 30minute, 60minute, 3hour, day, etc.
LIMIT = 2500                      # Max symbols to process

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
    equity_df = pd.read_csv(os.path.join("data", "storage", "tokens.csv"))
    equity_df = equity_df.dropna(subset=["KITE_ID"])
    
    # Setup session and authentication
    session = requests.session()
    header = {"Authorization": f"enctoken {ENCTOKEN}"}
    
    # Create output directory
    # save_path = os.path.join("data/storage/raw/equity/zerodha/", f"{START_DATE.year}-{END_DATE.year}", TIMEFRAME)

    local_output = "data/storage/equity/"
    drive_output = r"G:\My Drive\public\paid\data\equity"

    save_path = os.path.join(local_output, TIMEFRAME)
    os.makedirs(save_path, exist_ok=True)
    
    # Process each symbol
    for index, row in equity_df.iterrows():
        counter = index + 1
        
        # Check processing limit
        if counter > LIMIT:
            print(f"Reached row limit ({LIMIT}). Stopping execution.")
            break

        # Extract symbol data
        token = int(row["KITE_ID"])
        symbol = row["SYMBOL"]
        filename = os.path.join(save_path, f"{counter:04d}_{symbol}.csv")

        # Check if file exists and get last date
        file_start_date = START_DATE
        if os.path.exists(filename):
            try:
                existing_df = pd.read_csv(filename)
                if len(existing_df) > 0:
                    last_date_str = existing_df.iloc[-1]['Date']
                    # Parse date (format: 2015-04-01T09:15:00+0530)
                    last_date = datetime.strptime(last_date_str[:10], '%Y-%m-%d')
                    file_start_date = last_date + timedelta(days=1)
                    
                    if file_start_date > END_DATE:
                        print(f"File {filename} already up to date. Skipping.")
                        metrics['skipped_existing'] += 1
                        continue
                    
                    print(f"Updating {filename} from {file_start_date.strftime('%Y-%m-%d')}")
            except Exception as e:
                print(f"Error reading existing file {filename}: {e}. Re-fetching from start.")
                file_start_date = START_DATE
        
        metrics['total_processed'] += 1

        # Initialize data collection
        df = pd.DataFrame()
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

            # Make API call
            response = session.get(url, params=params, headers=header)

            # Handle rate limiting
            if response.status_code == 429:
                print(f"\nRate limit exceeded for {symbol}. Waiting 5 seconds...")
                metrics['rate_limited'] += 1
                time.sleep(5)
                df = pd.DataFrame()  # Reset and restart
                start_iter = START_DATE
                rate_limit_retries += 1
                if rate_limit_retries > 3:
                    print(f"Too many rate limit retries for {symbol}. Skipping.")
                    break
                continue

            # Handle API errors
            elif response.status_code != 200:
                print(f"\nError {response.status_code} for token {token}: "
                      f"{response.text}\n")
                metrics['api_errors'] += 1
                break

            # Parse response data
            try:
                data = response.json().get("data", {}).get("candles", [])
            except Exception as e:
                print(f"JSON parsing error for token {token}: {e}")
                print(f"Raw response: {response.text}")
                metrics['json_errors'] += 1
                break

            # Convert to DataFrame and append
            temp_df = pd.DataFrame(data, columns=["Date", "Open", "High", 
                                                "Low", "Close", "Volume"])
            if not temp_df.empty:
                df = pd.concat([df, temp_df], ignore_index=True)

            # Move to next period
            start_iter = period_end + timedelta(days=1)

        # Save or append data if sufficient
        if len(df) > 0:
            if os.path.exists(filename) and file_start_date > START_DATE:
                # Append to existing file
                df.to_csv(filename, mode='a', header=False, index=False)
                print(f"Appended {len(df)} rows to {filename}")
            else:
                # Create new file
                df.to_csv(filename, index=False)
                print(f"Saved {filename} with {len(df)} rows, "
                      f"starting from {df.iloc[0, 0][:10]}")
            metrics['successfully_fetched'] += 1

            # Batch processing delay
            if metrics['successfully_fetched'] % 10 == 0:
                print(f"\nFetched {metrics['successfully_fetched']} files, sleeping for 3 seconds...\n")
                time.sleep(3)

        elif file_start_date == START_DATE:
            # Only log insufficient data for new files
            print(f"Skipping {filename}: Insufficient data, "
                  f"got {len(df)} rows.")
            metrics['insufficient_data'] += 1

        time.sleep(1)  # Rate limit protection between symbols

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
