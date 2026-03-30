# Summary

The backtest includes the following phases along with conclusionns

1) NIFTY moves by 1% from the it's spot price every week... it would be either up/down, this happens 90% of the time.
    - the rv_iv_analysis.py does the work, it helps us to calculate the weekly moves and rank them in percentiles
    - our goal is to capture that 1% move with long straddles.

2) I have backtested the idea of setting up long straddles on index (NIFTY)
    - in order to find the opportunities that are cheap (low IV), I have sticked to a defined amount to buy the options.
    - for a defined configuration (RR, Trade Setup Cost, etc), I have got a result with an avg pnl of 53% on each trade.
    - out of 76 expires that are backtested, found 32 trades (16 expires).
    - the backtest.py helps us to do everything to completely backtest the idea on the historical options data

The following documentation explains the phase 1 defined above in detail.

# Weekly Volatility Analysis for Options Trading

## Overview
A systematic approach to analyze weekly price movements in indices and stocks to identify profitable options trading opportunities. The analysis reveals that 90% of the time, markets move more than 1% from Friday Close Price to Thursday Close Price (in the next week), creating consistent opportunities for long straddle/strangle strategies.

## Research Methodology

### 1. Historical Data Analysis
- **Dataset**: 28 years of Nifty50 data (1996-2024) - expandable to all indices and stocks
- **Time Frame**: Friday close to Thursday close weekly cycles
- **Sample Size**: 1,400+ weekly periods for robust statistical significance

### 2. Core Measurements

#### Absolute Change Calculation
```
Friday Close Price = Close price of index/stock in the current week, on weekend.    (Eg : Feb 06 2026 - Friday)
Thursday Close Price = Close price of index/stock in the next week, on expiry day.  (Eg : Feb 12 2026 - Thursday)
```
```
Absolute Change = |Thursday Close Price - Friday Close Price| / Friday Close Price * 100
```
- Measures directional movement regardless of up/down
- Captures the actual realized volatility over the week
- Forms basis for options strategy profitability analysis

#### Peak Change Calculation
```
High =  All time high price of index/stock in the next 4 trading sessions (till expiry).
Low  =  All time low  price of index/stock in the next 4 trading sessions (till expiry).
```
```
Peak Change = MAX(|High - Friday Close|, |Low - Friday Close|) / Friday Close * 100
```
- Identifies maximum intraday movement during the week
- Critical for options exit timing and profit maximization
- Reveals true volatility potential beyond close-to-close moves

### 3. Statistical Framework

#### Percentile Distribution Analysis
- **90th Percentile**: Extreme volatility events (>3% moves)
- **75th-90th**: High volatility periods (2-3% moves)
- **50th-75th**: Normal volatility range (1.5-2% moves)
- **25th-50th**: Moderate volatility (1-1.5% moves)
- **Bottom 10th**: Low volatility periods (<1% moves)

#### Key Finding
**90% of weeks show >1% absolute movement from Friday to Thursday**

## Options Trading Strategy

### 1. Long Strangle Setup
- **Entry Day**: Friday close (when IV typically bottoms out)
- **Strike Selection**: 0.5% OTM calls and puts from ATM
- **Rationale**: Capture the expected 1% weekly movement
- **IV Advantage**: Enter when implied volatility is at weekly lows

### 2. Strategy Logic
```
Friday Close Price = 100
Call Strike = 100.5 (0.5% OTM)
Put Strike = 99.5 (0.5% OTM)

Profit Scenarios:
- If Thursday close > 101 or < 99 → Profitable
- Historical probability: 90% of weeks
```

### 3. Risk-Reward Profile
- **Maximum Risk**: Premium paid for both options
- **Profit Potential**: Unlimited (theoretically)
- **Breakeven**: Strike ± premium paid
- **Success Rate**: 90% based on historical analysis

## Data Processing Pipeline

#### Input Requirements
```
- Historical OHLCV data (I would recommend data of atleast 10 years...)
- EOD data would be enough for analysis part.
- We would need the historical option data to conduct a proper backtest.
```

#### Analysis Steps
```
1. EXTRACT → Friday close to Thursday close periods
2. CALCULATE → Absolute & Peak Change Percentages
3. RANK → Percentile distribution analysis
4. VALIDATE → Statistical significance testing
5. BACKTEST → Historical options data validation (pending)
6. FORWARDTEST → A better alternative if we don't have options data
```

## Key Research Findings

### 1. Nifty50 Analysis (1996-2024)
- **Average Absolute Change**: ~1.8% per week
- **Average Peak Change**: ~2.5% per week
- **90% Probability**: Weekly movement >1% from Friday to Thursday
- **Consistency**: Pattern holds across different market cycles

### 2. Volatility Patterns
- **Friday IV Crush**: Implied volatility typically lowest at Friday close
- **Weekly Expansion**: Volatility builds throughout the week
- **Seasonal Effects**: Higher volatility during earnings/event weeks
- **Market Regime Independence**: Pattern persists in bull/bear markets

### 3. Strategy Validation Requirements
```
Next Steps:
1. Collect historical options data for backtesting
2. Calculate actual premium costs vs profits
3. Factor in transaction costs and slippage
4. Test across different market conditions
5. Expand analysis to other indices and stocks
```

## Practical Implementation

### 1. Universal Application
- **Indices**: Nifty50, BankNifty, Sensex, sectoral indices
- **Large Cap Stocks**: High liquidity stocks with active options
- **Mid Cap Stocks**: Stocks with sufficient options volume
- **International Markets**: Adaptable to global indices

### 2. Entry Criteria
- **Timing**: Friday close entries for optimal IV conditions
- **Liquidity**: Ensure sufficient options volume and tight spreads
- **Volatility Check**: Confirm current IV is below historical average
- **Market Conditions**: Avoid major event weeks (earnings, policy announcements)

### 3. Risk Management
- **Position Sizing**: Risk only 1-2% of capital per trade
- **Stop Loss**: Exit if premium decays without movement
- **Profit Taking**: Close positions when movement exceeds 1.5%

## Statistical Validation

### 1. Sample Robustness
- **28-Year Dataset**: 1,400+ weekly observations
- **Market Cycles**: Includes multiple bull/bear cycles
- **Crisis Periods**: 2008 financial crisis, COVID-19, etc.
- **Statistical Significance**: 90% confidence level achieved

### 2. Expandable Framework
```python
# Configuration for any instrument
START_DAY = "Friday"     # Entry day
END_DAY = "Thursday"     # Exit analysis day
STRIKE_DISTANCE = 0.5   # Percentage OTM for strikes
MIN_MOVEMENT = 1.0      # Target movement percentage
```

### 3. Backtesting Requirements
```
Pending Validation:
- Historical options premium data
- Greeks behaviour should be taken care of
- Slippage calculations inclusions
- Generating trades, and analysing them
```

## Expected Outcomes

### 1. Strategy Performance Metrics
- **Win Rate**: Expected 90% based on movement analysis
- **Average Profit**: Target 50-100% return on premium
- **Maximum Loss**: Limited to premium paid
- **Sharpe Ratio**: High risk-adjusted returns expected

### 2. Market Behavior Insights
- **IV Patterns**: Friday lows, mid-week highs
- **Movement Consistency**: 90% weekly movement >1%
- **Seasonal Effects**: Identify high-probability periods
- **Regime Analysis**: Strategy performance across market conditions

## Plausible Enhancements

### 1. Multi-Asset Analysis
- Expand to all NSE indices and liquid stocks
- International market adaptation
- Sector-specific volatility patterns
- Cross-asset correlation analysis

### 2. Strategy Optimization
- Dynamic strike selection based on IV levels
- Multi-timeframe analysis (2-day, 3-day cycles)
- Volatility forecasting models
- Integrating ML models to predict change in IV

### 3. Risk Management Evolution
- Real-time IV monitoring systems
- Automated position sizing algorithms
- Dynamic hedging strategies
- Portfolio-level risk optimization

---