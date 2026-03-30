# Markov Model 1 Documentation

## Event String Interpretation

An event string has the format:

```
"{Next%} > Prev_High | High_Broken, {Last_Candle}, {Base%} Reached"
"{Next%} < Prev_Low  | Low_Broken,  {Last_Candle}, {Base%} Reached"
```

### Prev_High / High_Broken (bullish case):
Indicates the current bar broke above the previous bar's high.
The event records the probability that, once price has already advanced by Base% above the previous high, it will continue further to reach Next% above that high, conditioned on the last candle color.

### Prev_Low / Low_Broken (bearish case):
Indicates the current bar broke below the previous bar's low.
The event records the probability that, once price has already fallen by Base% below the previous low, it will continue further to reach Next% below that low, conditioned on the last candle color.

### Last_Candle: 
"Last Green", "Last Red", or "Last Neutral" describes the previous bar's candle.

### Base% Reached: 
The starting milestone that was achieved, from which continuation probability toward Next% is measured.

### Probability: 
The likelihood (in %) of hitting Next% given Base% was reached.

### Count: 
Number of times this event occurred in the dataset.