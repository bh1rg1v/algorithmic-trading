# Problem Statement:
# Recursively scan through the given root directory and delete
# all folders whose name is the same as their parent folder,
# even if they contain files/folders.
#
# Example:
#
# Before:
# Expiry 04th April/
#     Expiry 04th April/
#         some_file.csv
#
# After:
# Expiry 04th April/
#
# The inner duplicated folder and ALL its contents will be deleted.

import os
import shutil


def delete_duplicate_named_folders(root_folder):
    """
    Deletes folders whose name matches their parent folder name,
    including all files/subfolders inside them.

    Time Complexity: O(N)
    Space Complexity: O(1)
    """

    deleted_count = 0

    # Bottom-up traversal
    for current_root, dirs, files in os.walk(root_folder, topdown=False):

        current_folder_name = os.path.basename(current_root)

        parent_folder = os.path.dirname(current_root)

        parent_folder_name = os.path.basename(parent_folder)

        # Check if folder name matches parent folder name
        if current_folder_name == parent_folder_name:

            try:
                shutil.rmtree(current_root)

                print(f"[DELETED] {current_root}\n")

                deleted_count += 1

            except Exception as e:

                print(f"[ERROR] Could not delete:")
                print(current_root)

                print(f"Reason: {e}\n")

    print(f"\nTotal duplicate folders deleted: {deleted_count}")


# Root folder
root_folder = (
    r"D:\github\algorithmic-trading\data\reconstruct"
    r"\tradecharter\banknifty\weekly"
)

delete_duplicate_named_folders(root_folder)