"""
Fundamentals data fetcher from Screener.in.
Saves each table into separate CSV files.
"""

import os
import time

import pandas as pd
import requests
from bs4 import BeautifulSoup


LIMIT = 5000


def clean_filename(name):
    """Convert table name into safe filename."""

    return (
        name.lower()
        .replace(" ", "_")
        .replace("&", "and")
        .replace("-", "_")
    )


def fetch_fundamentals_data(
    name,
    symbol,
    file_number,
    skip_existing=True,
    stats=None
):
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
        f"{name}"
    )

    os.makedirs(output_dir, exist_ok=True)

    # ======================================================================
    # REQUIRED FILES
    # ======================================================================

    required_files = [
        "quarterly_results.csv",
        "profit_and_loss.csv",
        "balance_sheet.csv",
        "cash_flows.csv",
        "ratios.csv",
        "shareholding_pattern_quarterly.csv",
        "shareholding_pattern_yearly.csv",
    ]

    all_files_exist = all(
        os.path.exists(os.path.join(output_dir, file))
        for file in required_files
    )

    # ======================================================================
    # SKIP IF DATA ALREADY EXISTS
    # ======================================================================

    if skip_existing and all_files_exist:

        print(f"Skipping {symbol} - data already exists")

        stats["skipped"] = stats.get("skipped", 0) + 1

        return True

    # ======================================================================
    # FETCH PAGE
    # ======================================================================

    url = f"https://www.screener.in/company/{symbol}/"

    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    rate_limited = False

    for attempt in range(2):

        print(f"Fetching data for {symbol}...")

        response = requests.get(
            url,
            headers=headers
        )

        if response.status_code == 200:

            soup = BeautifulSoup(
                response.content,
                "html.parser"
            )

            break

        elif response.status_code == 429:

            print(
                f"Rate limited for {symbol}, "
                f"waiting 30 seconds..."
            )

            rate_limited = True

            time.sleep(30)

            continue

        else:

            print(
                f"Failed to fetch page for "
                f"{symbol}: {response.status_code}"
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

        stats["rate_limited"] = (
            stats.get("rate_limited", 0) + 1
        )

    # ======================================================================
    # FIND TABLES
    # ======================================================================

    tables = soup.find_all(
        "table",
        class_="data-table"
    )

    # ======================================================================
    # TABLE NAME MAPPING
    # ======================================================================

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

        # ==================================================================
        # SKIP UNWANTED TABLES
        # ==================================================================

        if table_idx not in table_names:

            continue

        table_name = table_names[table_idx]

        filename = clean_filename(table_name) + ".csv"

        filepath = os.path.join(
            output_dir,
            filename
        )

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
                    for td in row.find_all(
                        ["td", "th"]
                    )
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

            # ==============================================================
            # NORMALIZE HEADERS
            # ==============================================================

            headers_row += (
                [""] *
                (max_cols - len(headers_row))
            )

            # ==============================================================
            # NORMALIZE ROWS
            # ==============================================================

            normalized_rows = []

            for row in data_rows:

                row += (
                    [""] *
                    (max_cols - len(row))
                )

                normalized_rows.append(row)

            # ==============================================================
            # CREATE DATAFRAME
            # ==============================================================

            df = pd.DataFrame(
                normalized_rows,
                columns=headers_row
            )

            # ==============================================================
            # SAVE CSV
            # ==============================================================

            df.to_csv(
                filepath,
                index=False
            )

            saved_files += 1

        else:

            print(
                f"No data found in "
                f"{table_name}"
            )

    # ======================================================================
    # FINAL STATUS
    # ======================================================================

    if saved_files > 0:

        stats["fetched"] = (
            stats.get("fetched", 0) + 1
        )

        return True

    stats["failed"] = (
        stats.get("failed", 0) + 1
    )

    print(f"FAILED: No tables saved for {symbol}")

    return False


def fetch_data(skip_existing=True):
    """Fetch fundamentals data."""

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

        # ==================================================================
        # READ TOKENS CSV
        # ==================================================================

        tokens_df = pd.read_csv(tokens_path)

        # ==================================================================
        # CREATE SYMBOL -> SHOONYA TOKEN MAP
        # ==================================================================

        tickers = dict(
            zip(
                tokens_df["SYMBOL"]
                .astype(str)
                .str.strip(),

                tokens_df["SHOONYA_TOKEN"]
                .astype(str)
                .str.strip()
            )
        )

        # ==================================================================
        # GET SYMBOLS
        # ==================================================================

        symbols = (
            tokens_df["SYMBOL"]
            .dropna()
            .astype(str)
            .str.strip()
            .unique()
        )

        symbols = symbols[:LIMIT]

        total_symbols = len(symbols)

        # ==================================================================
        # PROCESS SYMBOLS
        # ==================================================================

        for idx, symbol in enumerate(symbols, 1):

            # ==============================================================
            # STOCK SEPARATOR
            # ==============================================================

            print("\n" + "=" * 100)

            print(
                f"[{idx}/{total_symbols}] "
                f"Processing {symbol}"
            )

            print("=" * 100)

            # ==============================================================
            # FIRST ATTEMPT USING SYMBOL
            # ==============================================================

            isFetched = fetch_fundamentals_data(
                symbol,
                symbol,
                idx,
                skip_existing=skip_existing,
                stats=stats,
            )

            # ==============================================================
            # RETRY USING SHOONYA TOKEN
            # ==============================================================

            if not isFetched:

                ticker_id = tickers.get(symbol)

                if ticker_id:

                    print(
                        f"[RETRY] "
                        f"{symbol} -> {ticker_id}"
                    )

                    new = fetch_fundamentals_data(
                        symbol,
                        ticker_id,
                        idx,
                        skip_existing=skip_existing,
                        stats=stats
                    )

                    isFetched = isFetched or new

                else:

                    print(
                        f"[ERROR] "
                        f"No ticker ID "
                        f"available for {symbol}"
                    )

            # ==============================================================
            # STATUS
            # ==============================================================

            if isFetched:

                print(f"[SUCCESS] {symbol}")

            else:

                print(f"[FAILED] {symbol}")

            # ==============================================================
            # DELAY
            # ==============================================================

            if (
                stats["fetched"] % 10 == 0 and
                stats["fetched"] > 0
            ):

                print(
                    f"\nFetched "
                    f"{stats['fetched']} companies, "
                    f"waiting 0 second..."
                )

                time.sleep(0)

        # ==================================================================
        # SUMMARY
        # ==================================================================

        print("\n" + "=" * 100)

        print("SUMMARY")

        print("=" * 100)

        print(
            f"Total symbols processed: "
            f"{len(symbols)}"
        )

        print(
            f"Files fetched: "
            f"{stats['fetched']}"
        )

        print(
            f"Files skipped: "
            f"{stats['skipped']}"
        )

        print(
            f"Rate limited: "
            f"{stats['rate_limited']}"
        )

        print(
            f"Failed to fetch: "
            f"{stats['failed']}"
        )

    except FileNotFoundError:

        print(f"File not found: {tokens_path}")

    except KeyError:

        print(
            "Column 'SYMBOL' "
            "not found in tokens.csv"
        )


def main():
    """Main function."""

    print("Choose an option:")
    print("1. Fetch new data (skip existing files)")
    print("2. Update all data (fetch everything)")

    choice = input(
        "Enter your choice (1 or 2): "
    ).strip()

    while True:

        if choice == "1":

            fetch_data(skip_existing=True)

            break

        elif choice == "2":

            fetch_data(skip_existing=False)

            break

        else:

            print(
                "Invalid choice. "
                "Please select 1 or 2."
            )


if __name__ == "__main__":
    main()