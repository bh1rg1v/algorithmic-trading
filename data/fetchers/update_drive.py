import os
import shutil
import time


def copy_base_to_output(base_folder, output_folder, copy_everything=False):
    """
    Copies all folders and files from base_folder to output_folder.

    Parameters:
    ----------
    base_folder : str
        Source directory path.

    output_folder : str
        Destination directory path.

    copy_everything : bool, default=False
        False:
            - Skip files that already exist in output_folder.
        True:
            - Replace existing files in output_folder.
    """

    start_time = time.time()

    # Ensure source exists
    if not os.path.exists(base_folder):
        raise FileNotFoundError(f"Base folder does not exist: {base_folder}")

    # Create output folder if not present
    os.makedirs(output_folder, exist_ok=True)

    skipped = 0
    copied = 0
    replaced = 0

    # Walk through every folder/file in base_folder
    for root, dirs, files in os.walk(base_folder):

        # Preserve folder structure
        relative_path = os.path.relpath(root, base_folder)
        destination_root = os.path.join(output_folder, relative_path)

        # Create subfolders in output
        os.makedirs(destination_root, exist_ok=True)

        # Process files
        for file_name in files:

            source_file = os.path.join(root, file_name)
            destination_file = os.path.join(destination_root, file_name)

            # If file exists
            if os.path.exists(destination_file):

                # Replace only if copy_everything=True
                if copy_everything:
                    shutil.copy2(source_file, destination_file)
                    # print(f"Replaced: {destination_file}")
                    replaced += 1

                else:
                    # print(f"Skipped: {destination_file}")
                    skipped += 1
                    pass

            else:
                # Copy new file
                shutil.copy2(source_file, destination_file)
                # print(f"Copied: {destination_file}")
                copied += 1

            if copied % 500 == 0 and copied > 0:
                print(f"\nCopied {copied} files...\n")

            if skipped % 1000 == 0 and skipped > 0:
                print(f"\tSkipped {skipped} files...")

    print(f"Copied: {copied} | Replaced: {replaced} | Skipped: {skipped}")

    end_time = time.time()

    total_time = end_time - start_time

    print(f"Time Taken: {total_time:.2f} seconds")

def index_options():

    # copying index options data to drive

    base_folder = r"data\storage\options\index"
    base_folder = r"D:\github\algorithmic-trading\data\storage\options\index"
    output_folder = "G:\\My Drive\\public\\paid\\data\\options\\index"

    print("\nCopying index options data to drive...")
    copy_base_to_output(base_folder, output_folder, copy_everything=False)

def stock_options():

    # copying stock options data to drive

    base_folder = r"D:\github\algorithmic-trading\data\storage\options\stocks"
    output_folder = "G:\\My Drive\\public\\paid\\data\\options\\stocks"

    print("\nCopying stock options data to drive...")
    copy_base_to_output(base_folder, output_folder, copy_everything=False)

def equity():

    # copying equity data to drive

    base_folder = r"D:\github\algorithmic-trading\data\storage\equity"
    output_folder = "G:\\My Drive\\public\\paid\\data\\equity"

    print("\nCopying equity data to drive...")
    copy_base_to_output(base_folder, output_folder, copy_everything=False)

def fundamentals():

    # copying fundamentals data to drive

    base_folder = r"D:\github\algorithmic-trading\data\storage\fundamentals"
    output_folder = "G:\\My Drive\\public\\paid\\data\\fundamentals"

    print("\nCopying fundamentals data to drive...")
    copy_base_to_output(base_folder, output_folder, copy_everything=False)

def implied_volatility():

    # copying implied volatility data to drive

    base_folder = r"D:\github\algorithmic-trading\data\storage\implied volatility"
    output_folder = "G:\\My Drive\\public\\paid\\data\\implied volatility"

    print("\nCopying implied volatility data to drive...")
    copy_base_to_output(base_folder, output_folder, copy_everything=True)



def main():

    # index_options()
    # stock_options()
    # equity()
    fundamentals()
    # implied_volatility()

    return

if __name__ == "__main__":
    main()