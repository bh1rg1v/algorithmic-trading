import requests
import os
import pandas as pd
from datetime import datetime, timedelta

from dotenv import load_dotenv

load_dotenv()

# Base URL
base_url = "https://api.upstox.com/v3/historical-candle"

# Path parameters
instrument_keys = {
    "NIFTY" : "NSE_INDEX|Nifty 50",
    "SENSEX": "BSE_INDEX|SENSEX"
}
interval = "minutes"
unit = "1"

to_date = datetime.today()
from_date = datetime.strptime("2022-01-01", "%Y-%m-%d")

access_token = os.getenv("UPSTOX_ACCESS_TOKEN")

for name, instrument_key in instrument_keys.items():
    
    print(f"\nFetching data for {name}...")
    all_candles = []
    
    current_end = to_date
    while current_end >= from_date:
        current_start = max(current_end - timedelta(days=28), from_date)
        
        url = f"{base_url}/{instrument_key}/{interval}/{unit}/{current_end.strftime('%Y-%m-%d')}/{current_start.strftime('%Y-%m-%d')}"
        
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {access_token}"
        }
        
        response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            data = response.json().get("data", {}).get("candles", [])
            if not data:
                print(f"No more data available before {current_start.strftime('%Y-%m-%d')}")
                break
            all_candles.extend(data)
            print(f"Fetched {len(data)} candles from {current_start.strftime('%Y-%m-%d')} to {current_end.strftime('%Y-%m-%d')}")
        else:
            print(f"Error: {response.status_code} - {response.text}")
            print(f"Stopping at {current_start.strftime('%Y-%m-%d')}")
            break
        
        current_end = current_start - timedelta(days=1)
    
    if all_candles:
        df = pd.DataFrame(all_candles, columns=["Date", "Open", "High", "Low", "Close", "Volume", "OI"])
        df = df.iloc[::-1].reset_index(drop=True)
        
        output_folder = r"data\storage\raw\index"
        os.makedirs(output_folder, exist_ok=True)
        output_file = os.path.join(output_folder, f"{name}.csv")
        
        df.to_csv(output_file, index=False)
        print(f"Total {len(df)} candles saved to {output_file}")
    else:
        print(f"No data fetched for {name}")