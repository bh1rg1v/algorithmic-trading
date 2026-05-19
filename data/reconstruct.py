import os
import re
import pandas as pd
from collections import defaultdict

# ============================================================
# CONFIG
# ============================================================

INPUT_ROOT = r"D:\github\datasets\kaggle\archive - nifty & banknifty 2020 - 2024 options data\nifty_data\nifty_options"

OUTPUT_ROOT = r"D:\github\datasets\reconstructed_nifty_options"

# LIMIT NUMBER OF FILES TO READ
FILE_LIMIT = 25000000000

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

# SORT FILES
all_csv_files.sort()

print("\n================================================")
print(f"TOTAL CSV FILES FOUND: {len(all_csv_files)}")
print("================================================")

# ============================================================
# LIMIT FILES
# ============================================================

all_csv_files = all_csv_files[:FILE_LIMIT]

print(f"\nPROCESSING FIRST {len(all_csv_files)} FILES")

# ============================================================
# STORE DATA
# ============================================================

contract_data = defaultdict(list)

# ============================================================
# READ ALL FILES
# ============================================================

for idx, file_path in enumerate(all_csv_files, 1):

    print("\n------------------------------------------------")
    print(f"[{idx}/{len(all_csv_files)}]")
    print(f"READING FILE:")
    print(file_path)
    print("------------------------------------------------")

    try:

        df = pd.read_csv(file_path)

        print(f"ROWS READ: {len(df)}")

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

        print("MISSING COLUMNS:")
        print(missing_columns)

        continue

    print("ALL REQUIRED COLUMNS FOUND")

    # ========================================================
    # CLEAN DATE/TIME
    # ========================================================

    df["date"] = df["date"].astype(str).str.strip()
    df["time"] = df["time"].astype(str).str.strip()

    # ========================================================
    # CREATE TIMESTAMP
    # ========================================================

    print("\nCREATING TIMESTAMP COLUMN...")

    df["timestamp"] = pd.to_datetime(
        df["date"] + " " + df["time"],
        dayfirst=True,
        errors="coerce"
    )

    print("\nTIMESTAMP SAMPLE:")

    print(
        df[
            [
                "date",
                "time",
                "timestamp"
            ]
        ].head()
    )

    invalid_timestamp_count = df["timestamp"].isna().sum()

    print(f"\nINVALID TIMESTAMPS: {invalid_timestamp_count}")

    # ========================================================
    # REMOVE INVALID TIMESTAMPS
    # ========================================================

    df = df[df["timestamp"].notna()]

    print(f"VALID ROWS AFTER TIMESTAMP FILTER: {len(df)}")

    if len(df) == 0:

        print("NO VALID ROWS LEFT")
        continue

    # ========================================================
    # LOCALIZE TIMEZONE
    # ========================================================

    try:

        df["timestamp"] = (
            df["timestamp"]
            .dt.tz_localize("Asia/Kolkata")
        )

        print("TIMEZONE LOCALIZATION SUCCESS")

    except Exception as e:

        print("TIMEZONE LOCALIZATION FAILED")
        print(e)

        continue

    # ========================================================
    # GROUP BY SYMBOL
    # ========================================================

    print("\nGROUPING BY SYMBOL...")

    grouped = df.groupby("symbol")

    symbol_count = 0

    for symbol, sdf in grouped:

        symbol_count += 1

        parsed = parse_symbol(symbol)

        if parsed is None:

            print(f"FAILED TO PARSE SYMBOL: {symbol}")

            continue

        expiry_folder = get_expiry_folder(parsed)

        output_file = generate_output_filename(parsed)

        print(
            f"SYMBOL: {symbol} | "
            f"ROWS: {len(sdf)} | "
            f"OUTPUT: {expiry_folder}/{output_file}"
        )

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

    print(f"\nTOTAL SYMBOLS PROCESSED: {symbol_count}")

# ============================================================
# SAVE RECONSTRUCTED FILES
# ============================================================

print("\n================================================")
print("SAVING RECONSTRUCTED FILES")
print("================================================")

total_contracts = len(contract_data)

print(f"\nTOTAL CONTRACT FILES: {total_contracts}")

if total_contracts == 0:

    print("\nNO CONTRACT DATA FOUND")
    print("CHECK SYMBOL PARSING")
    exit()

for idx, ((expiry_folder, output_file), dfs) in enumerate(contract_data.items(), 1):

    print("\n------------------------------------------------")
    print(f"[{idx}/{total_contracts}]")
    print(f"SAVING:")
    print(f"{expiry_folder}/{output_file}")
    print("------------------------------------------------")

    try:

        print(f"NUMBER OF DATAFRAMES: {len(dfs)}")

        # ====================================================
        # MERGE DATAFRAMES
        # ====================================================

        final_df = pd.concat(dfs, ignore_index=True)

        print(f"ROWS AFTER CONCAT: {len(final_df)}")

        # ====================================================
        # SORT
        # ====================================================

        final_df = final_df.sort_values("timestamp")

        print("SORT SUCCESS")

        # ====================================================
        # REMOVE EXACT DUPLICATES
        # ====================================================

        before_duplicates = len(final_df)

        final_df = final_df.drop_duplicates()

        after_duplicates = len(final_df)

        print(
            f"DUPLICATES REMOVED: "
            f"{before_duplicates - after_duplicates}"
        )

        print(f"FINAL ROWS: {after_duplicates}")

        # ====================================================
        # CONVERT TIMESTAMP
        # ====================================================

        final_df["timestamp"] = final_df["timestamp"].astype(str)

        # ====================================================
        # CREATE OUTPUT FOLDER
        # ====================================================

        expiry_output_path = os.path.join(
            OUTPUT_ROOT,
            expiry_folder
        )

        os.makedirs(expiry_output_path, exist_ok=True)

        print(f"OUTPUT FOLDER CREATED")

        # ====================================================
        # OUTPUT PATH
        # ====================================================

        output_path = os.path.join(
            expiry_output_path,
            output_file
        )

        print(f"OUTPUT PATH:")
        print(output_path)

        # ====================================================
        # SAVE CSV
        # ====================================================

        final_df.to_csv(output_path, index=False)

        print("CSV SAVE SUCCESS")

        # ====================================================
        # VERIFY SAVE
        # ====================================================

        if os.path.exists(output_path):

            saved_df = pd.read_csv(output_path)

            print(f"VERIFIED SAVED ROWS: {len(saved_df)}")

        else:

            print("FILE NOT FOUND AFTER SAVE")

    except Exception as e:

        print("FAILED TO SAVE FILE")
        print(e)

print("\n================================================")
print("DONE")
print("================================================")