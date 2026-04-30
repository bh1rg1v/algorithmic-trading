"""Fundamentals data fetcher from Screener.in."""
import os
import time

import pandas as pd
import requests
from bs4 import BeautifulSoup


def fetch_fundamentals_data(symbol, file_number, skip_existing=True, stats=None):
    """Fetch fundamentals data from Screener.in."""
    if stats is None:
        stats = {}
    
    output_dir = os.path.join("data", "storage", "raw", "fundamentals")
    os.makedirs(output_dir, exist_ok=True)
    
    filename = f"{file_number:04d}_{symbol}.csv"
    filepath = os.path.join(output_dir, filename)
    
    if skip_existing and os.path.exists(filepath):
        print(f"Skipping {symbol} - file already exists")
        stats['skipped'] = stats.get('skipped', 0) + 1
        return False
    
    url = f"https://www.screener.in/company/{symbol}/consolidated/"
    headers = {"User-Agent": "Mozilla/5.0"}

    rate_limited = False
    for attempt in range(2):
        response = requests.get(url, headers=headers)

        print(response)

        if response.status_code == 200:
            soup = BeautifulSoup(response.content, "html.parser")
            print(f"Page fetched successfully for {symbol}!", end = " ")
            break
        elif response.status_code == 429:
            print(f"Rate limited for {symbol}, waiting 30 seconds...")
            rate_limited = True
            time.sleep(30)
            continue
        else:
            print(f"Failed to fetch page for {symbol}:", response.status_code)
            stats['failed'] = stats.get('failed', 0) + 1
            return False
    else:
        print(f"Failed to fetch {symbol} after retries")
        stats['failed'] = stats.get('failed', 0) + 1
        return False

    if rate_limited:
        stats['rate_limited'] = stats.get('rate_limited', 0) + 1

    tables = soup.find_all("table", class_="data-table")
    table_names = [
        "Quarterly Results",
        "Profit & Loss", 
        "Balance Sheet",
        "Cash Flows",
        "Ratios",
        "Shareholding Pattern - Quarterly",
        "Shareholding Pattern - Yearly"
    ]
    
    all_rows = []
    for table_idx, table in enumerate(tables):
        
        table_name = table_names[table_idx] if table_idx < len(table_names) else f"TABLE_{table_idx + 1}"
        all_rows.append([table_name, "", "", ""])
        
        headers = [th.text.strip() for th in table.find("thead").find_all("th")]
        all_rows.append(headers)
        
        for row in table.find("tbody").find_all("tr"):
            cols = [td.text.strip() for td in row.find_all("td")]
            all_rows.append(cols)
        
        all_rows.append(["", "", "", ""])
    
    if all_rows:
        df = pd.DataFrame(all_rows)
        df.to_csv(filepath, index=False, header=False)
        print(f"Saved {symbol} data to {filepath}")
        stats['fetched'] = stats.get('fetched', 0) + 1
        return True
    
    stats['failed'] = stats.get('failed', 0) + 1
    return False


def fetch_new_data():
    """Fetch data skipping existing files."""
    tokens_path = os.path.join("data", "storage", "tokens.csv")
    stats = {'fetched': 0, 'skipped': 0, 'rate_limited': 0, 'failed': 0}
    
    try:
        tokens_df = pd.read_csv(tokens_path)
        symbols = tokens_df["SYMBOL"].dropna().unique()
        
        for idx, symbol in enumerate(symbols, 1):
            fetch_fundamentals_data(symbol.strip(), idx, skip_existing=True, stats=stats)
            
            if stats['fetched'] % 10 == 0 and stats['fetched'] > 0:
                print(f"Fetched {stats['fetched']} files, waiting 5 seconds...")
                time.sleep(5)
        
        print("\n=== SUMMARY ===")
        print(f"Total symbols processed: {len(symbols)}")
        print(f"Files fetched: {stats['fetched']}")
        print(f"Files skipped: {stats['skipped']}")
        print(f"Rate limited: {stats['rate_limited']}")
        print(f"Failed to fetch: {stats['failed']}")
            
    except FileNotFoundError:
        print(f"File not found: {tokens_path}")
    except KeyError:
        print("Column 'SYMBOL' not found in tokens.csv")


def update_all_data():
    """Fetch all data including existing files."""
    tokens_path = os.path.join("data", "storage", "tokens.csv")
    stats = {'fetched': 0, 'skipped': 0, 'rate_limited': 0, 'failed': 0}
    
    try:
        tokens_df = pd.read_csv(tokens_path)
        symbols = tokens_df["SYMBOL"].dropna().unique()
        
        for idx, symbol in enumerate(symbols, 1):
            fetch_fundamentals_data(symbol.strip(), idx, skip_existing=False, stats=stats)
            
            if stats['fetched'] % 10 == 0 and stats['fetched'] > 0:
                print(f"Fetched {stats['fetched']} files, waiting 5 seconds...")
                time.sleep(5)
        
        print("\n=== SUMMARY ===")
        print(f"Total symbols processed: {len(symbols)}")
        print(f"Files fetched: {stats['fetched']}")
        print(f"Files skipped: {stats['skipped']}")
        print(f"Rate limited: {stats['rate_limited']}")
        print(f"Failed to fetch: {stats['failed']}")
            
    except FileNotFoundError:
        print(f"File not found: {tokens_path}")
    except KeyError:
        print("Column 'SYMBOL' not found in tokens.csv")


def main():
    """Main function with user choice."""
    print("Choose an option:")
    print("1. Fetch new data (skip existing files)")
    print("2. Update all data (fetch everything)")
    
    choice = input("Enter your choice (1 or 2): ").strip()
    
    while True:
        if choice == "1":
            fetch_new_data()
            break
        elif choice == "2":
            update_all_data()
            break
        else:
            print("Invalid choice. Please select 1 or 2.")


if __name__ == "__main__":
    main()
