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



## Repository Architecture

### **`broker/`** - Broker Integration
- **`shoonya/`**
  - `basicfunctions.py` - Core Shoonya API wrapper functions
  - `config.py` - Shoonya API configuration and authentication
- **`upstox/`**
  - `instruments/instruments.py` - Upstox instrument data management

### **`data/`** - Data Management
- **`fetchers/`** - Data fetching modules
  - **`equity/`**
    - `hd_equity.py` - Fetch top 2000 stocks OHLCV data from Zerodha API (Apr 2015+)
  - **`fundamentals/`**
    - `hd_fundamentals.py` - Scrape fundamental metrics for 2500+ stocks from screener.in
  - **`implied_volatility/`**
    - `hd_implied_volatility.py` - Fetch IV data for top 100 stocks from Sensibull API
  - **`index/`**
    - `hd_index.py` - Fetch NIFTY & SENSEX spot data from Upstox API (Jan 2022+)
  - **`options/`**
    - `hd_options.py` - Fetch index options data from Upstox API (Oct 2024+)
- **`storage/`** - Data storage with symbol files and tokens
  - **`raw/`** - Raw market data (equity, options, index)
    - **`nifty50/`**
      - `nifty.py` - NIFTY index data processing
      - `nifty50.py` - NIFTY 50 constituent stocks processing
      - `nifty50_dailydata.py` - Daily NIFTY 50 data aggregation
  - **`processed/`** - Processed and cleaned data

### **`backtesting/`** - Backtesting Modules
- **`markov_models/`** - Markov chain stock classification backtests
  - `backtest_events.py` - Event-based backtesting for Markov models
  - `markov_model1.py` - Primary Markov model implementation
  - `run_markov_analysis.py` - Execute Markov analysis backtests
  - **`ml/`** - Machine learning enhanced Markov models
    - `bt_ml_gb.py` - Gradient Boosting classifier backtest
    - `bt_ml_rf.py` - Random Forest classifier backtest
- **`markov_models_org/`** - Original Markov model implementations (archived)
- **`previous_version/`** - Legacy backtesting scripts
  - `backtesting_utility.py` - Utility functions for backtesting
  - `bt-sharpe-old.py` - Old Sharpe ratio optimization
  - `bt-sharpe-portfolio.py` - Portfolio-level Sharpe optimization
  - `bt-sharpe.py` - Current Sharpe ratio backtesting
  - `bt-trend-following-1.py` - Trend following strategy v1
  - `bt-trend-following-2.py` - Trend following strategy v2
  - `bt-trend-following.py` - Main trend following backtest
  - `BT.py` - Base backtesting framework
  - `stock_risk_metrics.py` - Calculate stock risk metrics
- **`rv_iv_analysis/`** - Realized vs Implied volatility analysis
  - `backtest.py` - Grid search backtest with multiprocessing and caching for RV-IV strategy
  - `main.py` - Real-time RV-IV analysis scheduler with Telegram alerts
  - `rv_iv_analysis.py` - Core volatility analysis and percentile calculations
  - `track_prices.py` - Live price tracking and straddle cost calculation
  - **`results/`** - Backtest results with config_log.csv tracking all parameter combinations
- **`scalper/`**
  - `scalper.py` - Scalping strategy backtest
- **`volatility/`**
  - `bt_realized_volatility.py` - Realized volatility backtesting

### **`forward_testing/`** - Forward Testing
- **`markov_models/`** - Forward testing for Markov models
- **`rv_iv_analysis/`**
  - `rv_iv_analysis.py` - Live forward testing for RV-IV strategy

### **`live/`** - Live Trading
Live trading implementations and configurations

### **`projects/`** - Trading Projects
- **`p1-stock-action-classification-markov/`** - Markov chain stock classification
- **`p2-rv-iv-analysis/`** - Realized vs Implied volatility analysis
  - `main.py` - Project main entry point
  - `rv_iv_analysis.py` - Volatility analysis implementation
  - `track_prices.py` - Price tracking module
- **`p3-automated-trading-bot/`** - Automated scalping bot
  - `scalper.py` - Scalping bot implementation

### **`others/`** - Miscellaneous
- **`books/`** - Trading and finance reference books
- **`process_aif_funds_list/`** - AIF (Alternative Investment Funds) data processing
  - `add_aif_data.py` - Parse and add AIF entries from text to CSV
  - `extract_state_city.py` - Extract state and capital city from AIF addresses
  - `aif_list.csv` - AIF funds database
  - `aif_list_with_location.csv` - AIF data with location columns

### **`utilities/`** - Utility Scripts
- `telegram_bot.py` - Telegram notification bot for trade alerts

### **`recyclebin/`** - Archived Data
Old analysis and historical data files

### **Root Files**
- `filter.py` - Filter and analyze backtest config_log.csv results by criteria
- `config_log.csv` - Log of all backtest configurations and results
- `filtered_configs.csv` - Filtered backtest results meeting specified criteria
- `requirements.txt` - Python dependencies
- `.env.example` - Environment variables template
- `.gitignore` - Git ignore rules
- `Dockerfile` - Docker container configuration
- `README.md` - This file