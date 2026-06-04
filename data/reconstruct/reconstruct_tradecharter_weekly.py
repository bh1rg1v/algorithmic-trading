import os
import re
import sys
import pandas as pd
from pathlib import Path

# ============================================================
# INPUT / OUTPUT PATHS
# ============================================================

INPUT_FOLDER = r"D:\github\algorithmic-trading\data\reconstruct\tradecharter\banknifty\weekly"

OUTPUT_FOLDER = (
    r"D:\github\algorithmic-trading\data\reconstructed"
    r"\banknifty\tradecharter\weekly"
)

# Optional processing range
START = 0
LIMIT = 18000

# ============================================================
# GLOBAL STATS
# ============================================================

FILES_SAVED = 0
FILES_SKIPPED = 0
FILES_FAILED = 0

# ============================================================
# FILE NAME PARSER
# ============================================================

isBankNifty = True


# ============================================================
# FILE NAME PARSER
# ============================================================

isBankNifty = True


def parse_contract_name(filename):
    """
    Parses option contract filename and extracts:
    - strike
    - option type

    Supported formats:
    1) CE 6200
    2) PE 6200
    3) BANKNIFTY35000CE
    4) BANKNIFTY35000PE
    5) BANKNIFTYWK35000CE
    6) BANKNIFTY25JUN2035000CE
    7) BANKNIFTY18APR24500PE

    Also validates that ONLY ONE regex pattern matches.
    If multiple patterns match same filename:
    - print stats
    - terminate program

    Time Complexity: O(1)
    Space Complexity: O(1)
    """

    name = Path(filename).stem.upper()

    # --------------------------------------------------------
    # STRIKE DIGIT RULE
    # --------------------------------------------------------

    strike_pattern = r"\d{5}" if isBankNifty else r"\d+"

    # --------------------------------------------------------
    # ALL PATTERNS
    # --------------------------------------------------------

    patterns = [

        # ----------------------------------------------------
        # FORMAT 1/2
        # CE 6200
        # PE 6200
        # ----------------------------------------------------

        (
            "Format 1/2",

            rf"^(CE|PE)\s+(\d+)$",

            lambda m: (
                m.group(2),   # strike
                m.group(1),   # option_type
            )
        ),

        # ----------------------------------------------------
        # FORMAT 3/4
        # BANKNIFTY35000CE
        # ----------------------------------------------------

        (
            "Format 3/4",

            rf"^BANKNIFTY({strike_pattern})(CE|PE)$",

            lambda m: (
                m.group(1),
                m.group(2),
            )
        ),

        # ----------------------------------------------------
        # FORMAT 3B
        # BANKNIFTYWK35000CE
        # ----------------------------------------------------

        (
            "Format 3B",

            rf"^BANKNIFTYWK({strike_pattern})(CE|PE)$",

            lambda m: (
                m.group(1),
                m.group(2),
            )
        ),

        # ----------------------------------------------------
        # FORMAT 5
        # BANKNIFTY25JUN2035000CE
        # ----------------------------------------------------

        (
            "Format 5",

            rf"^BANKNIFTY\d{{1,2}}[A-Z]{{3}}\d{{2}}"
            rf"({strike_pattern})(CE|PE)$",

            lambda m: (
                m.group(1),
                m.group(2),
            )
        ),

        # ----------------------------------------------------
        # FORMAT 6
        # BANKNIFTY18APR24500PE
        #
        # 18APR -> expiry portion
        # 24500 -> strike
        # PE    -> option type
        # ----------------------------------------------------

        (
            "Format 6",

            rf"^BANKNIFTY\d{{2}}[A-Z]{{3}}"
            rf"({strike_pattern})(CE|PE)$",

            lambda m: (
                m.group(1),
                m.group(2),
            )
        ),
    ]

    # --------------------------------------------------------
    # CHECK ALL PATTERNS
    # --------------------------------------------------------

    matches_found = []

    for format_name, pattern, extractor in patterns:

        match = re.match(pattern, name)

        if match:

            strike, option_type = extractor(match)

            matches_found.append(
                (
                    format_name,
                    strike,
                    option_type,
                    pattern,
                )
            )

    # --------------------------------------------------------
    # MULTIPLE MATCH CHECK
    # --------------------------------------------------------

    if len(matches_found) > 1:

        print("\n" + "=" * 60)
        print("[ERROR] MULTIPLE REGEX MATCHES FOUND")
        print("=" * 60)

        print(f"Filename: {filename}\n")

        for idx, (
            format_name,
            strike,
            option_type,
            pattern,
        ) in enumerate(matches_found, start=1):

            print(f"[MATCH {idx}]")
            print(f"Format      : {format_name}")
            print(f"Strike      : {strike}")
            print(f"Option Type : {option_type}")
            print(f"Regex       : {pattern}")
            print()

        print_stats()

        terminate_program()

    # --------------------------------------------------------
    # SINGLE MATCH
    # --------------------------------------------------------

    if len(matches_found) == 1:

        (
            format_name,
            strike,
            option_type,
            pattern,
        ) = matches_found[0]

        # print(format_name)

        return strike, option_type

    # --------------------------------------------------------
    # NO MATCH
    # --------------------------------------------------------

    return None, None

# ============================================================
# DATE HELPERS
# ============================================================


def format_expiry_parts(expiry_date):

    expiry_folder = expiry_date.strftime("%Y-%m-%d")
    expiry_month = expiry_date.strftime("%b").upper()
    expiry_year = expiry_date.strftime("%y")

    return expiry_folder, expiry_month, expiry_year

# ============================================================
# PRINT STATS
# ============================================================


def print_stats():

    print("\n" + "=" * 60)
    print("STATS")
    print("=" * 60)

    print(f"Files Saved   : {FILES_SAVED}")
    print(f"Files Skipped : {FILES_SKIPPED}")
    print(f"Files Failed  : {FILES_FAILED}")

    print("=" * 60 + "\n")

# ============================================================
# TERMINATE PROGRAM
# ============================================================


def terminate_program():

    print_stats()

    print("\nPROGRAM TERMINATED\n")

    sys.exit(1)

# ============================================================
# PROCESS SINGLE FILE
# ============================================================


def process_file(file_path):

    global FILES_SAVED
    global FILES_SKIPPED
    global FILES_FAILED

    try:

        # ----------------------------------------------------
        # PARSE FILE NAME
        # ----------------------------------------------------

        strike, option_type = parse_contract_name(file_path.name)

        if strike is None or option_type is None:

            FILES_SKIPPED += 1

            print(f"\n[SKIPPED] Could not parse filename:")
            print(file_path)

            terminate_program()

        # ----------------------------------------------------
        # READ FILE
        # ----------------------------------------------------

        df = pd.read_csv(
            file_path,
            header=None
        )

        # ----------------------------------------------------
        # EMPTY FILE CHECK
        # ----------------------------------------------------

        if df.empty:

            FILES_SKIPPED += 1

            print(f"\n[SKIPPED] Empty file:")
            print(file_path)

            terminate_program()

        # ----------------------------------------------------
        # HANDLE COLUMN COUNT
        # ----------------------------------------------------

        if len(df.columns) == 8:

            df.columns = [
                "contract",
                "date",
                "time",
                "open",
                "high",
                "low",
                "close",
                "volume",
            ]

        elif len(df.columns) == 9:

            df.columns = [
                "contract",
                "date",
                "time",
                "open",
                "high",
                "low",
                "close",
                "volume",
                "oi",
            ]

        else:

            FILES_SKIPPED += 1

            print(f"\n[SKIPPED] Unexpected column count:")
            print(file_path)

            print(f"Column count found: {len(df.columns)}")

            terminate_program()

        # ----------------------------------------------------
        # KEEP REQUIRED COLUMNS
        # ----------------------------------------------------

        df = df[
            [
                "date",
                "time",
                "open",
                "high",
                "low",
                "close",
                "volume",
            ]
        ]

        # ----------------------------------------------------
        # HANDLE MULTIPLE DATE FORMATS
        # ----------------------------------------------------

        parsed_dates = pd.Series(pd.NaT, index=df.index)

        # FORMAT 1 -> DD/MM/YYYY
        mask = parsed_dates.isna()

        parsed_dates.loc[mask] = pd.to_datetime(
            df.loc[mask, "date"],
            format="%d/%m/%Y",
            errors="coerce"
        )

        # FORMAT 2 -> YYYY/MM/DD
        mask = parsed_dates.isna()

        parsed_dates.loc[mask] = pd.to_datetime(
            df.loc[mask, "date"],
            format="%Y/%m/%d",
            errors="coerce"
        )

        # FORMAT 3 -> DD-MM-YYYY
        mask = parsed_dates.isna()

        parsed_dates.loc[mask] = pd.to_datetime(
            df.loc[mask, "date"],
            format="%d-%m-%Y",
            errors="coerce"
        )

        # ----------------------------------------------------
        # INVALID DATE CHECK
        # ----------------------------------------------------

        if parsed_dates.isna().all():

            FILES_SKIPPED += 1

            print(f"\n[SKIPPED] Invalid dates:")
            print(file_path)

            terminate_program()

        # ----------------------------------------------------
        # NORMALIZE DATE FORMAT
        # ----------------------------------------------------

        df["date"] = parsed_dates.dt.strftime("%Y-%m-%d")

        # ----------------------------------------------------
        # GET EXPIRY FROM FOLDER NAME
        # ----------------------------------------------------

        relative_parts = file_path.relative_to(INPUT_FOLDER).parts

        year_folder = relative_parts[0]

        if len(relative_parts) < 4:

            FILES_SKIPPED += 1

            print(f"\n[SKIPPED] Invalid folder structure:")
            print(file_path)

            terminate_program()

        expiry_folder = relative_parts[2]

        try:

            expiry_date = pd.to_datetime(
                expiry_folder,
                format="%Y-%m-%d"
            )

        except Exception:

            FILES_SKIPPED += 1

            print(f"\n[SKIPPED] Invalid expiry folder:")
            print(file_path)

            print(f"Expiry folder found: {expiry_folder}")

            terminate_program()

        expiry_folder, expiry_month, expiry_year = (
            format_expiry_parts(expiry_date)
        )

        expiry_date_str = expiry_date.strftime("%d")

        # ----------------------------------------------------
        # OUTPUT FILE NAME
        # ----------------------------------------------------

        output_filename = (
            f"BANKNIFTY_{strike}_{option_type}_"
            f"{expiry_date_str}_{expiry_month}_{expiry_year}.csv"
        )

        # ----------------------------------------------------
        # OUTPUT DIRECTORY
        # ----------------------------------------------------

        output_dir = os.path.join(
            OUTPUT_FOLDER,
            year_folder,
            expiry_folder,
        )

        os.makedirs(output_dir, exist_ok=True)

        output_path = os.path.join(
            output_dir,
            output_filename
        )

        # ----------------------------------------------------
        # SAVE FILE
        # ----------------------------------------------------

        df.to_csv(output_path, index=False)

        FILES_SAVED += 1

        print(f"[SAVED] {output_path}")

    except Exception as e:

        FILES_FAILED += 1

        print(f"\n[ERROR] Failed processing file:")
        print(file_path)

        print("\nException:")
        print(e)

        terminate_program()

# ============================================================
# SCAN ALL FILES
# ============================================================


def scan_and_process():

    input_path = Path(INPUT_FOLDER)

    all_files = []

    # --------------------------------------------------------
    # SCAN CSV + TXT FILES
    # --------------------------------------------------------

    for ext in ["*.csv", "*.txt"]:
        all_files.extend(input_path.rglob(ext))

    all_files = sorted(all_files)[START:LIMIT]

    print("\n" + "=" * 60)
    print(f"TOTAL FILES FOUND : {len(all_files)}")
    print("=" * 60)

    # --------------------------------------------------------
    # PROCESS FILES
    # --------------------------------------------------------

    for idx, file_path in enumerate(all_files, start=1):

        print("\n" + "-" * 60)
        print(f"[{idx}/{len(all_files)}]")
        print(file_path)
        print("-" * 60)

        process_file(file_path)

        print_stats()

    # --------------------------------------------------------
    # FINAL SUMMARY
    # --------------------------------------------------------

    print("\nPROCESSING COMPLETED")

    print_stats()

# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":

    scan_and_process()

"""

Good morning sir, I have already given you some feedback,
I have got another point to add

I think, adding elo scoring algorithm would be great,
it would be a bit complex,
but still it will be the best measure for evaluating the users
beyond the vibeathons at a higher level

I think rather than taking averages or considering the score
of a single test for global scoreboard, it would be better to evaluate
based on elo score

"""