import os
import sys
import random
import concurrent.futures
import pandas as pd
import numpy as np

# Base directory for options index data
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "storage", "options", "index"))

def process_chunk(chunk):
    """Processes a chunk of files, counting rows in binary mode for speed"""
    results = []
    errors = []
    sep = os.sep
    for file_path, rel_path, index_name in chunk:
        try:
            # Parse contract metadata from filename using fast string operations
            filename = file_path.split(sep)[-1]
            name_without_ext = filename[:-4] if filename.endswith('.csv') else filename
            parts = name_without_ext.split('_')
            
            strike = None
            opt_type = None
            expiry = None
            
            # Find strike price and option type CE/PE
            if len(parts) >= 4:
                for idx, part in enumerate(parts):
                    if part == 'CE' or part == 'PE':
                        opt_type = part
                        if idx > 0:
                            prev = parts[idx-1]
                            if prev.isdigit() or ('.' in prev and prev.replace('.', '', 1).isdigit()):
                                strike = float(prev) if '.' in prev else int(prev)
                        expiry = "_".join(parts[idx+1:])
                        break
            
            with open(file_path, 'rb') as f:
                content = f.read()
                count = content.count(b'\n')
                line_count = count - 1 if count > 0 else 0
                is_empty = len(content) == 0
                is_header_only = len(content) > 0 and line_count == 0
                
            results.append({
                'index': index_name,
                'path': file_path,
                'rel_path': rel_path,
                'rows': line_count,
                'strike': strike,
                'opt_type': opt_type,
                'expiry': expiry,
                'is_empty': is_empty,
                'is_header_only': is_header_only
            })
        except Exception as e:
            errors.append((rel_path, str(e)))
    return results, errors

def print_progress_bar(iteration, total, prefix='', suffix='', decimals=1, length=40, fill='█'):
    """Call in a loop to create terminal progress bar"""
    percent = ("{0:." + str(decimals) + "f}").format(100 * (iteration / float(total)))
    filled_length = int(length * iteration // total)
    bar = fill * filled_length + '-' * (length - filled_length)
    sys.stdout.write(f'\r{prefix} |{bar}| {percent}% {suffix}')
    sys.stdout.flush()
    if iteration == total:
        sys.stdout.write('\n')
        sys.stdout.flush()

def analyze_sample_files(file_paths, num_samples=100):
    """Samples and parses some CSV files to extract volume, price, and OI statistics"""
    samples = random.sample(file_paths, min(len(file_paths), num_samples))
    volumes = []
    prices = []
    ois = []
    
    for path in samples:
        try:
            df = pd.read_csv(path)
            if len(df) == 0:
                continue
                
            # Locate volume column
            vol_col = next((c for c in df.columns if c.lower() in ('volume', 'vol')), None)
            if vol_col is not None:
                volumes.append(df[vol_col].mean())
                
            # Locate close price column
            close_col = next((c for c in df.columns if c.lower() in ('close', 'cl')), None)
            if close_col is not None:
                prices.append(df[close_col].mean())
                
            # Locate Open Interest (OI) column
            oi_col = next((c for c in df.columns if c.lower() in ('oi', 'open_interest', 'open interest')), None)
            if oi_col is not None:
                ois.append(df[oi_col].mean())
        except Exception:
            pass
            
    return {
        'avg_volume': np.mean(volumes) if volumes else 0.0,
        'avg_price': np.mean(prices) if prices else 0.0,
        'avg_oi': np.mean(ois) if ois else 0.0
    }

def get_csv_files(directory, base_dir, index_name):
    """Iteratively scans directory for CSV files using fast os.scandir and slice-based relative paths"""
    files_list = []
    stack = [directory]
    base_len = len(base_dir) + 1
    while stack:
        curr_dir = stack.pop()
        try:
            for entry in os.scandir(curr_dir):
                if entry.is_dir(follow_symlinks=False):
                    stack.append(entry.path)
                elif entry.is_file(follow_symlinks=False) and entry.name.endswith('.csv'):
                    files_list.append((entry.path, entry.path[base_len:], index_name))
        except Exception:
            pass
    return files_list

def scan_index_data():
    if not os.path.exists(BASE_DIR):
        print(f"Directory not found: {BASE_DIR}")
        return
        
    # List all indices (subdirectories under BASE_DIR)
    all_indices = sorted([d for d in os.listdir(BASE_DIR) if os.path.isdir(os.path.join(BASE_DIR, d))])
    
    all_indices = ["banknifty"]  # User override
    
    # Filter indices that don't have stats file
    indices = []
    for ind in all_indices:
        stats_path = os.path.join(os.path.dirname(__file__), f"{ind}_stats.txt")
        if os.path.exists(stats_path):
            print(f"Stats file for {ind} already exists, skipping index.")
        else:
            indices.append(ind)
            
    if not indices:
        print("All indices have already been processed (stats files exist).")
        return
        
    print(f"Scanning index options data in: {BASE_DIR} using multi-threading")
    
    # Collect all CSV files using optimized stack scanner
    files_to_process = []
    for index_name in indices:
        index_dir = os.path.join(BASE_DIR, index_name)
        files_to_process.extend(get_csv_files(index_dir, BASE_DIR, index_name))
                    
    total_files = len(files_to_process)
    print(f"Found {total_files} CSV files to process. Starting parallel execution...")
    
    if total_files == 0:
        print("No CSV files found to process.")
        return

    # Split files into chunks to reduce Future scheduling overhead
    chunk_size = 1000
    chunks = [files_to_process[i:i + chunk_size] for i in range(0, total_files, chunk_size)]
    
    all_results = []
    errors = []
    num_workers = min(32, (os.cpu_count() or 1) * 4)
    
    # Initialize progress bar
    print_progress_bar(0, total_files, prefix='Progress:', suffix=f'Processed 0/{total_files} files', length=40)
    
    completed_files = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=num_workers) as executor:
        future_to_chunk = {executor.submit(process_chunk, chunk): chunk for chunk in chunks}
        
        for future in concurrent.futures.as_completed(future_to_chunk):
            chunk_results, chunk_errors = future.result()
            chunk = future_to_chunk[future]
            completed_files += len(chunk)
            
            print_progress_bar(completed_files, total_files, prefix='Progress:', suffix=f'Processed {completed_files}/{total_files} files', length=40)
            all_results.extend(chunk_results)
            errors.extend(chunk_errors)

    # Perform EDA groupings
    print(f"\nProcessing EDA Summary Statistics...")
    df_meta = pd.DataFrame(all_results)
    
    for index_name in indices:
        df_index = df_meta[df_meta['index'] == index_name]
        if len(df_index) == 0:
            continue
            
        # 1. Metadata Stats
        total_index_files = len(df_index)
        ce_count = len(df_index[df_index['opt_type'] == 'CE'])
        pe_count = len(df_index[df_index['opt_type'] == 'PE'])
        ce_pct = (ce_count / total_index_files) * 100 if total_index_files > 0 else 0
        pe_pct = (pe_count / total_index_files) * 100 if total_index_files > 0 else 0
        
        unique_expiries = df_index['expiry'].dropna().nunique()
        
        strikes = df_index['strike'].dropna().unique()
        min_strike = np.min(strikes) if len(strikes) > 0 else "N/A"
        max_strike = np.max(strikes) if len(strikes) > 0 else "N/A"
        
        # Calculate most common strike price step (difference)
        strike_step = "N/A"
        if len(strikes) > 1:
            sorted_strikes = sorted(strikes)
            diffs = np.diff(sorted_strikes)
            # Filter out diffs of 0 and find most common difference
            diffs = diffs[diffs > 0]
            if len(diffs) > 0:
                values, counts = np.unique(diffs, return_counts=True)
                strike_step = values[np.argmax(counts)]

        # 2. Data Density / Row Stats
        total_rows = df_index['rows'].sum()
        empty_files = len(df_index[df_index['is_empty'] == True])
        header_only_files = len(df_index[df_index['is_header_only'] == True])
        empty_pct = (empty_files / total_index_files) * 100 if total_index_files > 0 else 0
        header_only_pct = (header_only_files / total_index_files) * 100 if total_index_files > 0 else 0
        active_files_df = df_index[df_index['rows'] > 0]
        active_files_count = len(active_files_df)
        active_pct = (active_files_count / total_index_files) * 100 if total_index_files > 0 else 0
        
        active_rows = active_files_df['rows']
        min_rows = np.min(active_rows) if len(active_rows) > 0 else 0
        max_rows = np.max(active_rows) if len(active_rows) > 0 else 0
        mean_rows = np.mean(active_rows) if len(active_rows) > 0 else 0.0
        median_rows = np.median(active_rows) if len(active_rows) > 0 else 0.0

        # 3. Sampled Data Stats (Volume, Price, OI)
        sample_stats = {'avg_volume': 0.0, 'avg_price': 0.0, 'avg_oi': 0.0}
        if active_files_count > 0:
            sample_paths = active_files_df['path'].tolist()
            sample_stats = analyze_sample_files(sample_paths, num_samples=100)

        # Build report
        report_lines = []
        report_lines.append(f"{'='*80}")
        report_lines.append(f"INDEX EDA SUMMARY: {index_name.upper()}")
        report_lines.append(f"{'='*80}")
        report_lines.append(f"Metadata Statistics:")
        report_lines.append(f"  - Total Files (Contracts) : {total_index_files:,}")
        report_lines.append(f"  - Call Options (CE)       : {ce_count:,} ({ce_pct:.1f}%)")
        report_lines.append(f"  - Put Options (PE)        : {pe_count:,} ({pe_pct:.1f}%)")
        report_lines.append(f"  - Unique Expiry Dates     : {unique_expiries:,}")
        report_lines.append(f"  - Strike Price Range      : {min_strike} to {max_strike} (Common Step: {strike_step})")
        report_lines.append(f"\nData Density Statistics:")
        report_lines.append(f"  - Total Row Count (Mins)  : {total_rows:,}")
        report_lines.append(f"  - Completely Empty (0B)   : {empty_files:,} ({empty_pct:.1f}%)")
        report_lines.append(f"  - Header-only Files       : {header_only_files:,} ({header_only_pct:.1f}%)")
        report_lines.append(f"  - Active Files (>0 rows)  : {active_files_count:,} ({active_pct:.1f}%)")
        report_lines.append(f"  - Rows per Active File:")
        report_lines.append(f"      - Min                 : {min_rows:,}")
        report_lines.append(f"      - Max                 : {max_rows:,}")
        report_lines.append(f"      - Mean                : {mean_rows:.1f}")
        report_lines.append(f"      - Median              : {median_rows:.1f}")
        report_lines.append(f"\nSampled Data Statistics (from 100 random active contracts):")
        report_lines.append(f"  - Average Volume / Candle : {sample_stats['avg_volume']:.1f}")
        report_lines.append(f"  - Average Close Price     : {sample_stats['avg_price']:.2f}")
        report_lines.append(f"  - Average Open Interest   : {sample_stats['avg_oi']:.1f}")
        
        report_text = "\n".join(report_lines)
        print(f"\n{report_text}")
        
        # Save to file
        stats_path = os.path.join(os.path.dirname(__file__), f"{index_name}_stats.txt")
        try:
            with open(stats_path, 'w', encoding='utf-8') as sf:
                sf.write(report_text)
            print(f"Saved stats to {stats_path}")
        except Exception as e:
            print(f"Error saving stats to {stats_path}: {e}")
        
    if errors:
        print(f"\n--- Errors encountered during scan ({len(errors)}) ---")
        for rel_path, err in errors[:20]:
            print(f"Error reading {rel_path}: {err}")
        if len(errors) > 20:
            print(f"... and {len(errors) - 20} more errors.")
            
    print(f"\nScan complete. Total files processed: {total_files:,}")

if __name__ == "__main__":
    scan_index_data()
