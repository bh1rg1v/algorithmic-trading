import os
import sys
import csv
from datetime import datetime
from concurrent.futures import ProcessPoolExecutor, as_completed

# Define paths
DATA_DIR = os.path.join("data", "storage", "options", "index", "2014-2024", "nifty")
OUTPUT_CSV = "contract_data_availability.csv"

def parse_date(date_str):
    """
    Robustly parses date strings of different formats into datetime objects.
    """
    date_str = date_str.strip()
    for fmt in ('%d-%m-%Y', '%Y-%m-%d', '%d/%m/%Y', '%Y/%m/%d'):
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            pass
    return None

def process_expiry_contracts(year, expiry_folder, expiry_path):
    """
    Processes all option contracts in a single expiry directory.
    For each contract (CSV file), it counts the unique days of data,
    the start date, and the end date.
    """
    try:
        csv_files = [f for f in os.listdir(expiry_path) if f.lower().endswith('.csv')]
        if not csv_files:
            return []
        
        results = []
        for csv_file in csv_files:
            csv_path = os.path.join(expiry_path, csv_file)
            contract_name = os.path.splitext(csv_file)[0]
            unique_dates = set()
            
            try:
                with open(csv_path, 'r', encoding='utf-8') as f:
                    # Skip header
                    header = f.readline()
                    if not header:
                        continue
                    
                    last_date = None
                    for line in f:
                        comma_idx = line.find(',')
                        if comma_idx != -1:
                            date_str = line[:comma_idx].strip()
                            if date_str != last_date:
                                if date_str.lower() not in ('date', ''):
                                    unique_dates.add(date_str)
                                    last_date = date_str
            except Exception as e:
                print(f"[WARNING] Error reading {csv_path}: {e}")
                continue
                
            if not unique_dates:
                results.append({
                    "Year": year,
                    "Expiry": expiry_folder,
                    "Contract": contract_name,
                    "Days_Count": 0,
                    "Start_Date": "N/A",
                    "End_Date": "N/A"
                })
                continue
            
            # Parse only unique dates (usually 1 to 50 dates per contract)
            parsed_dates = []
            for d in unique_dates:
                dt = parse_date(d)
                if dt:
                    parsed_dates.append(dt)
            
            if parsed_dates:
                parsed_dates.sort()
                start_date = parsed_dates[0].strftime('%Y-%m-%d')
                end_date = parsed_dates[-1].strftime('%Y-%m-%d')
            else:
                start_date = "N/A"
                end_date = "N/A"
                
            results.append({
                "Year": year,
                "Expiry": expiry_folder,
                "Contract": contract_name,
                "Days_Count": len(unique_dates),
                "Start_Date": start_date,
                "End_Date": end_date
            })
            
        return results
    except Exception as e:
        print(f"[ERROR] Error processing folder {expiry_path}: {e}")
        return []

def main():
    if not os.path.exists(DATA_DIR):
        print(f"Error: Option data directory not found at: {DATA_DIR}")
        print("Please check the path or workspace root.")
        sys.exit(1)
        
    print("=" * 80)
    print("CONTRACT DATA AVAILABILITY CALCULATOR (MULTIPROCESSING)")
    print("=" * 80)
    print(f"Scanning directory: {DATA_DIR}\n")
    
    # Gather all expiry directories
    tasks = []
    
    # We expect directory structure: nifty/<year>/<expiry_folder>
    for year in sorted(os.listdir(DATA_DIR)):
        year_path = os.path.join(DATA_DIR, year)
        if not os.path.isdir(year_path):
            continue
            
        for expiry_folder in sorted(os.listdir(year_path)):
            expiry_path = os.path.join(year_path, expiry_folder)
            if not os.path.isdir(expiry_path):
                continue
                
            tasks.append((year, expiry_folder, expiry_path))
            
    print(f"Found {len(tasks)} expiry directories to process.")
    print("Running optimized contract-level processing using multiprocessing...")
    
    results = []
    processed_count = 0
    total_tasks = len(tasks)
    
    # ProcessPoolExecutor will spawn multiple worker processes
    with ProcessPoolExecutor() as executor:
        futures = {executor.submit(process_expiry_contracts, y, e, p): (y, e) for y, e, p in tasks}
        
        for future in as_completed(futures):
            res_list = future.result()
            if res_list:
                results.extend(res_list)
            processed_count += 1
            if processed_count % 10 == 0 or processed_count == total_tasks:
                print(f"Progress: {processed_count}/{total_tasks} expiries processed...", end='\r')
    
    print("\nProcessing complete!\n")
    
    # Sort results by Year, Expiry folder, and Contract name
    results.sort(key=lambda x: (x["Year"], x["Expiry"], x["Contract"]))
    
    # Write to CSV
    try:
        with open(OUTPUT_CSV, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = ["Year", "Expiry", "Contract", "Days_Count", "Start_Date", "End_Date"]
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            for r in results:
                writer.writerow(r)
        print(f"✓ Detailed contract report saved to: {os.path.abspath(OUTPUT_CSV)}\n")
    except Exception as e:
        print(f"Error saving report to CSV: {e}")
        
    # Compile the "days of data : count of contracts" distribution
    days_to_contract_count = {}
    for r in results:
        days = r["Days_Count"]
        days_to_contract_count[days] = days_to_contract_count.get(days, 0) + 1
        
    # Display the frequency distribution (ALL OF IT)
    print("=" * 80)
    print("DISTRIBUTION: DAYS OF DATA TO COUNT OF CONTRACTS")
    print("=" * 80)
    print(f"{'Days of Data':<15} | {'Count of Contracts':<20}")
    print("-" * 40)
    for days in sorted(days_to_contract_count.keys()):
        print(f"{days:<15} | {days_to_contract_count[days]:<20}")
    print("=" * 80)
    
    # Display summary statistics
    if results:
        total_contracts = len(results)
        avg_days = sum(r["Days_Count"] for r in results) / total_contracts
        max_days_contract = max(results, key=lambda x: x["Days_Count"])
        min_days_contract = min(results, key=lambda x: x["Days_Count"])
        
        print("\nSUMMARY STATISTICS")
        print("=" * 80)
        print(f"Total Contracts Scanned      : {total_contracts}")
        print(f"Average Days per Contract    : {avg_days:.2f} days")
        print(f"Max Days of Data in Contract : {max_days_contract['Days_Count']} days ({max_days_contract['Contract']})")
        print(f"Min Days of Data in Contract : {min_days_contract['Days_Count']} days ({min_days_contract['Contract']})")
        print("-" * 80)
        
        # Display breakdown by year
        print("\nYearly Breakdown of Contracts:")
        print(f"{'Year':<8}{'Contracts':<12}{'Avg Days':<12}")
        print("-" * 32)
        
        yearly_stats = {}
        for r in results:
            y = r["Year"]
            if y not in yearly_stats:
                yearly_stats[y] = {"count": 0, "days": 0}
            yearly_stats[y]["count"] += 1
            yearly_stats[y]["days"] += r["Days_Count"]
            
        for y in sorted(yearly_stats.keys()):
            stats = yearly_stats[y]
            yr_avg = stats["days"] / stats["count"]
            print(f"{y:<8}{stats['count']:<12}{yr_avg:<12.2f}")
            
        print("=" * 80)

if __name__ == "__main__":
    main()
