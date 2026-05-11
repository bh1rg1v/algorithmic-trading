"""
Fundamentals data fetcher from Screener.in.
Saves each table into separate CSV files.
"""

import os
import time

import pandas as pd
import requests
from bs4 import BeautifulSoup


def clean_filename(name):
    """Convert table name into safe filename."""

    return (
        name.lower()
        .replace(" ", "_")
        .replace("&", "and")
        .replace("-", "_")
    )


def fetch_fundamentals_data(symbol, file_number, skip_existing=True, stats=None):
    """Fetch fundamentals data from Screener.in."""

    if stats is None:
        stats = {}

    # ======================================================================
    # CREATE COMPANY FOLDER
    # ======================================================================

    output_dir = os.path.join(
        "data",
        "storage",
        "fundamentals",
        f"{symbol}"
    )

    os.makedirs(output_dir, exist_ok=True)

    # ======================================================================
    # SKIP IF DATA ALREADY EXISTS
    # ======================================================================

    if skip_existing and len(os.listdir(output_dir)) > 0:

        # print(f"Skipping {symbol} - data already exists")

        stats["skipped"] = stats.get("skipped", 0) + 1

        return False

    # ======================================================================
    # FETCH PAGE
    # ======================================================================

    url = f"https://www.screener.in/company/{symbol}/consolidated/"

    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    rate_limited = False

    for attempt in range(2):

        response = requests.get(url, headers=headers)

        print(response)

        if response.status_code == 200:

            soup = BeautifulSoup(response.content, "html.parser")

            print(f"Page fetched successfully for {symbol}!")

            break

        elif response.status_code == 429:

            print(f"Rate limited for {symbol}, waiting 30 seconds...")

            rate_limited = True

            time.sleep(30)

            continue

        else:

            print(
                f"Failed to fetch page for {symbol}:",
                response.status_code
            )

            stats["failed"] = stats.get("failed", 0) + 1

            return False

    else:

        print(f"Failed to fetch {symbol} after retries")

        stats["failed"] = stats.get("failed", 0) + 1

        return False

    # ======================================================================
    # RATE LIMIT STATS
    # ======================================================================

    if rate_limited:

        stats["rate_limited"] = stats.get("rate_limited", 0) + 1

    # ======================================================================
    # FIND TABLES
    # ======================================================================

    tables = soup.find_all("table", class_="data-table")

    # Correct mapping based on actual Screener structure
    table_names = {
        0: "Quarterly Results",
        1: "Profit & Loss",
        2: "Balance Sheet",
        3: "Cash Flows",
        4: "Ratios",
        7: "Shareholding Pattern Quarterly",
        8: "Shareholding Pattern Yearly",
    }

    # ======================================================================
    # PROCESS TABLES
    # ======================================================================

    saved_files = 0

    for table_idx, table in enumerate(tables):

        print(f"Processing table {table_idx + 1} for {symbol}")

        # Skip unwanted tables
        if table_idx not in table_names:

            print(f"Skipping table {table_idx + 1}")

            continue

        table_name = table_names[table_idx]

        filename = clean_filename(table_name) + ".csv"

        filepath = os.path.join(output_dir, filename)

        thead = table.find("thead")
        tbody = table.find("tbody")

        headers_row = []
        data_rows = []

        # ==================================================================
        # EXTRACT HEADERS
        # ==================================================================

        if thead:

            headers_row = [
                th.text.strip()
                for th in thead.find_all("th")
            ]

        # ==================================================================
        # EXTRACT ROWS
        # ==================================================================

        if tbody:

            for row in tbody.find_all("tr"):

                cols = [
                    td.text.strip()
                    for td in row.find_all(["td", "th"])
                ]

                if cols:

                    data_rows.append(cols)

        # ==================================================================
        # SAVE CSV
        # ==================================================================

        if headers_row or data_rows:

            max_cols = max(
                [len(headers_row)] +
                [len(row) for row in data_rows]
            )

            # Normalize headers
            headers_row += [""] * (max_cols - len(headers_row))

            # Normalize rows
            normalized_rows = []

            for row in data_rows:

                row += [""] * (max_cols - len(row))

                normalized_rows.append(row)

            df = pd.DataFrame(
                normalized_rows,
                columns=headers_row
            )

            df.to_csv(filepath, index=False)

            print(f"Saved: {filepath}")

            saved_files += 1

    # ======================================================================
    # FINAL STATUS
    # ======================================================================

    if saved_files > 0:

        stats["fetched"] = stats.get("fetched", 0) + 1

        print(f"Saved {saved_files} tables for {symbol}")

        return True

    stats["failed"] = stats.get("failed", 0) + 1

    return False


def fetch_new_data():
    """Fetch data skipping existing files."""

    tokens_path = os.path.join(
        "data",
        "storage",
        "tokens.csv"
    )

    stats = {
        "fetched": 0,
        "skipped": 0,
        "rate_limited": 0,
        "failed": 0,
    }

    try:

        tokens_df = pd.read_csv(tokens_path)

        symbols = tokens_df["SYMBOL"].dropna().unique()

        for idx, symbol in enumerate(symbols, 1):

            fetch_fundamentals_data(
                symbol.strip(),
                idx,
                skip_existing=True,
                stats=stats,
            )

            # Delay every 10 successful fetches
            if stats["fetched"] % 10 == 0 and stats["fetched"] > 0:

                print(
                    f"Fetched {stats['fetched']} companies, "
                    f"waiting 3 seconds..."
                )

                time.sleep(3)

        # ==================================================================
        # SUMMARY
        # ==================================================================

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

    tokens_path = os.path.join(
        "data",
        "storage",
        "tokens.csv"
    )

    stats = {
        "fetched": 0,
        "skipped": 0,
        "rate_limited": 0,
        "failed": 0,
    }

    try:

        tokens_df = pd.read_csv(tokens_path)

        symbols = tokens_df["SYMBOL"].dropna().unique()

        for idx, symbol in enumerate(symbols, 1):

            fetch_fundamentals_data(
                symbol.strip(),
                idx,
                skip_existing=False,
                stats=stats,
            )

            # Delay every 10 successful fetches
            if stats["fetched"] % 10 == 0 and stats["fetched"] > 0:

                print(
                    f"Fetched {stats['fetched']} companies, "
                    f"waiting 5 seconds..."
                )

                time.sleep(5)

        # ==================================================================
        # SUMMARY
        # ==================================================================

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
    """Main function."""

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