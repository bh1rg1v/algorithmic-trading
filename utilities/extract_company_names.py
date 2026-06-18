import os

# Define the input directory and output file paths
DATA_DIR = r"d:\github\algorithmic-trading\data\storage\equity\minute"
OUTPUT_FILE = r"d:\github\algorithmic-trading\data\storage\equity\company_names.txt"

def extract_company_names(data_dir, output_file):
    if not os.path.exists(data_dir):
        print(f"Error: Directory not found: {data_dir}")
        return

    company_names = []
    
    # Iterate through all files in the directory
    for filename in os.listdir(data_dir):
        if filename.endswith(".csv"):
            # Remove the .csv extension
            name_without_ext = filename[:-4]
            
            # Split by the first underscore to remove the number prefix (e.g., '0001_')
            parts = name_without_ext.split("_", 1)
            if len(parts) == 2:
                company_names.append(parts[1])
    
    # Sort the names alphabetically for convenience
    company_names.sort()

    # Save to the output file
    with open(output_file, 'w') as f:
        for name in company_names:
            f.write(name + "\n")
    
    print(f"Successfully extracted {len(company_names)} company names and saved them to {output_file}")

if __name__ == "__main__":
    extract_company_names(DATA_DIR, OUTPUT_FILE)