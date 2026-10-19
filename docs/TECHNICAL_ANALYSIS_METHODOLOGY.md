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
The Relative Strength Index measures momentum and velocity of price movements using Wilder's smoothed moving average ($\alpha = 1 / 14$):
$$\Delta P_t = P_t - P_{t-1}$$
$$\text{Gain}_t = \max(\Delta P_t, 0), \quad \text{Loss}_t = \max(-\Delta P_t, 0)$$

**Exact Wilder Initialization:**
- The first 14 price changes ($t = 1 \dots 14$) are seeded using their Simple Moving Average (SMA):
  $$\text{AvgGain}_{14} = \frac{1}{14} \sum_{i=1}^{14} \text{Gain}_i, \quad \text{AvgLoss}_{14} = \frac{1}{14} \sum_{i=1}^{14} \text{Loss}_i$$
- First valid RSI appears at observation index 14 (15th price observation).
- Subsequent bars ($t > 14$) follow Wilder's exponential recurrence:
  $$\text{AvgGain}_t = \frac{\text{AvgGain}_{t-1} \cdot 13 + \text{Gain}_t}{14}$$
  $$\text{AvgLoss}_t = \frac{\text{AvgLoss}_{t-1} \cdot 13 + \text{Loss}_t}{14}$$
$$\text{RS}_t = \frac{\text{AvgGain}_t}{\text{AvgLoss}_t}, \quad \text{RSI}_t = 100 - \left(\frac{100}{1 + \text{RS}_t}\right)$$
- If $\text{AvgLoss}_t = 0$ and $\text{AvgGain}_t > 0$, $\text{RSI}_t = 100.0$.
- If $\text{AvgGain}_t = 0$ and $\text{AvgLoss}_t > 0$, $\text{RSI}_t = 0.0$.
- If $\text{AvgGain}_t = 0$ and $\text{AvgLoss}_t = 0$ (completely flat series), $\text{RSI}_t = 50.0$ (neutral).
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
- **Standard Deviation Convention:** Bollinger Bands use population standard deviation ($\text{ddof}=0$, divisor $N=20$) by default per John Bollinger's canonical definition. Sample standard deviation ($\text{ddof}=1$, divisor $N-1=19$) is optionally supported via the `ddof` parameter.

### 3.6 Average True Range (ATR - 14)
$$\text{True Range}_0 = \text{High}_0 - \text{Low}_0$$
$$\text{True Range}_t = \max\left( \text{High}_t - \text{Low}_t, \; |\text{High}_t - \text{Close}_{t-1}|, \; |\text{Low}_t - \text{Close}_{t-1}| \right)$$
**Exact Wilder Initialization:**
- The first valid ATR at index 13 (the 14th bar) is the Simple Moving Average of the first 14 True Ranges:
  $$\text{ATR}_{13} = \frac{1}{14} \sum_{i=0}^{13} \text{True Range}_i$$
- Subsequent bars ($t \ge 14$) follow Wilder's exponential smoothing:
  $$\text{ATR}_t = \frac{\text{ATR}_{t-1} \cdot 13 + \text{True Range}_t}{14}$$

---

## 4. Performance & Risk Measures

### 4.1 Multi-Period Return Horizons & Indexing Conventions
- **Return Horizon Definition:** An $N$-interval return reflects percentage price change across $N$ trading intervals:
  $$R_t(N) = \left(\frac{P_t}{P_{t-N}} - 1\right) \times 100\%$$
- **Standardized Observation Requirements ($N+1$ Rule):**
  - Point-to-point comparison over $N$ trading intervals strictly requires at least $N + 1$ chronological observations ($P_0, \dots, P_N$) so that index $(t - N) \ge 0$.
  - With dataset length $M \ge N + 1$, $P_{t-N} = \text{df.iloc}[-1 - N]$.
  - When $M = N$, the dataset spans only $N - 1$ return intervals ($P_{\text{last}} / P_0 - 1$) and is therefore strictly suppressed from being labeled as a full $N$-interval return.
- **Supported Return Horizons:**
  - **1-Month Return (21 trading intervals):** Requires $\ge 22$ bars ($N+1$). Evaluates $(P_t / P_{t-21}) - 1$.
  - **3-Month Return (63 trading intervals):** Requires $\ge 64$ bars ($N+1$). Evaluates $(P_t / P_{t-63}) - 1$.
  - **6-Month Return (126 trading intervals):** Requires $\ge 127$ bars ($N+1$). Evaluates $(P_t / P_{t-126}) - 1$.
  - **1-Year Return (252 trading intervals):** Requires **both** $\ge 253$ trading bars ($N+1$) **and** verified annual calendar coverage (340 to 395 calendar days with max consecutive gap $\le 14$ days). Suppressed if calendar coverage is inadequate or history $< 253$ bars.

### 4.2 52-Week Range & Duration Guard
Over the most recent trailing window of $\min(252, N)$ bars:
$$\text{High}_{52\text{W}} = \max(\text{High}_{\text{window}}), \quad \text{Low}_{52\text{W}} = \min(\text{Low}_{\text{window}})$$
$$\text{Distance from High} = \left(\frac{P_{\text{last}}}{\text{High}_{52\text{W}}} - 1\right) \times 100\%$$
$$\text{Distance from Low} = \left(\frac{P_{\text{last}}}{\text{Low}_{52\text{W}}} - 1\right) \times 100\%$$
- **Labeling Guard:** The range is explicitly designated as `52-Week Range` **only** when history is $\ge 252$ bars and calendar coverage meets the 340–395 day requirement. Otherwise, it is transparently labeled as `Available-History Range (N bars)` to prevent false annual claims.

### 4.3 Annualized Volatility
Daily return is $R_t = (P_t / P_{t-1}) - 1$.
The sample standard deviation of daily returns $\sigma_d$ (computed across $\ge 10$ return observations) is annualized across standard 252 trading days:
$$\sigma_{\text{ann}} = \sigma_d \times \sqrt{252} \times 100\%$$

### 4.4 Maximum Historical Drawdown
$$\text{Peak}_t = \max_{0 \le s \le t} P_s$$
$$\text{Drawdown}_t = \frac{P_t - \text{Peak}_t}{\text{Peak}_t} \times 100\%$$
$$\text{Max Drawdown} = \min_{t} \text{Drawdown}_t$$

### 4.5 Comparative Benchmark Alignment (Base = 100)
When an asset price series $A$ is compared against a benchmark series $B$:
1. **Common-Date Inner Join:** An inner join on unique dates aligns observations. Non-finite values and non-positive prices are eliminated.
2. **Normalized Performance Series:** Both series are rebased to 100 on the initial common date $t_0$:
   $$A^*_t = \frac{A_t}{A_{t_0}} \times 100, \quad B^*_t = \frac{B_t}{B_{t_0}} \times 100$$
3. **Common-Period Relative Spread:**
   $$\text{Relative Spread}_{\text{period}} = \left( \frac{A_{\text{last}}}{A_{t_0}} - 1 \right) \times 100\% - \left( \frac{B_{\text{last}}}{B_{t_0}} - 1 \right) \times 100\%$$
4. **1-Year Relative Spread Guard:**
   1-Year relative return is populated **only** if the common overlapping window spans $\ge 253$ trading bars ($N+1$ observations for 252 intervals) **and** satisfies calendar coverage (340–395 calendar days, max gap $\le 14$ days). Overlapping windows shorter than 253 bars are strictly reported as common-period returns.

---

## 5. Parameter Validation & Edge Case Guarantees

| Indicator / Function | Input Parameter Guard | Zero / Negative Value Behavior | Flat Series Handling |
|:---|:---|:---|:---|
| **SMA** | `period >= 1` | `ValueError` raised on $\le 0$ | Constant value output |
| **EMA** | `period >= 1` | `ValueError` raised on $\le 0$ | Constant value output |
| **RSI(14)** | `period >= 1` | `ValueError` raised on $\le 0$ | Returns exactly 50.0 (neutral) |
| **MACD(12, 26, 9)** | `fast, slow, signal >= 1`, `fast < slow` | `ValueError` raised on invalid params | Line = 0, Signal = 0, Hist = 0 |
| **Bollinger Bands** | `period >= 1`, `num_std >= 0` | `ValueError` raised on invalid params | $\sigma = 0 \implies$ Upper = Middle = Lower |
| **ATR(14)** | `period >= 1` | `ValueError` raised on $\le 0$ | Constant bar range $High - Low$ |

---

## 6. Analytical Notice & Limitations

1. **Non-Predictive:** Past volatility, moving average crosses, and oscillator extremes reflect past price distribution only; they do not guarantee future performance or provide automated buy/sell signals.
2. **Lagging Indicators:** Moving averages and MACD are inherently trend-following lagging indicators that experience slippage during regime shifts.
3. **Data Quality & Corporate Action Dependency:** Indicator accuracy depends strictly on the integrity and adjustment basis of ingested OHLCV data. Unadjusted raw series will produce artificial jumps upon stock splits or cash dividends.
4. **Volatile In-Memory Processing:** Custom user CSV uploads are processed entirely in-memory and are never written to disk or transmitted to external servers. Invariant checks verify internal mathematical consistency, not third-party data provider authenticity.
