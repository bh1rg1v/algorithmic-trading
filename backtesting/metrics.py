"""

1) Total Returns:

    - Total Return
    - CAGR
    - Average Trade Return
    - Median Trade Return
    - Monthly Returns
    - Yearly Returns

2) Risk Metrics:

    - Maximum Drawdown
    - Average Drawdown
    - Volatility (Standard Deviation)
    - Downside Volatility (Sortino)

3) Risk Adjusted Returns:

    - Sharpe Ratio
    - Sortino Ratio
    - Calmar Ratio
    - MAR Ratio
    - Omega Ratio

4) Trade Statistics:

    - Number of Trades
    - Win Rate
    - Loss Rate
    - Average Winner
    - Average Loser
    - Largest Winner
    - Largest Loser
    - Median Winner
    - Median Loser

5) Expectancy Metrics:

    - Expectancy
    - Reward/Risk Ratio: AvgWin/AvgLoss
    - Profit Factor: GrossProfit/GrossLoss

Capital Efficiency Metric

    - Return on Capital
    - Capital Utilization %
    - Return per Margin Used

6) Equity Curve Metrics

    - Equity Curve
    - Percentage Positive Months
    - Consecutive Winning Months
    - Consecutive Losing Months

Option Specific Metrics

    - Premium Decay
    - Average Holding Time
    - Average days-to-expiry at Entry
    - Performance by DTE Bucket
    - Performance by Moneyness
    - Premium Capture % (If target move was ₹100 and option captured ₹40. 40/100=40%)
    - Market Regime Metrics (Bull, Bear, Sideways, High/Low Volatile)

Benchmark Comparison

    - Benchmark Returns (Nifty 50, Bank Nifty, etc.)
    - Alpha
    - Beta
    - R-Squared
    - Information Ratio

7) Tail Risk Metrics

    - Value at Risk (VaR)
    - Conditional Value at Risk (CVaR)
    - Worst Trade
    - Worst Day
    - Worst Week
    - Worst Month

Position Sizing Metrics

    - Kelly %
    - Risk of Ruin
    - Largest Consecutive Losses

"""

import os
import json
import numpy as np
import pandas as pd


# ============================================================
# CONFIG
# ============================================================

INITIAL_CAPITAL = 80_000

TRADES_PATH = r"D:\github\algorithmic-trading\backtesting\rv_iv_analysis\results\RV_IV_Analysis_20260604_101557\trades.csv"

OUTPUT_DIR = r"D:\github\algorithmic-trading\backtesting\rv_iv_analysis\results\RV_IV_Analysis_20260604_101557\metrics"

LOT_SIZE = 65
LOTS = 1


# ============================================================
# LOAD DATA
# ============================================================

def load_data(path):

    df = pd.read_csv(path)

    df["entry_time"] = pd.to_datetime(df["entry_time"])
    df["exit_time"] = pd.to_datetime(df["exit_time"])
    df["expiry"] = pd.to_datetime(df["expiry"])

    # Convert premium points -> rupees
    df["pnl"] = (
        df["pnl"]
        * LOT_SIZE
        * LOTS
    )

    df = df.sort_values("exit_time").reset_index(drop=True)

    return df


# ============================================================
# EQUITY CURVE
# ============================================================

def build_equity_curve(df, initial_capital):

    equity = [initial_capital]

    for pnl in df["pnl"]:
        equity.append(equity[-1] + pnl)

    equity = pd.Series(equity)

    return equity


# ============================================================
# RETURNS METRICS
# ============================================================

def get_return_metrics(df, equity, initial_capital):

    ending_capital = equity.iloc[-1]

    total_return = (
        ending_capital - initial_capital
    ) / initial_capital

    days = (
        df["exit_time"].max()
        - df["entry_time"].min()
    ).days

    years = days / 365.25

    if years > 0:
        cagr = (
            ending_capital / initial_capital
        ) ** (1 / years) - 1
    else:
        cagr = np.nan

    metrics = {
        "Total Return %": total_return * 100,
        "CAGR %": cagr * 100,
        "Average Trade Return %": df["pnl_pct"].mean(),
        "Median Trade Return %": df["pnl_pct"].median(),
    }

    return metrics


# ============================================================
# MONTHLY / YEARLY RETURNS
# ============================================================

def get_period_returns(df):

    monthly = (
        df.groupby(
            df["exit_time"].dt.to_period("M")
        )["pnl"]
        .sum()
        .reset_index()
    )

    yearly = (
        df.groupby(
            df["exit_time"].dt.to_period("Y")
        )["pnl"]
        .sum()
        .reset_index()
    )

    return monthly, yearly


# ============================================================
# DRAWDOWN METRICS
# ============================================================

def get_drawdown_metrics(equity):

    running_max = equity.cummax()

    drawdown = (
        equity - running_max
    ) / running_max

    metrics = {
        "Maximum Drawdown %":
            drawdown.min() * 100,

        "Average Drawdown %":
            drawdown[drawdown < 0].mean() * 100
    }

    return metrics, drawdown


# ============================================================
# RISK METRICS
# ============================================================

def get_risk_metrics(df):

    returns = df["pnl_pct"] / 100

    downside = returns[returns < 0]

    metrics = {
        "Volatility %":
            returns.std() * 100,

        "Downside Volatility %":
            downside.std() * 100
    }

    return metrics


# ============================================================
# RISK ADJUSTED RETURNS
# ============================================================

def get_ratio_metrics(df, drawdown):

    returns = df["pnl_pct"] / 100

    mean_return = returns.mean()

    volatility = returns.std()

    downside = returns[returns < 0]

    downside_vol = downside.std()

    max_dd = abs(drawdown.min())

    sharpe = (
        mean_return / volatility
        if volatility != 0
        else np.nan
    )

    sortino = (
        mean_return / downside_vol
        if downside_vol != 0
        else np.nan
    )

    calmar = (
        mean_return / max_dd
        if max_dd != 0
        else np.nan
    )

    metrics = {
        "Sharpe Ratio": sharpe,
        "Sortino Ratio": sortino,
        "Calmar Ratio": calmar,
        "MAR Ratio": calmar
    }

    return metrics


# ============================================================
# TRADE STATISTICS
# ============================================================

def get_trade_statistics(df):

    winners = df[df["pnl"] > 0]
    losers = df[df["pnl"] < 0]

    metrics = {

        "Number of Trades":
            len(df),

        "Win Rate %":
            len(winners) / len(df) * 100,

        "Loss Rate %":
            len(losers) / len(df) * 100,

        "Average Winner":
            winners["pnl"].mean(),

        "Average Loser":
            losers["pnl"].mean(),

        "Largest Winner":
            winners["pnl"].max(),

        "Largest Loser":
            losers["pnl"].min(),

        "Median Winner":
            winners["pnl"].median(),

        "Median Loser":
            losers["pnl"].median()
    }

    return metrics


# ============================================================
# EXPECTANCY METRICS
# ============================================================

def get_expectancy_metrics(df):

    winners = df[df["pnl"] > 0]
    losers = df[df["pnl"] < 0]

    win_rate = len(winners) / len(df)
    loss_rate = len(losers) / len(df)

    avg_win = winners["pnl"].mean()

    avg_loss = abs(
        losers["pnl"].mean()
    )

    expectancy = (
        win_rate * avg_win
        -
        loss_rate * avg_loss
    )

    rr = avg_win / avg_loss

    profit_factor = (
        winners["pnl"].sum()
        /
        abs(losers["pnl"].sum())
    )

    return {
        "Expectancy": expectancy,
        "Reward Risk Ratio": rr,
        "Profit Factor": profit_factor
    }


# ============================================================
# EQUITY METRICS
# ============================================================

def get_equity_metrics(monthly_returns):

    monthly_returns["month_pnl"] = monthly_returns["pnl"]

    positive_months = (
        monthly_returns["month_pnl"] > 0
    ).mean() * 100

    max_win_streak = 0
    max_loss_streak = 0

    win_streak = 0
    loss_streak = 0

    for pnl in monthly_returns["month_pnl"]:

        if pnl > 0:
            win_streak += 1
            loss_streak = 0

        elif pnl < 0:
            loss_streak += 1
            win_streak = 0

        else:
            win_streak = 0
            loss_streak = 0

        max_win_streak = max(
            max_win_streak,
            win_streak
        )

        max_loss_streak = max(
            max_loss_streak,
            loss_streak
        )

    return {
        "Percentage Positive Months %":
            positive_months,

        "Consecutive Winning Months":
            max_win_streak,

        "Consecutive Losing Months":
            max_loss_streak
    }


# ============================================================
# TAIL RISK
# ============================================================

def get_tail_risk_metrics(df):

    pnl = df["pnl"]

    var95 = np.percentile(
        pnl,
        5
    )

    cvar95 = pnl[pnl <= var95].mean()

    weekly = (
        df.groupby(
            df["exit_time"].dt.to_period("W")
        )["pnl"]
        .sum()
    )

    monthly = (
        df.groupby(
            df["exit_time"].dt.to_period("M")
        )["pnl"]
        .sum()
    )

    return {
        "VaR 95": var95,
        "CVaR 95": cvar95,
        "Worst Trade": pnl.min(),
        "Worst Week": weekly.min(),
        "Worst Month": monthly.min()
    }


# ============================================================
# MAIN
# ============================================================

def main():

    df = load_data(TRADES_PATH)

    equity = build_equity_curve(
        df,
        INITIAL_CAPITAL
    )

    monthly_returns, yearly_returns = (
        get_period_returns(df)
    )

    metrics = {}

    metrics.update(
        get_return_metrics(
            df,
            equity,
            INITIAL_CAPITAL
        )
    )

    dd_metrics, drawdown = (
        get_drawdown_metrics(
            equity
        )
    )

    metrics.update(dd_metrics)

    metrics.update(
        get_risk_metrics(df)
    )

    metrics.update(
        get_ratio_metrics(
            df,
            drawdown
        )
    )

    metrics.update(
        get_trade_statistics(df)
    )

    metrics.update(
        get_expectancy_metrics(df)
    )

    metrics.update(
        get_equity_metrics(
            monthly_returns
        )
    )

    metrics.update(
        get_tail_risk_metrics(df)
    )

    print("\n" + "=" * 60)
    print("BACKTEST METRICS")
    print("=" * 60)

    for k, v in metrics.items():

        if isinstance(v, float):
            print(
                f"{k:<35}: {v:.4f}"
            )
        else:
            print(
                f"{k:<35}: {v}"
            )

    equity_df = pd.DataFrame({
        "equity": equity
    })

    os.makedirs(
        OUTPUT_DIR,
        exist_ok=True
    )

    equity_df.to_csv(
        os.path.join(
            OUTPUT_DIR,
            "equity_curve.csv"
        ),
        index=False
    )

    monthly_returns.to_csv(
        os.path.join(
            OUTPUT_DIR,
            "monthly_returns.csv"
        ),
        index=False
    )

    yearly_returns.to_csv(
        os.path.join(
            OUTPUT_DIR,
            "yearly_returns.csv"
        ),
        index=False
    )

    sorted_trades = (
        df.sort_values(
            by="pnl_pct",
            ascending=False
        )
    )

    sorted_trades.to_csv(
        os.path.join(
            OUTPUT_DIR,
            "trades_sorted_by_pnl_pct.csv"
        ),
        index=False
    )

    with open(
        os.path.join(
            OUTPUT_DIR,
            "metrics.json"
        ),
        "w"
    ) as f:

        json.dump(
            metrics,
            f,
            indent=4,
            default=str
        )


if __name__ == "__main__":
    main()