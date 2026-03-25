import pandas as pd
import re

def parse_aif_data(text):
    """Parse AIF data from text format"""
    entries = []
    current_entry = {}
    
    lines = text.strip().split('\n')
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        # Check if line starts with a known field
        if line.startswith('Name'):
            # Save previous entry if exists
            if current_entry:
                entries.append(current_entry)
            # Start new entry
            current_entry = {'Name': line.replace('Name', '', 1)}
        elif line.startswith('Registration No.'):
            current_entry['Registration No.'] = line.replace('Registration No.', '', 1)
        elif line.startswith('E-mail'):
            current_entry['E-mail'] = line.replace('E-mail', '', 1)
        elif line.startswith('Address'):
            current_entry['Address'] = line.replace('Address', '', 1)
        elif line.startswith('Contact Person'):
            current_entry['Contact Person'] = line.replace('Contact Person', '', 1)
        elif line.startswith('Correspondence Address'):
            current_entry['Correspondence Address'] = line.replace('Correspondence Address', '', 1)
        elif line.startswith('Validity'):
            current_entry['Validity'] = line.replace('Validity', '', 1)
        elif line.startswith('Telephone'):
            current_entry['Telephone'] = line.replace('Telephone', '', 1)
        elif line.startswith('Fax No.'):
            current_entry['Fax No.'] = line.replace('Fax No.', '', 1)
    
    # Add last entry
    if current_entry:
        entries.append(current_entry)
    
    return entries

def add_to_csv(csv_path, new_data_text):
    """Add new AIF data to CSV file"""
    
    # Parse new data
    new_entries = parse_aif_data(new_data_text)
    
    if not new_entries:
        print("No data parsed from input text")
        return
    
    # Load existing CSV
    try:
        existing_df = pd.read_csv(csv_path)
        print(f"Loaded existing CSV with {len(existing_df)} entries")
    except FileNotFoundError:
        existing_df = pd.DataFrame()
        print("CSV not found, will create new file")
    
    # Convert new entries to DataFrame
    new_df = pd.DataFrame(new_entries)
    
    # Get all unique columns from both dataframes
    all_columns = list(set(existing_df.columns.tolist() + new_df.columns.tolist()))
    
    # Reindex both dataframes to have all columns
    existing_df = existing_df.reindex(columns=all_columns)
    new_df = new_df.reindex(columns=all_columns)
    
    # Combine dataframes
    combined_df = pd.concat([existing_df, new_df], ignore_index=True)
    
    # Remove duplicates based on Registration No.
    if 'Registration No.' in combined_df.columns:
        before_count = len(combined_df)
        combined_df = combined_df.drop_duplicates(subset=['Registration No.'], keep='last')
        after_count = len(combined_df)
        if before_count > after_count:
            print(f"Removed {before_count - after_count} duplicate entries")
    
    # Save to CSV
    combined_df.to_csv(csv_path, index=False)
    print(f"Saved {len(combined_df)} total entries to {csv_path}")
    print(f"Added {len(new_entries)} new entries")
    print(f"Columns: {', '.join(combined_df.columns.tolist())}")

if __name__ == "__main__":
    print("AIF Data Parser - Add entries to aif_list.csv")
    print("="*60)
    print("Paste your AIF data below.")
    print("When finished, type 'END' on a new line and press Enter.")
    print("="*60)
    print()
    
    lines = []
    while True:
        try:
            line = input()
            if line.strip().upper() == 'END':
                break
            lines.append(line)
        except EOFError:
            break
    
    aif_data = '\n'.join(lines)
    
    if not aif_data.strip():
        print("\nNo data provided. Exiting.")
    else:
        csv_path = "others/process_aif_funds_list/aif_list.csv"
        print("\nProcessing data...\n")
        add_to_csv(csv_path, aif_data)
