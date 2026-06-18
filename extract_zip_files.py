# Problem Statement:
# Scan through a given folder (including all child folders),
# find all .zip files, extract them in their respective locations,
# and delete the ZIP files after successful extraction.

import os
import zipfile


def extract_zip_files(root_folder):
    """
    Recursively scans through all folders starting from root_folder,
    finds ZIP files, extracts them into folders with the same name,
    and deletes the ZIP files after successful extraction.

    Time Complexity: O(N)
    Space Complexity: O(1) excluding extracted data
    """

    extracted_count = 0
    deleted_count = 0
    failed_count = 0

    # Walk through all directories and subdirectories
    for current_path, _, files in os.walk(root_folder):

        for file in files:

            # Check for ZIP files
            if file.lower().endswith(".zip"):

                zip_path = os.path.join(current_path, file)

                # Create extraction folder
                extract_folder = os.path.join(
                    current_path,
                    os.path.splitext(file)[0]
                )

                print(f"\n[FOUND] {zip_path}")

                try:
                    # Create extraction directory if not exists
                    os.makedirs(extract_folder, exist_ok=True)

                    # Extract ZIP
                    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                        zip_ref.extractall(extract_folder)

                    print(f"[EXTRACTED] -> {extract_folder}")

                    extracted_count += 1

                    # Delete ZIP after successful extraction
                    os.remove(zip_path)

                    print(f"[DELETED] -> {zip_path}")

                    deleted_count += 1

                except Exception as e:
                    print(f"[FAILED] {zip_path}")
                    print(f"Reason: {e}")

                    failed_count += 1

    print("\n========== SUMMARY ==========")
    print(f"Total Extracted : {extracted_count}")
    print(f"Total Deleted   : {deleted_count}")
    print(f"Total Failed    : {failed_count}")


# ================= TEST =================

if __name__ == "__main__":

    # Change this path
    folder_path = r"D:\github\algorithmic-trading\data\reconstruct\tradecharter\banknifty\weekly"

    extract_zip_files(folder_path)