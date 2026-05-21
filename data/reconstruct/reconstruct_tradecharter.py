"""

input folder:  D:\github\algorithmic-trading\data\reconstruct\tradecharter\monthly

the following are the details of the input folder/data

Folder Structure:

{year}/{month}/

where year is in the range of [2014, 2021]
month in the range of [January, December]

File Name Formats:

1) CE 6200.csv / PE 6200.csv
2) CE 6200.txt / PE 6200.txt (data is comma seperated)
3) NIFTY9900CE.txt / NIFTY9900PE.txt
4) NIFTY10500CE.csv / NIFTY10500PE.csv
5) NIFTY25JUN208500PE.csv / NIFTY25JUN208500CE.csv (NIFTY{expiry_date}{expiry_month}{expiry_year}{option_type}.csv)

columns in each file: (there are no headers in the csv/txt files)

option contract name, date, time, open, high, low, close, volume

date format: dd-mm-yyyy
time format: hh:mm

output folder: D:\github\algorithmic-trading\data\reconstructed\nifty\monthly

the following are the details of the output folder/data

Folder Structure:

{year}/{month}/{expiry_folder}/

expiry_folder = YYYY-MM-DD (use the last date available in the input data for each contract)

File Name Format:

NIFTY_{STRIKE}_{option_type}_{expiry_date}_{expiry_month}_{expiry_year} (here, expiry year shoud be in YY format)

columns in the output folder:

date, time, open, high, low, close, volume

give me a python script to read that input data and save the data in output format

"""

import os
import re
import sys
import pandas as pd
from pathlib import Path

# ============================================================
# INPUT / OUTPUT PATHS
# ============================================================

INPUT_FOLDER = r"D:\\github\\algorithmic-trading\data\\reconstruct\\tradecharter\\monthly"
OUTPUT_FOLDER = r"D:\\github\\algorithmic-trading\data\\reconstructed\\nifty\\monthly"

# Optional processing limit
START = 0
LIMIT = 100000000

# ============================================================
# MONTHLY EXPIRY DATES (HARDCODED)
# ============================================================

MONTHLY_EXPIRIES = {
    (2014, "JANUARY"): "30-JAN-2014",
    (2014, "FEBRUARY"): "26-FEB-2014",
    (2014, "MARCH"): "27-MAR-2014",
    (2014, "APRIL"): "24-APR-2014",
    (2014, "MAY"): "29-MAY-2014",
    (2014, "JUNE"): "26-JUN-2014",
    (2014, "JULY"): "31-JUL-2014",
    (2014, "AUGUST"): "28-AUG-2014",
    (2014, "SEPTEMBER"): "25-SEP-2014",
    (2014, "OCTOBER"): "30-OCT-2014",
    (2014, "NOVEMBER"): "27-NOV-2014",
    (2014, "DECEMBER"): "24-DEC-2014",

    (2015, "JANUARY"): "29-JAN-2015",
    (2015, "FEBRUARY"): "26-FEB-2015",
    (2015, "MARCH"): "26-MAR-2015",
    (2015, "APRIL"): "30-APR-2015",
    (2015, "MAY"): "28-MAY-2015",
    (2015, "JUNE"): "25-JUN-2015",
    (2015, "JULY"): "30-JUL-2015",
    (2015, "AUGUST"): "27-AUG-2015",
    (2015, "SEPTEMBER"): "24-SEP-2015",
    (2015, "OCTOBER"): "29-OCT-2015",
    (2015, "NOVEMBER"): "26-NOV-2015",
    (2015, "DECEMBER"): "31-DEC-2015",

    (2016, "JANUARY"): "28-JAN-2016",
    (2016, "FEBRUARY"): "25-FEB-2016",
    (2016, "MARCH"): "31-MAR-2016",
    (2016, "APRIL"): "28-APR-2016",
    (2016, "MAY"): "26-MAY-2016",
    (2016, "JUNE"): "30-JUN-2016",
    (2016, "JULY"): "28-JUL-2016",
    (2016, "AUGUST"): "25-AUG-2016",
    (2016, "SEPTEMBER"): "29-SEP-2016",
    (2016, "OCTOBER"): "27-OCT-2016",
    (2016, "NOVEMBER"): "24-NOV-2016",
    (2016, "DECEMBER"): "29-DEC-2016",

    (2017, "JANUARY"): "25-JAN-2017",
    (2017, "FEBRUARY"): "23-FEB-2017",
    (2017, "MARCH"): "30-MAR-2017",
    (2017, "APRIL"): "27-APR-2017",
    (2017, "MAY"): "25-MAY-2017",
    (2017, "JUNE"): "29-JUN-2017",
    (2017, "JULY"): "27-JUL-2017",
    (2017, "AUGUST"): "31-AUG-2017",
    (2017, "SEPTEMBER"): "28-SEP-2017",
    (2017, "OCTOBER"): "26-OCT-2017",
    (2017, "NOVEMBER"): "30-NOV-2017",
    (2017, "DECEMBER"): "28-DEC-2017",

    (2018, "JANUARY"): "25-JAN-2018",
    (2018, "FEBRUARY"): "22-FEB-2018",
    (2018, "MARCH"): "28-MAR-2018",
    (2018, "APRIL"): "26-APR-2018",
    (2018, "MAY"): "31-MAY-2018",
    (2018, "JUNE"): "28-JUN-2018",
    (2018, "JULY"): "26-JUL-2018",
    (2018, "AUGUST"): "30-AUG-2018",
    (2018, "SEPTEMBER"): "27-SEP-2018",
    (2018, "OCTOBER"): "25-OCT-2018",
    (2018, "NOVEMBER"): "29-NOV-2018",
    (2018, "DECEMBER"): "27-DEC-2018",

    (2019, "JANUARY"): "31-JAN-2019",
    (2019, "FEBRUARY"): "28-FEB-2019",
    (2019, "MARCH"): "28-MAR-2019",
    (2019, "APRIL"): "25-APR-2019",
    (2019, "MAY"): "30-MAY-2019",
    (2019, "JUNE"): "27-JUN-2019",
    (2019, "JULY"): "25-JUL-2019",
    (2019, "AUGUST"): "29-AUG-2019",
    (2019, "SEPTEMBER"): "26-SEP-2019",
    (2019, "OCTOBER"): "31-OCT-2019",
    (2019, "NOVEMBER"): "28-NOV-2019",
    (2019, "DECEMBER"): "26-DEC-2019",

    (2020, "JANUARY"): "30-JAN-2020",
    (2020, "FEBRUARY"): "27-FEB-2020",
    (2020, "MARCH"): "26-MAR-2020",
    (2020, "APRIL"): "30-APR-2020",
    (2020, "MAY"): "28-MAY-2020",
    (2020, "JUNE"): "25-JUN-2020",
    (2020, "JULY"): "30-JUL-2020",
    (2020, "AUGUST"): "27-AUG-2020",
    (2020, "SEPTEMBER"): "24-SEP-2020",
    (2020, "OCTOBER"): "29-OCT-2020",
    (2020, "NOVEMBER"): "26-NOV-2020",
    (2020, "DECEMBER"): "31-DEC-2020",

    (2021, "JANUARY"): "28-JAN-2021",
    (2021, "FEBRUARY"): "25-FEB-2021",
    (2021, "MARCH"): "25-MAR-2021",
    (2021, "APRIL"): "29-APR-2021",
    (2021, "MAY"): "27-MAY-2021",
    (2021, "JUNE"): "24-JUN-2021",
    (2021, "JULY"): "29-JUL-2021",
    (2021, "AUGUST"): "26-AUG-2021",
    (2021, "SEPTEMBER"): "30-SEP-2021",
    (2021, "OCTOBER"): "28-OCT-2021",
    (2021, "NOVEMBER"): "25-NOV-2021",
    (2021, "DECEMBER"): "30-DEC-2021",
}

# ============================================================
# GLOBAL STATS
# ============================================================

FILES_SAVED = 0
FILES_SKIPPED = 0
FILES_FAILED = 0

# ============================================================
# FILE NAME PARSER
# ============================================================

def parse_contract_name(filename):

    name = Path(filename).stem.upper()

    # FORMAT 1/2 -> CE 6200 / PE 6200
    match = re.match(r"^(CE|PE)\s+(\d+)$", name)

    if match:
        option_type = match.group(1)
        strike = match.group(2)

        return strike, option_type

    # FORMAT 3/4 -> NIFTY9900CE
    match = re.match(r"^NIFTY(\d+)(CE|PE)$", name)

    if match:
        strike = match.group(1)
        option_type = match.group(2)

        return strike, option_type

    # FORMAT 5 -> NIFTY25JUN208500PE
    match = re.match(
        r"^NIFTY\d{1,2}[A-Z]{3}\d{2}(\d+)(CE|PE)$",
        name
    )

    if match:
        strike = match.group(1)
        option_type = match.group(2)

        return strike, option_type

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
        # GET YEAR / MONTH
        # ----------------------------------------------------

        relative_parts = file_path.relative_to(INPUT_FOLDER).parts

        year_folder = relative_parts[0]
        month_folder = relative_parts[1]

        # ----------------------------------------------------
        # GET HARDCODED EXPIRY
        # ----------------------------------------------------

        expiry_key = (
            int(year_folder),
            month_folder.upper()
        )

        if expiry_key not in MONTHLY_EXPIRIES:

            FILES_SKIPPED += 1

            print(f"\n[SKIPPED] Expiry not found:")
            print(file_path)

            terminate_program()

        expiry_date = pd.to_datetime(
            MONTHLY_EXPIRIES[expiry_key],
            format="%d-%b-%Y"
        )

        expiry_folder, expiry_month, expiry_year = (
            format_expiry_parts(expiry_date)
        )

        expiry_date_str = expiry_date.strftime("%d")

        # ----------------------------------------------------
        # OUTPUT FILE NAME
        # ----------------------------------------------------

        output_filename = (
            f"NIFTY_{strike}_{option_type}_"
            f"{expiry_date_str}_{expiry_month}_{expiry_year}.csv"
        )

        # ----------------------------------------------------
        # OUTPUT DIRECTORY
        # ----------------------------------------------------

        # output_dir = os.path.join(
        #     OUTPUT_FOLDER,
        #     year_folder,
        #     month_folder,
        #     expiry_folder,
        # )

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

27-FEB-2014 ✅ (Maha Shivaratri Holiday - Thursday)
29-MAR-2018 ✅ (Mahavir Jayanthi Holiday - Thursday)

"""

"""

30-JAN-2014
26-FEB-2014
27-MAR-2014
24-APR-2014
29-MAY-2014
26-JUN-2014
31-JUL-2014
28-AUG-2014
25-SEP-2014
30-OCT-2014
27-NOV-2014
24-DEC-2014

29-JAN-2015
26-FEB-2015
26-MAR-2015
30-APR-2015
28-MAY-2015
25-JUN-2015
30-JUL-2015
27-AUG-2015
24-SEP-2015
29-OCT-2015
26-NOV-2015
31-DEC-2015

28-JAN-2016
25-FEB-2016
31-MAR-2016
28-APR-2016
26-MAY-2016
30-JUN-2016
28-JUL-2016
25-AUG-2016
29-SEP-2016
27-OCT-2016
24-NOV-2016
29-DEC-2016

25-JAN-2017
23-FEB-2017
30-MAR-2017
27-APR-2017
25-MAY-2017
29-JUN-2017
27-JUL-2017
31-AUG-2017
28-SEP-2017
26-OCT-2017
30-NOV-2017
28-DEC-2017

25-JAN-2018
22-FEB-2018
28-MAR-2018
26-APR-2018
31-MAY-2018
28-JUN-2018
26-JUL-2018
30-AUG-2018
27-SEP-2018
25-OCT-2018
29-NOV-2018
27-DEC-2018

31-JAN-2019
28-FEB-2019
28-MAR-2019
25-APR-2019
30-MAY-2019
27-JUN-2019
25-JUL-2019
29-AUG-2019
26-SEP-2019
31-OCT-2019
28-NOV-2019
26-DEC-2019

30-JAN-2020
27-FEB-2020
26-MAR-2020
30-APR-2020
28-MAY-2020
25-JUN-2020
30-JUL-2020
27-AUG-2020
24-SEP-2020
29-OCT-2020
26-NOV-2020
31-DEC-2020

28-JAN-2021
25-FEB-2021
25-MAR-2021
29-APR-2021
27-MAY-2021
24-JUN-2021
29-JUL-2021
26-AUG-2021
30-SEP-2021
28-OCT-2021
25-NOV-2021
30-DEC-2021

"""