import requests
import gzip
import json
import os
import pandas as pd

"""

Links to download the instruments list provided by UPSTOX API

Complete    -   https://assets.upstox.com/market-quote/instruments/exchange/complete.json.gz

NSE         -   https://assets.upstox.com/market-quote/instruments/exchange/NSE.json.gz
BSE         -   https://assets.upstox.com/market-quote/instruments/exchange/BSE.json.gz
MCX         -   https://assets.upstox.com/market-quote/instruments/exchange/MCX.json.gz

NSE MIS     -   https://assets.upstox.com/market-quote/instruments/exchange/NSE_MIS.json.gz
BSE MIS     -   https://assets.upstox.com/market-quote/instruments/exchange/BSE_MIS.json.gz

MTF         -   https://assets.upstox.com/market-quote/instruments/exchange/MTF.json.gz
Suspended   -   https://assets.upstox.com/market-quote/instruments/exchange/suspended-instrument.json.gz

Note
    1) These files are updated around 06:00 AM by UPSTOX

What does this program do ???

    Process 1 - Download complete list of instruments with their meta data and stores in a csv file

    Process 2 - Filter and creates CSVs for specific segments

                a) INDEX
                b) FNO
                c) MTF
                d) EQUITY

    Process 3 - 

"""

# output folder path & check existence
output_folder = "broker/upstox/instruments"
os.makedirs(output_folder, exist_ok=True)

url = "https://assets.upstox.com/market-quote/instruments/exchange/complete.json.gz"
response = requests.get(url)

# Save and extract
gz_path = os.path.join(output_folder, "complete.json.gz")
json_path = os.path.join(output_folder, "complete.json")

with open(gz_path, "wb") as f:
    f.write(response.content)

with gzip.open(gz_path, "rb") as f_in:
    with open(json_path, "wb") as f_out:
        f_out.write(f_in.read())

# Delete the .gz file
os.remove(gz_path)

# print(f"Downloaded and extracted to: {json_path}")

with open(r"broker\upstox\instruments\complete.json", "r") as f:
    data = json.load(f)

df = pd.DataFrame(data)
df.to_csv(os.path.join(output_folder, "complete.csv"), index=False)

df = pd.read_csv(os.path.join(output_folder, "complete.csv"))

# Filtering and create a seperate csv for index instruments

df_filtered = df[df['segment'].isin(['NSE_INDEX', 'BSE_INDEX'])]
df_filtered = df_filtered.dropna(axis=1, how='all')
path = os.path.join(output_folder, "index.csv")
df_filtered.to_csv(path, index=False)

# Filtering and create a seperate csv for fno instruments

df_filtered = df[df['segment'].isin(['NSE_FO', 'BSE_FO'])]
df_filtered = df_filtered.dropna(axis=1, how='all')
path = os.path.join(output_folder, "fno.csv")
df_filtered.to_csv(path, index=False)

# Filtering and create a seperate csv for mtf instruments

df_filtered = df[df['mtf_enabled'].notna()]
df_filtered = df_filtered.dropna(axis=1, how='all')
path = os.path.join(output_folder, "mtf.csv")
df_filtered.to_csv(path, index=False)

# Filtering and create a seperate csv for equity instruments

df_filtered = df[df['segment'].isin(['NSE_EQ', 'BSE_EQ'])]
df_filtered = df_filtered.dropna(axis=1, how='all')
path = os.path.join(output_folder, "equity.csv")
df_filtered.to_csv(path, index=False)

# Filtering and create a seperate csv for mcx instruments

df_filtered = df[df['exchange'] == 'MCX']
df_filtered = df_filtered.dropna(axis=1, how='all')
path = os.path.join(output_folder, "mcx.csv")
df_filtered.to_csv(path, index=False)

# Write code for downloading or filtering the suspended instruments.