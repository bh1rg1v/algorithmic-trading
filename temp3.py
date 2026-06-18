# Problem Statement:
# Recursively scan through the given root directory and rename
# folders of the format:
#
# Expiry 01st November
#
# into:
#
# YYYY-MM-DD
#
# Where:
# YYYY -> extracted from grandparent folder
# MM   -> extracted from parent folder
# DD   -> extracted from current folder name
#
# Example:
#
# Before:
# 2018/
#     November/
#         Expiry 01st November/
#
# After:
# 2018/
#     November/
#         2018-11-01/

import os
import re


def rename_expiry_folders(root_folder):
    """
    Renames expiry folders into YYYY-MM-DD format.

    Time Complexity: O(N)
    Space Complexity: O(1)
    """

    # Month name -> month number mapping
    month_map = {
        "January": "01",
        "February": "02",
        "March": "03",
        "April": "04",
        "May": "05",
        "June": "06",
        "July": "07",
        "August": "08",
        "September": "09",
        "October": "10",
        "November": "11",
        "December": "12",
    }

    renamed_count = 0

    # Bottom-up traversal
    for current_root, dirs, files in os.walk(root_folder, topdown=False):

        current_folder_name = os.path.basename(current_root)

        # Match:
        # Expiry 01st November
        match = re.match(
            r"Expiry\s+(\d+)(st|nd|rd|th)\s+([A-Za-z]+)",
            current_folder_name
        )

        if not match:
            continue

        # Extract day
        day = match.group(1).zfill(2)

        # Parent folder = month
        parent_folder = os.path.dirname(current_root)
        month_name = os.path.basename(parent_folder)

        # Grandparent folder = year
        grandparent_folder = os.path.dirname(parent_folder)
        year = os.path.basename(grandparent_folder)

        # Validate month
        if month_name not in month_map:

            print(f"[SKIPPED] Invalid month folder:")
            print(parent_folder)
            print()

            continue

        month = month_map[month_name]

        # New folder name
        new_folder_name = f"{year}-{month}-{day}"

        # New path
        new_folder_path = os.path.join(
            parent_folder,
            new_folder_name
        )

        # Skip if already exists
        if os.path.exists(new_folder_path):

            print(f"[SKIPPED] Already exists:")
            print(new_folder_path)
            print()

            continue

        try:
            os.rename(current_root, new_folder_path)

            print(f"[RENAMED]")
            print(f"FROM: {current_root}")
            print(f"TO  : {new_folder_path}")
            print()

            renamed_count += 1

        except Exception as e:

            print(f"[ERROR] Could not rename:")
            print(current_root)

            print(f"Reason: {e}")
            print()

    print(f"\nTotal folders renamed: {renamed_count}")


# Root folder
root_folder = (
    r"D:\github\algorithmic-trading\data\reconstruct"
    r"\tradecharter\banknifty\weekly"
)

rename_expiry_folders(root_folder)