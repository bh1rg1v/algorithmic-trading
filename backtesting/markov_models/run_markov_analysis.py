import pandas as pd
import os
from datetime import datetime
import sys
import time
from multiprocessing import Pool, cpu_count
sys.path.append('.')
from markov_model1 import compute_markov_event_probs

def process_single_file(args):
    filename, data_dir, individual_dir = args
    print("Processing:", filename[:-4])
    try:
        # Load data
        filepath = os.path.join(data_dir, filename)
        df = pd.read_csv(filepath)
        
        # Ensure required columns exist
        required_cols = ['Open', 'High', 'Low', 'Close']
        if not all(col in df.columns for col in required_cols):
            return (filename, "Missing columns", None)
        
        # Run Markov analysis
        symbol = filename.replace('.csv', '').split('_', 1)[1]
        results = compute_markov_event_probs(df)
        
        if len(results) > 0:
            results['Symbol'] = symbol
            results['Filename'] = filename
            
            # Save individual file results
            individual_file = os.path.join(individual_dir, f"markov_{symbol}.csv")
            results.to_csv(individual_file, index=False)
            
            return (filename, "Success", (symbol, len(results)))
        else:
            return (filename, "No events", None)
            
    except Exception as e:
        return (filename, str(e), None)

def run_markov_analysis():
    start_time = time.time()
    
    # Configuration
    LIMIT = 250  # Number of files to process
    MAX_CORES = 16  # Maximum number of CPU cores to use (Available = 20)
    MIN_PROBABILITY = 75.0  # Minimum probability threshold
    MIN_COUNT = 10  # Minimum count threshold
    
    # Setup paths
    data_dir = r"data\storage\raw\equity\zerodha\2015\day"
    results_dir = r"backtestresults\markov"
    script_name = os.path.splitext(os.path.basename(__file__))[0]
    
    # Create timestamp for folder naming
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_folder = f"markov_run_{timestamp}"
    output_dir = os.path.join(results_dir, script_name, run_folder)
    individual_dir = os.path.join(output_dir, "individual_files")
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(individual_dir, exist_ok=True)
    
    # Get top LIMIT CSV files
    csv_files = [f for f in os.listdir(data_dir) if f.endswith('.csv')]
    csv_files.sort()  # Sort by filename (which includes ranking)
    top_files = csv_files[:LIMIT]
    
    print(f"Processing {len(top_files)} files (limit: {LIMIT})...")
    
    # Process files in parallel
    cores_to_use = min(MAX_CORES, cpu_count(), len(top_files))
    print(f"Using {cores_to_use} CPU cores for parallel processing")
    
    # Prepare arguments for multiprocessing
    args_list = [(filename, data_dir, individual_dir) for filename in top_files]
    
    successful_files = []
    failed_files = []
    
    processing_start = time.time()
    with Pool(processes=cores_to_use) as pool:
        results = pool.map(process_single_file, args_list)
    processing_time = time.time() - processing_start
    
    # Process results
    for filename, status, data in results:
        if status == "Success" and data:
            symbol, event_count = data
            successful_files.append((filename, symbol, event_count))
            print(f"Success: {filename} -> {event_count} events found")
        else:
            failed_files.append((filename, status))
            print(f"Failed: {filename} -> {status}")
    
    # Save processing summary
    if successful_files:
        success_df = pd.DataFrame(successful_files, columns=['Filename', 'Symbol', 'Event_Count'])
        success_file = os.path.join(output_dir, "successful_files.csv")
        success_df.to_csv(success_file, index=False)
        
        # Combine all individual files into one sorted file
        all_data = []
        for filename, symbol, _ in successful_files:
            individual_file = os.path.join(individual_dir, f"markov_{symbol}.csv")
            if os.path.exists(individual_file):
                df = pd.read_csv(individual_file)
                all_data.append(df)
        
        if all_data:
            combined_df = pd.concat(all_data, ignore_index=True)
            combined_df = combined_df[(combined_df['Probability'] >= MIN_PROBABILITY) & (combined_df['Count'] >= MIN_COUNT)]
            combined_df = combined_df.sort_values(['Probability', 'Count'], ascending=[False, False]).reset_index(drop=True)
            combined_file = os.path.join(output_dir, "markov_combined_sorted.csv")
            combined_df.to_csv(combined_file, index=False)
        
        # Save summary statistics
        total_time = time.time() - start_time
        summary_stats = {
            'Data Directory': data_dir,
            'Files Limit': LIMIT,
            'Min Probability': MIN_PROBABILITY,
            'Min Count': MIN_COUNT,
            'Total Files Processed': len(top_files),
            'Successful Files': len(successful_files),
            'Failed Files': len(failed_files),
            'Total Events': success_df['Event_Count'].sum(),
            'Average Events per Symbol': success_df['Event_Count'].mean(),
            'Processing Time (seconds)': round(processing_time, 2),
            'Total Time (seconds)': round(total_time, 2)
        }
        
        summary_df = pd.DataFrame(list(summary_stats.items()), columns=['Metric', 'Value'])
        summary_file = os.path.join(output_dir, "analysis_summary.csv")
        summary_df.to_csv(summary_file, index=False)
        
        print(f"\nAnalysis Summary:")
        print(f"  Limit set: {LIMIT}")
        print(f"  Cores used: {cores_to_use}")
        print(f"  Total files: {len(top_files)}")
        print(f"  Successful: {len(successful_files)}")
        print(f"  Failed: {len(failed_files)}")
        print(f"  Total events: {summary_stats['Total Events']}")
        print(f"  Processing time: {processing_time:.2f}s")
        print(f"  Total time: {total_time:.2f}s")
        print(f"  Individual results saved in: {output_dir}")
        
    # Save failed files log
    if failed_files:
        failed_df = pd.DataFrame(failed_files, columns=['Filename', 'Error'])
        failed_file = os.path.join(output_dir, "failed_files.csv")
        failed_df.to_csv(failed_file, index=False)
        print(f"  Failed files logged in: failed_files.csv")
    
    if not successful_files:
        print("No results generated!")

if __name__ == "__main__":
    run_markov_analysis()