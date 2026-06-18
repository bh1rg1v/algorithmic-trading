# Problem Statement:
# Scan through the given root folder recursively.
# Find folders starting with "CSV" inside duplicated folders like:
#
# Expiry XYZ/
#     Expiry XYZ/
#         CSV .../
#             files...
#
# Move ALL FILES from the CSV folder up by TWO levels into:
#
# Expiry XYZ/
#
# and optionally remove empty folders afterward.

import os
import shutil


def move_csv_files_up(root_folder):
    """
    Recursively scans folders and moves files inside folders starting
    with 'CSV' up by two directory levels.

    Example:
    Before:
    Expiry 26th April/
        Expiry 26th April/
            CSV 18th Apr to 26th Apr (Expiry)/
                abc.csv
                xyz.csv

    After:
    Expiry 26th April/
        abc.csv
        xyz.csv

    Time Complexity: O(N)
    Space Complexity: O(1)
    """

    moved_files = 0

    # Bottom-up traversal
    for current_root, dirs, files in os.walk(root_folder, topdown=False):

        for folder_name in dirs:

            # Only process folders starting with CSV
            if not folder_name.startswith("CSV"):
                continue

            csv_folder_path = os.path.join(current_root, folder_name)

            # Destination = two levels up
            destination_folder = os.path.dirname(current_root)

            print(f"\n[PROCESSING] {csv_folder_path}")
            print(f"[DESTINATION] {destination_folder}\n")

            # Move all files recursively
            for inner_root, inner_dirs, inner_files in os.walk(csv_folder_path):

                for file_name in inner_files:

                    source_file = os.path.join(inner_root, file_name)
                    destination_file = os.path.join(
                        destination_folder,
                        file_name
                    )

                    # Skip duplicates
                    if os.path.exists(destination_file):
                        print(f"[SKIPPED] Already exists: {destination_file}")
                        continue

                    shutil.move(source_file, destination_file)

                    print(f"[MOVED]")
                    print(f"FROM: {source_file}")
                    print(f"TO  : {destination_file}\n")

                    moved_files += 1

            # Remove empty CSV folder after moving
            try:
                shutil.rmtree(csv_folder_path)
                print(f"[REMOVED] {csv_folder_path}\n")
            except Exception as e:
                print(f"[WARNING] Could not remove folder: {e}")

            # Remove duplicated empty folder if empty
            try:
                if not os.listdir(current_root):
                    os.rmdir(current_root)
                    print(f"[REMOVED EMPTY] {current_root}\n")
            except Exception as e:
                print(f"[WARNING] Could not remove folder: {e}")

    print(f"\nTotal files moved: {moved_files}")


# Root folder
root_folder = r"D:\github\algorithmic-trading\data\reconstruct\tradecharter\banknifty\weekly"

move_csv_files_up(root_folder)