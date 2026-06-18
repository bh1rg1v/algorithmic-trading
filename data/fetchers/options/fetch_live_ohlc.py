import os
from dotenv import load_dotenv
import requests
import json
import pandas as pd
import time

'''
This script fetches Option Chain data (CE and PE) for a given underlying instrument.
It first retrieves the valid expiry dates using the option/contract API, 
and then fetches the market data and Greeks using the option/chain API.
'''

# The user requested to save the data in a 'temp_data' folder in the project root.
# Based on the file path provided, the project root is 'd:\github\algorithmic-trading'.
output_dir = r"d:\github\algorithmic-trading\temp_data"
os.makedirs(output_dir, exist_ok=True)

load_dotenv()

token1 = os.getenv("UPSTOX_TOKEN_1")
token2 = os.getenv("UPSTOX_TOKEN_2")
token3 = os.getenv("UPSTOX_TOKEN_3")
token4 = os.getenv("UPSTOX_TOKEN_4")
token5 = os.getenv("UPSTOX_TOKEN_5")

ACCESS_TOKENS = [token for token in [token1, token2, token3, token4, token5] if token]

if not ACCESS_TOKENS:
    raise ValueError("No Upstox access tokens found in .env file. Please set UPSTOX_TOKEN_1, etc.")

current_token_index = 0
cycle_start_time = time.time()

def get_headers():
    """Returns headers for the API request with the current access token."""
    if not ACCESS_TOKENS[current_token_index]:
        raise ValueError(f"Access token at index {current_token_index} is None or empty.")
    return {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {ACCESS_TOKENS[current_token_index]}',
        'Accept': 'application/json'
    }

def switch_token():
    """Switches to the next available access token."""
    global current_token_index, cycle_start_time
    
    current_token_index += 1
    
    if current_token_index >= len(ACCESS_TOKENS):
        cycle_end_time = time.time()
        elapsed = cycle_end_time - cycle_start_time
        
        # This logic is for long-running jobs, might not be strictly necessary
        # for a single call, but kept for robustness.
        if elapsed < 1800:  # 30 minutes
            wait_time = 1800 - elapsed
            print(f"\nAll {len(ACCESS_TOKENS)} tokens exhausted. Waiting {wait_time:.2f} seconds to complete 30-minute cycle...")
            time.sleep(wait_time)
        
        current_token_index = 0
        cycle_start_time = time.time()
        print(f"\nRestarting cycle with Token 1")
    else:
        print(f"\nSwitching to Token {current_token_index + 1}/{len(ACCESS_TOKENS)}. Waiting 5 seconds...")
        time.sleep(5)

def get_expiries(instrument_key):
    """
    Fetches all valid expiry dates for a given instrument key using the option/contract API.
    """
    url = 'https://api.upstox.com/v2/option/contract'
    params = {
        'instrument_key': instrument_key
    }
    
    try:
        response = requests.get(url, params=params, headers=get_headers())
        
        if response.status_code == 429:
            print(f"Rate limited while fetching expiries. Switching token...")
            switch_token()
            response = requests.get(url, params=params, headers=get_headers())
            
        if response.status_code == 200:
            data = response.json().get('data', [])
            # Extract unique expiries and sort them
            expiries = sorted(list(set([contract['expiry'] for contract in data if 'expiry' in contract])))
            return expiries
        else:
            print(f"Error fetching expiries: {response.status_code}")
            print(response.text)
            return []
    except Exception as e:
        print(f"Error getting expiries: {e}")
        return []

def fetch_and_save_option_chain(instrument_key, expiry_date):
    """
    Fetches the option chain (CE and PE) for an instrument and expiry using the option/chain API, 
    then flattens the data and saves it to a CSV file.
    """
    
    url = 'https://api.upstox.com/v2/option/chain'
    
    params = {
        'instrument_key': instrument_key,
        'expiry_date': expiry_date
    }

    print(f"Fetching Option Chain data for: {instrument_key} (Expiry: {expiry_date})")

    try:
        response = requests.get(url, params=params, headers=get_headers())

        if response.status_code == 429:
            print(f"Rate limited on option chain. Switching token...")
            switch_token()
            response = requests.get(url, params=params, headers=get_headers())

        if response.status_code == 200:
            data = response.json().get('data', [])

            if data:
                rows = []
                for item in data:
                    strike = item.get('strike_price')
                    underlying_spot = item.get('underlying_spot_price')
                    pcr = item.get('pcr')

                    for opt_type, opt_key in [('CE', 'call_options'), ('PE', 'put_options')]:
                        if opt_key in item and item[opt_key]:
                            opt_data = item[opt_key]
                            market_data = opt_data.get('market_data', {})
                            greeks = opt_data.get('option_greeks', {})

                            row = {
                                'expiry': expiry_date,
                                'strike_price': strike,
                                'option_type': opt_type,
                                'instrument_key': opt_data.get('instrument_key'),
                                'underlying_spot_price': underlying_spot,
                                'pcr': pcr,
                                'ltp': market_data.get('ltp'),
                                'volume': market_data.get('volume'),
                                'oi': market_data.get('oi'),
                                'close_price': market_data.get('close_price'),
                                'bid_price': market_data.get('bid_price'),
                                'bid_qty': market_data.get('bid_qty'),
                                'ask_price': market_data.get('ask_price'),
                                'ask_qty': market_data.get('ask_qty'),
                                'prev_oi': market_data.get('prev_oi'),
                                'vega': greeks.get('vega'),
                                'theta': greeks.get('theta'),
                                'gamma': greeks.get('gamma'),
                                'delta': greeks.get('delta'),
                                'iv': greeks.get('iv'),
                                'pop': greeks.get('pop')
                            }
                            rows.append(row)

                if rows:
                    df = pd.DataFrame(rows)
                    # Sort by Strike Price and Option Type (CE before PE)
                    df = df.sort_values(by=['strike_price', 'option_type'])
                    
                    # Save to CSV
                    safe_instrument_key = instrument_key.replace('|', '_').replace(':', '_').replace(' ', '_')
                    filename = os.path.join(output_dir, f"option_chain_{safe_instrument_key}_{expiry_date}.csv")
                    df.to_csv(filename, index=False)
                    
                    print(f"Successfully fetched and saved data to {filename}")
                    print(f"Total option contracts retrieved: {len(df)}")
                else:
                    print("Parsed option chain correctly, but no contracts found.")
            else:
                print(f"No option chain data found for '{instrument_key}' for expiry {expiry_date}.")
        else:
            print(f"Error fetching option chain for {instrument_key}: {response.status_code}")
            try:
                print(f"Response: {response.json()}")
            except json.JSONDecodeError:
                print(f"Response: {response.text}")

    except requests.exceptions.RequestException as e:
        print(f"A network error occurred: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    nifty_instrument_key = 'NSE_INDEX|Nifty 50'
    
    print(f"Fetching available expiry dates for {nifty_instrument_key}...")
    expiries = get_expiries(nifty_instrument_key)
    
    if expiries:
        print(f"Found {len(expiries)} expiries. Fetching option chain for the nearest expiry: {expiries[0]}")
        fetch_and_save_option_chain(nifty_instrument_key, expiries[0])
        
        # Uncomment the loop below to fetch data for ALL available expiries:
        # for expiry in expiries:
        #     fetch_and_save_option_chain(nifty_instrument_key, expiry)
    else:
        print("No expiries found. Exiting.")