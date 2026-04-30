import pandas as pd
import os

def load_config_log(csv_path):
    """Load config log CSV"""
    if not os.path.exists(csv_path):
        print(f"Error: {csv_path} not found")
        return None
    
    df = pd.read_csv(csv_path)
    print(f"Loaded {len(df)} configurations from {csv_path}\n")
    return df

def display_summary(df):
    """Display summary statistics"""
    print("="*80)
    print("CONFIG LOG SUMMARY")
    print("="*80)
    print(f"\nTotal Configurations: {len(df)}")
    print(f"\nColumns: {', '.join(df.columns.tolist())}")
    
    if 'total_trades' in df.columns:
        print(f"\nTotal Trades Statistics:")
        print(f"  Min: {df['total_trades'].min()}")
        print(f"  Max: {df['total_trades'].max()}")
        print(f"  Mean: {df['total_trades'].mean():.2f}")
        print(f"  Median: {df['total_trades'].median():.2f}")
    
    if 'profit_rate' in df.columns:
        print(f"\nProfit Rate Statistics:")
        print(f"  Min: {df['profit_rate'].min():.2f}%")
        print(f"  Max: {df['profit_rate'].max():.2f}%")
        print(f"  Mean: {df['profit_rate'].mean():.2f}%")
        print(f"  Median: {df['profit_rate'].median():.2f}%")
    
    if 'win_rate' in df.columns:
        print(f"\nWin Rate Statistics:")
        print(f"  Min: {df['win_rate'].min():.2f}%")
        print(f"  Max: {df['win_rate'].max():.2f}%")
        print(f"  Mean: {df['win_rate'].mean():.2f}%")
        print(f"  Median: {df['win_rate'].median():.2f}%")
    
    if 'total_pnl' in df.columns:
        print(f"\nTotal PnL Statistics:")
        print(f"  Min: {df['total_pnl'].min():.2f}")
        print(f"  Max: {df['total_pnl'].max():.2f}")
        print(f"  Mean: {df['total_pnl'].mean():.2f}")
        print(f"  Sum: {df['total_pnl'].sum():.2f}")

def filter_top_configs(df, metric='profit_rate', top_n=10):
    """Filter top N configurations by metric"""
    if metric not in df.columns:
        print(f"Error: Metric '{metric}' not found in dataframe")
        return None
    
    top_df = df.nlargest(top_n, metric)
    
    print(f"\n{'='*80}")
    print(f"TOP {top_n} CONFIGURATIONS BY {metric.upper()}")
    print("="*80)
    
    for idx, row in top_df.iterrows():
        print(f"\nRank {top_df.index.get_loc(idx) + 1}:")
        print(f"  Results Folder: {row.get('results_folder', 'N/A')}")
        print(f"  Strike Distance %: {row.get('strike_distance_pct', 'N/A')}")
        print(f"  Max Premium %: {row.get('max_total_premium_pct', 'N/A')}")
        print(f"  Target Multiplier: {row.get('target_multiplier', 'N/A')}")
        print(f"  Window: {row.get('window_start', 'N/A')} - {row.get('window_finish', 'N/A')}")
        print(f"  Total Trades: {row.get('total_trades', 'N/A')}")
        print(f"  Profit Rate: {row.get('profit_rate', 'N/A'):.2f}%")
        print(f"  Win Rate: {row.get('win_rate', 'N/A'):.2f}%")
        print(f"  Total PnL: {row.get('total_pnl', 'N/A'):.2f}")
    
    return top_df

def filter_by_criteria(df, min_trades=None, min_profit_rate=None, min_win_rate=None):
    """Filter configurations by custom criteria"""
    filtered_df = df.copy()
    
    if min_trades is not None and 'total_trades' in df.columns:
        filtered_df = filtered_df[filtered_df['total_trades'] >= min_trades]
    
    if min_profit_rate is not None and 'profit_rate' in df.columns:
        filtered_df = filtered_df[filtered_df['profit_rate'] >= min_profit_rate]
    
    if min_win_rate is not None and 'win_rate' in df.columns:
        filtered_df = filtered_df[filtered_df['win_rate'] >= min_win_rate]
    
    print(f"\n{'='*80}")
    print(f"FILTERED CONFIGURATIONS")
    print("="*80)
    print(f"Criteria:")
    if min_trades is not None:
        print(f"  Min Trades: {min_trades}")
    if min_profit_rate is not None:
        print(f"  Min Profit Rate: {min_profit_rate}%")
    if min_win_rate is not None:
        print(f"  Min Win Rate: {min_win_rate}%")
    
    print(f"\nMatching Configurations: {len(filtered_df)}")
    
    return filtered_df

def save_filtered_results(df, output_path):
    """Save filtered results to CSV"""
    df.to_csv(output_path, index=False)
    print(f"\n✓ Saved {len(df)} configurations to {output_path}")

def main():
    config_log_path = "backtesting/rv_iv_analysis/results/config_log.csv"
    
    # Load config log
    df = load_config_log(config_log_path)
    
    if df is None:
        return
    
    # Display summary
    display_summary(df)
    
    # Filter by criteria
    print("\n")
    filtered_df = filter_by_criteria(df, min_trades=15)
    
    # Further filter by limit_one_trade == 1
    if 'limit_one_trade' in filtered_df.columns:
        filtered_df = filtered_df[filtered_df['limit_one_trade'] == 1]
        print(f"After filtering limit_one_trade == 1: {len(filtered_df)} configurations")
    
    # Filter by avg_pnl_pct >= 0
    if 'avg_pnl_pct' in filtered_df.columns:
        filtered_df = filtered_df[filtered_df['avg_pnl_pct'] >= 0]
        print(f"After filtering avg_pnl_pct >= 0: {len(filtered_df)} configurations")
    
    # Sort by avg_pnl_pct
    if 'avg_pnl_pct' in filtered_df.columns:
        filtered_df = filtered_df.sort_values('avg_pnl_pct', ascending=False)
        print(f"Sorted by avg_pnl_pct (descending)")
    
    # Display top results
    print(f"\n{'='*80}")
    print(f"TOP CONFIGURATIONS (Min 10 trades, limit_one_trade=1, sorted by avg_pnl_pct)")
    print("="*80)
    
    for idx, (_, row) in enumerate(filtered_df.head(20).iterrows(), 1):
        print(f"\nRank {idx}:")
        print(f"  Results Folder: {row.get('results_folder', 'N/A')}")
        print(f"  Strike Distance %: {row.get('strike_distance_pct', 'N/A')}")
        print(f"  Max Premium %: {row.get('max_total_premium_pct', 'N/A')}")
        print(f"  Target Multiplier: {row.get('target_multiplier', 'N/A')}")
        print(f"  Window: {row.get('window_start', 'N/A')} - {row.get('window_finish', 'N/A')}")
        print(f"  Total Trades: {row.get('total_trades', 'N/A')}")
        print(f"  Avg PnL %: {row.get('avg_pnl_pct', 'N/A'):.2f}%")
        print(f"  Profit Rate: {row.get('profit_rate', 'N/A'):.2f}%")
        print(f"  Win Rate: {row.get('win_rate', 'N/A'):.2f}%")
        print(f"  Total PnL: {row.get('total_pnl', 'N/A'):.2f}")
    
    # Save filtered results
    if len(filtered_df) > 0:
        output_path = "filtered_configs.csv"
        save_filtered_results(filtered_df, output_path)
    
    # # Show top configurations by different metrics
    # print("\n")
    # filter_top_configs(df, metric='profit_rate', top_n=5)
    # 
    # print("\n")
    # filter_top_configs(df, metric='win_rate', top_n=5)
    # 
    # print("\n")
    # filter_top_configs(df, metric='total_pnl', top_n=5)
    # 
    # # Filter by custom criteria
    # print("\n")
    # filtered_df = filter_by_criteria(df, min_trades=10, min_profit_rate=50, min_win_rate=50)

if __name__ == "__main__":
    main()
