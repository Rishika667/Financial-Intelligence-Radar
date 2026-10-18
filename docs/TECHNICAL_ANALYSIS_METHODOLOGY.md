# Technical Analysis MVP — Quantitative Methodology & Mathematical Specifications

## 1. Executive Summary & Objective

The **Technical Analysis MVP** within **Fundamentals Lens** is an evidence-backed, zero-cost quantitative research engine. It provides analysts with standardized historical price action context, trend indicators, momentum oscillators, volatility measures, and comparative benchmark tracking alongside audited fundamental disclosures.

### Core Architecture & Guiding Tenets
1. **Zero External TA Dependencies:** Built purely using Python's standard library, `pandas`, `numpy`, and `plotly`. Heavy external libraries (`yfinance`, `ta`, `pandas_ta`) are avoided to ensure fast execution, portability, and zero supply-chain risk.
2. **In-Memory Data Ingestion:** Uploaded custom OHLCV CSV files are parsed and validated strictly in volatile memory. No user files or private financial records are stored to disk.
3. **No Black-Box Signals or Price Forecasts:** The engine performs deterministic historical mathematical observations. It strictly avoids price predictions, buy/sell flags, automated signal generation, or trading recommendations.
4. **Transparent Sample Size & Non-Stationarity Caveats:** Financial time series are non-stationary and subject to structural regime shifts. Moving average horizons and indicator lookbacks are clearly parameterized and documented.

---

## 2. Input Data Format & Strict Validation Engine

The module accepts comma-separated values (CSV) containing daily trading intervals with the following canonical schema:

| Column | Data Type | Required | Canonical Rule & Format |
|:---|:---|:---:|:---|
| `Date` | Date String | Yes | ISO 8601 (`YYYY-MM-DD`) or standard date parseable by `pd.to_datetime`. Sorted chronologically without duplicate trading days. |
| `Open` | Float | Yes | Strictly positive non-zero opening transaction price ($ > 0.0 $). |
| `High` | Float | Yes | Strictly positive high price ($ > 0.0 $); must satisfy $ \text{High} \ge \text{Low} $, $ \text{High} \ge \text{Open} $, $ \text{High} \ge \text{Close} $. |
| `Low` | Float | Yes | Strictly positive low price ($ > 0.0 $); must satisfy $ \text{Low} \le \text{Open} $, $ \text{Low} \le \text{Close} $. |
| `Close` | Float | Yes | Strictly positive closing transaction price ($ > 0.0 $). |
| `Volume` | Integer/Float | Yes | Non-negative integer or float representing total shares traded ($ \ge 0 $). |

### Validation Rules (`validate_ohlcv_dataframe`)
- **Case-Insensitive Resolution:** Headers such as `date`, `OPEN`, `High`, `close`, `VOLUME` are resolved automatically.
- **Minimum Observation Guard:** Datasets must contain at least **20 trading days** to calculate basic moving averages and short-horizon oscillators. Warnings are registered if observations are below 200 trading days for the 200-day moving average.
- **Price Invariant Sanity:** Any violation where $\text{High} < \text{Low}$ fails validation immediately and flags the specific dates.

---

## 3. Mathematical Indicator Formulas

### 3.1 Simple Moving Averages (SMA)
For a price series $P$ over a rolling window of length $N$:
$$\text{SMA}_t(N) = \frac{1}{N} \sum_{i=0}^{N-1} P_{t-i}$$
Supported horizons:
- **SMA(20):** Short-term trend (approximately 1 month of trading).
- **SMA(50):** Medium-term trend (approximately 1 quarter of trading).
- **SMA(200):** Long-term institutional trend (approximately 1 year / 10 months of trading). Requires $\ge 200$ bars.

### 3.2 Exponential Moving Average (EMA)
$$\text{EMA}_t(N) = \alpha \cdot P_t + (1 - \alpha) \cdot \text{EMA}_{t-1}(N)$$
where the smoothing multiplier is:
$$\alpha = \frac{2}{N + 1}$$

### 3.3 Relative Strength Index (RSI - 14)
The Relative Strength Index measures momentum and velocity of price movements using Wilder's smoothed exponential moving average ($\alpha = 1 / 14$):
$$\Delta P_t = P_t - P_{t-1}$$
$$\text{Gain}_t = \max(\Delta P_t, 0), \quad \text{Loss}_t = \max(-\Delta P_t, 0)$$
$$\text{AvgGain}_t = \frac{1}{14} \text{Gain}_t + \frac{13}{14} \text{AvgGain}_{t-1}$$
$$\text{AvgLoss}_t = \frac{1}{14} \text{Loss}_t + \frac{13}{14} \text{AvgLoss}_{t-1}$$
$$\text{RS}_t = \frac{\text{AvgGain}_t}{\text{AvgLoss}_t}$$
$$\text{RSI}_t = 100 - \left(\frac{100}{1 + \text{RS}_t}\right)$$
- If $\text{AvgLoss}_t = 0$, $\text{RSI}_t = 100$.
- If $\text{AvgGain}_t = 0$, $\text{RSI}_t = 0$.
- Standard thresholds:
  - $\text{RSI} \ge 70$: Overbought indicator.
  - $\text{RSI} \le 30$: Oversold indicator.
  - $30 < \text{RSI} < 70$: Neutral momentum.

### 3.4 Moving Average Convergence Divergence (MACD - 12, 26, 9)
$$\text{MACD Line}_t = \text{EMA}_t(12) - \text{EMA}_t(26)$$
$$\text{Signal Line}_t = \text{EMA}_t(9 \text{ of MACD Line})$$
$$\text{MACD Histogram}_t = \text{MACD Line}_t - \text{Signal Line}_t$$
A positive histogram indicates expanding upward momentum; a negative histogram indicates contraction.

### 3.5 Bollinger Bands (20, 2.0 std)
$$\text{Middle Band}_t = \text{SMA}_t(20)$$
$$\sigma_t(20) = \sqrt{\frac{1}{20} \sum_{i=0}^{19} (P_{t-i} - \text{Middle Band}_t)^2}$$
$$\text{Upper Band}_t = \text{Middle Band}_t + 2.0 \cdot \sigma_t(20)$$
$$\text{Lower Band}_t = \text{Middle Band}_t - 2.0 \cdot \sigma_t(20)$$

### 3.6 Average True Range (ATR - 14)
$$\text{True Range}_t = \max\left( \text{High}_t - \text{Low}_t, \; |\text{High}_t - \text{Close}_{t-1}|, \; |\text{Low}_t - \text{Close}_{t-1}| \right)$$
$$\text{ATR}_t = \frac{1}{14} \text{True Range}_t + \frac{13}{14} \text{ATR}_{t-1}$$

---

## 4. Performance & Risk Measures

### 4.1 Multi-Period Return Horizons
- **1-Month Return:** Lookback of 21 trading bars: $((P_t / P_{t-21}) - 1) \times 100$.
- **3-Month Return:** Lookback of 63 trading bars: $((P_t / P_{t-63}) - 1) \times 100$.
- **6-Month Return:** Lookback of 126 trading bars: $((P_t / P_{t-126}) - 1) \times 100$.
- **1-Year Return:** Lookback of 252 trading bars: $((P_t / P_{t-252}) - 1) \times 100$.

### 4.2 52-Week Range & Distance Metrics
Over the most recent $\min(252, N)$ bars:
$$\text{High}_{52\text{W}} = \max(\text{High}_{\text{window}}), \quad \text{Low}_{52\text{W}} = \min(\text{Low}_{\text{window}})$$
$$\text{Distance from High} = \left(\frac{P_{\text{last}}}{\text{High}_{52\text{W}}} - 1\right) \times 100$$
$$\text{Distance from Low} = \left(\frac{P_{\text{last}}}{\text{Low}_{52\text{W}}} - 1\right) \times 100$$

### 4.3 Annualized Volatility
Daily return is $R_t = (P_t / P_{t-1}) - 1$.
The sample standard deviation of daily returns $\sigma_d$ is annualized across standard 252 trading days:
$$\sigma_{\text{ann}} = \sigma_d \times \sqrt{252} \times 100\%$$

### 4.4 Maximum Historical Drawdown
$$\text{Peak}_t = \max_{0 \le s \le t} P_s$$
$$\text{Drawdown}_t = \frac{P_t - \text{Peak}_t}{\text{Peak}_t} \times 100\%$$
$$\text{Max Drawdown} = \min_{t} \text{Drawdown}_t$$

### 4.5 Comparative Benchmark Alignment (Base = 100)
When an asset price series $A$ is compared against a benchmark series $B$, an inner join on common trading dates aligns the timelines. Both series are normalized to a base of 100 at the initial shared date $t_0$:
$$A^*_t = \frac{A_t}{A_{t_0}} \times 100, \quad B^*_t = \frac{B_t}{B_{t_0}} \times 100$$
Relative Performance Spread:
$$\text{Relative Spread} = \left( \frac{A_{\text{last}}}{A_{t_0}} - 1 \right) \times 100 - \left( \frac{B_{\text{last}}}{B_{t_0}} - 1 \right) \times 100$$

---

## 5. Analytical Notice & Limitations

1. **Non-Predictive:** Past volatility and volume distributions do not guarantee future price action.
2. **Lagging Indicators:** Moving averages and MACD are inherently trend-following lagging indicators that experience slippage during regime shifts.
3. **Data Quality Dependency:** Indicator accuracy depends strictly on the integrity and granularity of the ingested OHLCV data. Corporate actions (stock splits, special cash dividends) must be adjusted prior to upload.
