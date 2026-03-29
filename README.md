## Most Useful Things (in this repo)

### Historical Data Links
  - data\storage\raw\equity\README.md     [[Link](https://www.jiocloud.com/l/?u=nJeSTwHnU5GtuaLD7aYu97WZUO0E-HJCtLqWE-q4gD3VbsX1gBXZVMyTO5OGzLd-hkW)]
  - data\storage\raw\options\README.md    [[Link](https://drive.google.com/drive/folders/1QM_NSWSF0ny5fv9BxPXmDxG6fh5BftRY?usp=sharing)]


the above README files contains the details relevant to the respective datasets.

### Data Fetching Modules - **`data/fetchers/`**

- **`equity/hd_equity.py`**
  - helps you fetching top 2000 stocks OHLCV data from Apr 2015
  - data is fetched from zerodha's unoffical API
  - you'll need an account with zerodha to fetch the data

- **`options/hd_options.py`**
  - helps you fetching index options data from Oct 2024
  - data is fetched using upstox API
  - you'll need account with upstox to fetch the data
  - working on the script to fetch stock options data, will update it when done.

- **`index/hd_index.py`**
  - helps you fetching index (NIFTY & SENSEX) spot data from Jan 2022
  - data is fetched using upstox API
  - you'll need account with upstox to fetch the data

- **`implied_volatility/hd_implied_volatility.py`**
  - helps you fetching IV data of top 100 stocks & nifty index
  - data is fetched from sensibull's unofficial API
  - you don't need any account to fetch this data

- **`fundamentals/hd_fundamentals.py`**
  - helps you fetching fundamental metric data for about 2500 stocks
  - data is scraped from screener.in, be respectful with rate limits.
  - you don't need any account to fetch this data
  
- **Usage**
  - currently, you need to fork the whole repo to use the above data fetching modules.
  - I will try to make things modular in the above 5 mentioned scripts, in the near future.
  - So that, you don't need to fork the whole repo.

- **Note**
  - If you found any file to be corrupt, not working or giving some trouble. Please raise an issuse or drop a dm.
  - I am open to collaboration, kindly drop a dm to discuss any of your ideas or my ideas.
  - The below details are a bit older, I need to update it :)



## Repository Architecture

### **`broker/`** - Broker Integration
- **`shoonya/`** - Shoonya API implementation (basicfunctions.py, config.py)

### **`data/`** - Data Management
- **`fetchers/`** - Data fetching modules (equity, fundamentals, implied_volatility)
- **`storage/`** - Data storage with symbol files (BFO, BSE, NFO, NSE) and tokens.csv
  - **`raw/`** - Raw market data
  - **`processed/`** - Processed data

### **`projects/`** - Trading Projects
Individual trading projects and strategies:
- **`p1-stock-action-classification-markov/`** - Markov chain stock classification
- **`p2-rv-iv-analysis/`** - Realized vs Implied volatility analysis
- **`p3-automated-trading-bot/`** - Automated scalping bot

### **`backtesting/`** - Backtesting Modules
Backtesting implementations for each strategy:
- **`rv-iv-analysis/`** - Volatility analysis backtests with results
- **`scalper/`** - Scalper strategy backtests
- **`stock-action-classification-markov/`** - Markov model backtests

### **`forward-testing/`** - Forward Testing
Forward testing modules and results.

### **`live/`** - Live Trading
Live trading implementations and configurations.

### **`utilities/`** - Utility Scripts
- **`telegram_bot.py`** - Telegram notification bot

### **Root Files**
- **`requirements.txt`** - Python dependencies
- **`.env.example`** - Environment variables template
- **`.gitignore`** - Git ignore rules
- **`README.md`** - This file