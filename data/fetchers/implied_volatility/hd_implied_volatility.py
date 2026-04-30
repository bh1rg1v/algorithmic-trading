"""Implied volatility data fetcher from Sensibull API."""
import json
import os

import pandas as pd
import requests

def fetch_and_save_iv_data(input_csv, output_folder):
    """Fetch implied volatility data and save to CSV files.
    
    Fetches implied volatility (IV) history and near-expiry futures OHLC 
    data for symbols listed in the input CSV, calculates IV Rank and 
    IV Percentile, and saves the processed data to CSV files.

    Notes:
    - The OHLC data corresponds to near-expiry futures contracts, 
      not spot prices.
    - IV Rank and IV Percentile are calculated using expanding historical 
      windows to avoid lookahead bias.

    Args:
        input_csv (str): Path to the input CSV containing symbol names.
        output_folder (str): Path to folder where output CSV files 
                           will be saved.
    """

    # Read the list of symbols from the input CSV file
    df_symbols = pd.read_csv(input_csv)

    # Create the output directory if it doesn't exist
    os.makedirs(output_folder, exist_ok=True)

    # Loop through each unique symbol
    for symbol in df_symbols["SYMBOL"].dropna().unique():
        symbol = symbol.strip()

        # API endpoint to fetch IV and near-expiry futures OHLC data
        url = f"https://api.sensibull.com/v1/iv_graph/{symbol}?"
        response = requests.get(url)

        if response.status_code == 200:
            data = response.json()

            # Extract IV history and near-expiry futures OHLC data from the response
            iv_history = data.get("iv_history", {})
            ohlc_data = data.get("ohlc_data", {})

            # Convert IV history to a DataFrame
            df_iv = pd.DataFrame(list(iv_history.items()), 
                               columns=["Date", "IV"])

            # Convert OHLC data to a DataFrame
            ohlc_rows = []
            for date, ohlc in ohlc_data.items():
                if isinstance(ohlc, str):
                    ohlc = json.loads(ohlc)  # If OHLC is a JSON string, parse it
                row = {
                    "Date": date,
                    "Open": ohlc.get("open"),
                    "High": ohlc.get("high"),
                    "Low": ohlc.get("low"),
                    "Close": ohlc.get("close"),
                }
                ohlc_rows.append(row)

            df_ohlc = pd.DataFrame(ohlc_rows)

            # Merge IV and OHLC DataFrames on Date
            df_final = pd.merge(df_iv, df_ohlc, on="Date", how="outer")

            # Clean and preprocess IV values
            df_final["IV"] = pd.to_numeric(df_final["IV"], errors="coerce")
            df_final["IV"] = df_final["IV"].fillna(-1)

            # Function to calculate current IV Rank using all past data
            def calculate_rank(expanding_series):
                if len(expanding_series) > 0:
                    return (expanding_series.rank(ascending=False, 
                                                 method='dense').iloc[-1])
                return 0

            # Apply IV Rank calculation
            df_final["Rank"] = (df_final["IV"].expanding()
                               .apply(calculate_rank, raw=False))
            df_final["Rank"] = df_final["Rank"].fillna(0).astype(int)

            # Function to calculate current IV Percentile using all past data
            def calculate_percentile(expanding_series):
                if len(expanding_series) > 0:
                    return expanding_series.rank(pct=True).iloc[-1] * 100
                return 0

            # Apply IV Percentile calculation
            df_final["IV Percentile"] = (df_final["IV"].expanding()
                                       .apply(calculate_percentile, 
                                              raw=False))
            df_final["IV Percentile"] = df_final["IV Percentile"].round(2)

            # Reorder columns for final output
            df_final = df_final[["Date", "Open", "High", "Low", "Close", 
                               "IV", "Rank", "IV Percentile"]]

            # Save the final DataFrame to CSV
            output_file = f"{output_folder}/{symbol}.csv"
            df_final.to_csv(output_file, index=False)

            print(f"Data has been saved successfully for {symbol}.")
        else:
            print(f"Failed to fetch data for {symbol}. "
                  f"Status code: {response.status_code}.")

    print("\nAll symbols have been processed successfully.\n")


if __name__ == "__main__":
    input_csv = r"data\fetchers\implied_volatility\nse_fno_tickers.csv"

    local_output = "data/storage/raw/implied-volatility"
    drive_output = r"G:\My Drive\public\paid\data\implied volatility"

    output_folder = drive_output
    fetch_and_save_iv_data(input_csv, output_folder)
