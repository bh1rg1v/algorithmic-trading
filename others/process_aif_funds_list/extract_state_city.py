import pandas as pd

# Map of Indian states and their capital cities
STATE_CAPITAL_MAP = {
    'ANDHRA PRADESH': 'AMARAVATI',
    'ARUNACHAL PRADESH': 'ITANAGAR',
    'ASSAM': 'DISPUR',
    'BIHAR': 'PATNA',
    'CHHATTISGARH': 'RAIPUR',
    'GOA': 'PANAJI',
    'GUJARAT': 'GANDHINAGAR',
    'HARYANA': 'CHANDIGARH',
    'HIMACHAL PRADESH': 'SHIMLA',
    'JHARKHAND': 'RANCHI',
    'KARNATAKA': 'BANGALORE',
    'KERALA': 'THIRUVANANTHAPURAM',
    'MADHYA PRADESH': 'BHOPAL',
    'MAHARASHTRA': 'MUMBAI',
    'MANIPUR': 'IMPHAL',
    'MEGHALAYA': 'SHILLONG',
    'MIZORAM': 'AIZAWL',
    'NAGALAND': 'KOHIMA',
    'ODISHA': 'BHUBANESWAR',
    'PUNJAB': 'CHANDIGARH',
    'RAJASTHAN': 'JAIPUR',
    'SIKKIM': 'GANGTOK',
    'TAMIL NADU': 'CHENNAI',
    'TELANGANA': 'HYDERABAD',
    'TRIPURA': 'AGARTALA',
    'UTTAR PRADESH': 'LUCKNOW',
    'UTTARAKHAND': 'DEHRADUN',
    'WEST BENGAL': 'KOLKATA',
    'NATIONAL CAPITAL TERRITORY OF DELHI': 'NEW DELHI',
    'PUDUCHERRY': 'PUDUCHERRY',
    'JAMMU AND KASHMIR': 'SRINAGAR',
    'LADAKH': 'LEH'
}

# Capital cities list for easy lookup
CAPITAL_CITIES = set(STATE_CAPITAL_MAP.values())

def extract_state_city(address_text):
    """Extract state and capital city from address text"""
    if pd.isna(address_text) or not address_text:
        return None, None
    
    address_upper = str(address_text).upper()
    
    found_state = None
    found_city = None
    
    # Check for state
    for state in STATE_CAPITAL_MAP.keys():
        if state in address_upper:
            found_state = state
            break
    
    # Check for capital city only
    for capital in CAPITAL_CITIES:
        if capital in address_upper:
            found_city = capital
            break
    
    return found_state, found_city

def add_state_city_columns(input_csv_path, output_csv_path):
    """Add State and City columns to the CSV and save to new file"""
    
    print(f"Reading CSV file: {input_csv_path}")
    df = pd.read_csv(input_csv_path)
    
    print(f"Loaded {len(df)} entries")
    
    # Initialize new columns
    df['State'] = None
    df['City'] = None
    
    # Process each row
    for idx, row in df.iterrows():
        address = row.get('Address', '')
        corr_address = row.get('Correspondence Address', '')
        
        # Try to extract from Address first
        state, city = extract_state_city(address)
        
        # If not found, try Correspondence Address
        if not state or not city:
            state2, city2 = extract_state_city(corr_address)
            if not state:
                state = state2
            if not city:
                city = city2
        
        df.at[idx, 'State'] = state
        df.at[idx, 'City'] = city
        
        if (idx + 1) % 10 == 0:
            print(f"Processed {idx + 1}/{len(df)} entries...")
    
    # Save to new CSV
    df.to_csv(output_csv_path, index=False)
    
    print(f"\n✓ Successfully saved to {output_csv_path}")
    print(f"\nStatistics:")
    print(f"  Total entries: {len(df)}")
    print(f"  Entries with State: {df['State'].notna().sum()}")
    print(f"  Entries with City: {df['City'].notna().sum()}")
    print(f"  Entries with both: {(df['State'].notna() & df['City'].notna()).sum()}")
    
    # Show state distribution
    print(f"\nState Distribution:")
    state_counts = df['State'].value_counts()
    for state, count in state_counts.head(10).items():
        print(f"  {state}: {count}")
    
    # Show city distribution
    print(f"\nCapital Cities Found:")
    city_counts = df['City'].value_counts()
    for city, count in city_counts.items():
        print(f"  {city}: {count}")

if __name__ == "__main__":
    input_csv = "others/process_aif_funds_list/aif_list.csv"
    output_csv = "others/process_aif_funds_list/aif_list_with_location.csv"
    add_state_city_columns(input_csv, output_csv)
