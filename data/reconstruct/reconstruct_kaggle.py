import os
import re
import pandas as pd
from collections import defaultdict

# ============================================================
# CONFIG
# ============================================================

INPUT_ROOT = r"D:\github\datasets\kaggle\archive - nifty & banknifty 2020 - 2024 options data\nifty_data\nifty_options"

OUTPUT_ROOT = r"D:\github\algorithmic-trading\data\reconstructed\nifty\kaggle"

# LIMIT NUMBER OF FILES
START = 0
LIMIT = 252

os.makedirs(OUTPUT_ROOT, exist_ok=True)

# ============================================================
# MONTH MAP
# ============================================================

MONTH_MAP = {
    "JAN": "01",
    "FEB": "02",
    "MAR": "03",
    "APR": "04",
    "MAY": "05",
    "JUN": "06",
    "JUL": "07",
    "AUG": "08",
    "SEP": "09",
    "OCT": "10",
    "NOV": "11",
    "DEC": "12",
}

# ============================================================
# SYMBOL PARSER
# ============================================================

def parse_symbol(symbol):

    pattern = r"^NIFTY(\d{2})([A-Z]{3})(\d{2})(\d+)(CE|PE)$"

    match = re.match(pattern, symbol)

    if not match:
        return None

    expiry_day = match.group(1)
    expiry_month = match.group(2)
    expiry_year = match.group(3)
    strike = match.group(4)
    option_type = match.group(5)

    return {
        "expiry_day": expiry_day,
        "expiry_month": expiry_month,
        "expiry_year": expiry_year,
        "strike": strike,
        "option_type": option_type,
    }

# ============================================================
# EXPIRY FOLDER NAME
# ============================================================

def get_expiry_folder(parsed):

    year = f"20{parsed['expiry_year']}"
    month = MONTH_MAP[parsed["expiry_month"]]
    day = parsed["expiry_day"]

    return f"{year}-{month}-{day}"

# ============================================================
# OUTPUT FILE NAME
# ============================================================

def generate_output_filename(parsed):

    return (
        f"NIFTY_"
        f"{parsed['strike']}_"
        f"{parsed['option_type']}_"
        f"{parsed['expiry_day']}_"
        f"{parsed['expiry_month']}_"
        f"{parsed['expiry_year']}.csv"
    )

# ============================================================
# FIND ALL CSV FILES
# ============================================================

all_csv_files = []

for root, dirs, files in os.walk(INPUT_ROOT):

    for file in files:

        if file.endswith(".csv"):

            full_path = os.path.join(root, file)

            all_csv_files.append(full_path)

# all_csv_files.sort()

print("\n================================================")
print(f"TOTAL CSV FILES FOUND: {len(all_csv_files)}")
print("================================================")

# ============================================================
# LIMIT FILES
# ============================================================

all_csv_files = all_csv_files[START:START + LIMIT]

print(f"\nPROCESSING FILES: {len(all_csv_files)}")

# ============================================================
# STORE DATA
# ============================================================

contract_data = defaultdict(list)

# ============================================================
# READ FILES
# ============================================================

for idx, file_path in enumerate(all_csv_files, 1):

    print(f"\n[PROCESSING FILE {idx}/{len(all_csv_files)}] {os.path.basename(file_path)}")

    try:

        df = pd.read_csv(file_path)

        print(f"Rows: {len(df)}")

    except Exception as e:

        print("FAILED TO READ FILE")
        print(e)

        continue

    # ========================================================
    # VALIDATE COLUMNS
    # ========================================================

    required_columns = [
        "date",
        "time",
        "symbol",
        "open",
        "high",
        "low",
        "close",
        "oi",
        "volume",
    ]

    missing_columns = [
        col for col in required_columns
        if col not in df.columns
    ]

    if len(missing_columns) > 0:

        print(f"Missing columns: {missing_columns}")

        continue

    # ========================================================
    # CLEAN DATE/TIME
    # ========================================================

    df["date"] = df["date"].astype(str).str.strip()
    df["time"] = df["time"].astype(str).str.strip()

    # ========================================================
    # CREATE TIMESTAMP
    # ========================================================

    df["timestamp"] = pd.to_datetime(
        df["date"] + " " + df["time"],
        dayfirst=True,
        errors="coerce"
    )

    invalid_timestamp_count = df["timestamp"].isna().sum()

    if invalid_timestamp_count > 0:

        print(f"Invalid timestamps: {invalid_timestamp_count}")

    # ========================================================
    # REMOVE INVALID TIMESTAMPS
    # ========================================================

    df = df[df["timestamp"].notna()]

    print(f"Valid rows: {len(df)}")

    if len(df) == 0:

        print("NO VALID ROWS")
        continue

    # ========================================================
    # LOCALIZE TIMEZONE
    # ========================================================

    try:

        df["timestamp"] = (
            df["timestamp"]
            .dt.tz_localize("Asia/Kolkata")
        )

    except Exception as e:

        print("TIMEZONE FAILED")
        print(e)

        continue

    # ========================================================
    # GROUP SYMBOLS
    # ========================================================

    grouped = df.groupby("symbol")

    symbol_count = 0

    for symbol, sdf in grouped:

        parsed = parse_symbol(symbol)

        if parsed is None:
            continue

        symbol_count += 1

        expiry_folder = get_expiry_folder(parsed)

        output_file = generate_output_filename(parsed)

        # print(f"{symbol_count}. {symbol} ({len(sdf)} rows)")

        temp_df = sdf[
            [
                "timestamp",
                "open",
                "high",
                "low",
                "close",
                "volume",
                "oi",
            ]
        ].copy()

        contract_data[(expiry_folder, output_file)].append(temp_df)

    print(f"Symbols: {symbol_count}")

# ============================================================
# SAVE FILES
# ============================================================

print("\nSaving reconstructed files...")

total_contracts = len(contract_data)

print(f"Contracts: {total_contracts}")

if total_contracts == 0:

    print("NO CONTRACT DATA FOUND")
    exit()

for idx, ((expiry_folder, output_file), dfs) in enumerate(contract_data.items(), 1):

    print(f"\n[SAVE {idx}/{total_contracts}] {output_file}")

    try:

        # ====================================================
        # MERGE
        # ====================================================

        final_df = pd.concat(dfs, ignore_index=True)

        # print(f"Rows: {len(final_df)}")

        # ====================================================
        # SORT
        # ====================================================

        final_df = final_df.sort_values("timestamp")

        # ====================================================
        # REMOVE DUPLICATES
        # ====================================================

        before_duplicates = len(final_df)

        final_df = final_df.drop_duplicates()

        after_duplicates = len(final_df)

        duplicates_removed = (
            before_duplicates - after_duplicates
        )

        if duplicates_removed > 0:

            print(f"Duplicates removed: {duplicates_removed}")

        # print(f"Final rows: {after_duplicates}")

        # ====================================================
        # SPLIT TIMESTAMP
        # ====================================================

        final_df["date"] = (
            final_df["timestamp"]
            .dt.strftime("%d-%m-%Y")
        )

        final_df["time"] = (
            final_df["timestamp"]
            .dt.strftime("%H:%M")
        )

        # ====================================================
        # KEEP REQUIRED COLUMNS
        # ====================================================

        final_df = final_df[
            [
                "date",
                "time",
                "open",
                "high",
                "low",
                "close",
                "volume",
                "oi",
            ]
        ]

        # ====================================================
        # OUTPUT FOLDER
        # ====================================================

        expiry_output_path = os.path.join(
            OUTPUT_ROOT,
            expiry_folder
        )

        os.makedirs(expiry_output_path, exist_ok=True)

        # ====================================================
        # OUTPUT PATH
        # ====================================================

        output_path = os.path.join(
            expiry_output_path,
            output_file
        )

        # ====================================================
        # SAVE CSV
        # ====================================================

        final_df.to_csv(
            output_path,
            index=False
        )

        # print("Saved")

        # ====================================================
        # VERIFY
        # ====================================================

        if os.path.exists(output_path):

            saved_df = pd.read_csv(output_path)

            # print(f"Verified: {len(saved_df)} rows")

        else:

            print("FILE NOT FOUND")

    except Exception as e:

        print("FAILED TO SAVE FILE")
        print(e)

print("\nDone")