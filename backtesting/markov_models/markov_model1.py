import pandas as pd

def compute_markov_event_probs(df, milestones=[0.5 * x for x in range(0, 9)], neutral_threshold=0.0025):
    """
    Compute milestone event probabilities for OHLCV data.
    
    Parameters
    ----------
    df : pd.DataFrame
        Must contain columns ['Open', 'High', 'Low', 'Close'] (Volume optional).
    milestones : list of float
        Percent thresholds to evaluate (default: [0.0, 0.5, 1.0, 1.5, 2.0]).
    neutral_threshold : float
        Threshold (fraction of open price) to classify a candle as neutral.
    
    Returns
    -------
    summary : pd.DataFrame
        Table of events with columns:
        ['Event', 'Probability', 'Count']
    """
    # --- Copy to avoid modifying original
    df = df.copy()

    # print(df.head())

    # Previous highs/lows
    df["Prev_High"] = df["High"].shift(1)
    df["Prev_Low"] = df["Low"].shift(1)

    # print()
    # print(df.head())

    # Candle classification
    def classify_candle(o, c):

        if o <= 0:  # Avoid division by zero
            return "Last Neutral"
        
        if abs(c - o) / o < neutral_threshold:
            return "Last Neutral"
            
        return "Last Green" if c > o else "Last Red"

    df["Last_Candle"] = [classify_candle(o, c) for o, c in zip(df["Open"], df["Close"])]
    df["Last_Candle"] = df["Last_Candle"].shift(1)

    print()
    print(df.head())

    # --- Event extraction ---
    records = []
    for i in range(1, len(df)):

        row = df.iloc[i]
        prev_high, prev_low = row["Prev_High"], row["Prev_Low"]

        if pd.isna(prev_high) or pd.isna(prev_low):
            continue
        
        # Skip circuit hitting cases (O == H == L == C)
        if row["Open"] == row["High"] == row["Low"] == row["Close"]:
            continue

        # Check High/Low broken
        if row["High"] >= prev_high:
            ref, ref_level, broken = "Prev_High", prev_high, "High_Broken"
        elif row["Low"] <= prev_low:
            ref, ref_level, broken = "Prev_Low", prev_low, "Low_Broken"
        else:
            continue

        last_candle = row["Last_Candle"]

        # Check milestones
        for j in range(1, len(milestones)-1):

            base, nxt = milestones[j], milestones[j+1]

            # Skip if reference level is zero or invalid
            if ref_level <= 0:
                continue

            if ref == "Prev_High":
                base_level = ref_level * (1 + base/100)
                next_level = ref_level * (1 + nxt/100)
                base_reached = row["High"] >= base_level
                next_reached = row["High"] >= next_level
                move_desc = f"{nxt:.1f}% > {ref}"
            else:
                base_level = ref_level * (1 - base/100)
                next_level = ref_level * (1 - nxt/100)
                base_reached = row["Low"] <= base_level
                next_reached = row["Low"] <= next_level
                move_desc = f"{nxt:.1f}% < {ref}"

            if base_reached:
                event = f"{move_desc} | {broken}, {last_candle}, {base:.1f} Reached"
                # print("\n", event)
                outcome = 1 if next_reached else 0
                records.append((event, outcome))

    # --- Aggregate results ---
    if not records:
        return pd.DataFrame(columns=["Event", "Probability", "Count"])

    df_events = pd.DataFrame(records, columns=["Event", "Outcome"])
    summary = df_events.groupby("Event")["Outcome"].agg(["mean", "count"]).reset_index()
    summary.rename(columns={"mean": "Probability", "count": "Count"}, inplace=True)
    summary["Probability"] = (summary["Probability"] * 100).round(2)
    summary = summary.sort_values("Probability", ascending=False).reset_index(drop=True)

    return summary

if __name__ == "__main__":

    # do nothing
    pass