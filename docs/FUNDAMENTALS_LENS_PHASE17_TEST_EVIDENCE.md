# Fundamentals Lens — Phase 17 Test Evidence & Mathematical Acceptance Report
**Platform:** Fundamentals Lens • Evidence-First Financial Research Workbench  
**Author:** Created by Rishika Dangayach  
**Branch:** `pivot/fundamentals-lens-phase0`  
**Date:** 2026-10-19  
**Status:** ALL GATES PASSED (35/35 Phase 17 tests, 62/62 Technical tests, 258/258 Fundamentals validation checks)

---

## 1. Test Suite Summary & Acceptance Gate Results

```
============================= test session starts =============================
platform win32 -- Python 3.11.9, pytest-9.1.1, pluggy-1.6.0
rootdir: C:\Users\HP\.gemini\antigravity\scratch\Financial-Intelligence-Radar
configfile: pyproject.toml
plugins: anyio-4.15.1
collected 62 items

tests\fundamentals_lens\test_technical_analysis.py ....................  [ 32%]
tests\fundamentals_lens\test_phase16_technical_analysis.py .......       [ 43%]
tests\fundamentals_lens\test_phase17_technical_engine.py ............... [ 67%]
....................                                                     [100%]

============================= 62 passed in 2.22s ==============================
```

### Primary Gate Verification Checklist
- [x] **Release Blocker Gate:** `python scripts/validate_fundamentals_data.py` passes 258/258 checks (100% pass rate).
- [x] **Mathematical Assurance Gate:** SMA, EMA, RSI with Wilder's recurrence and flat-series handling, MACD, Bollinger Bands (`ddof=1`), and ATR pass deterministic fixtures.
- [x] **Parameter Invariant Gate:** Zero, negative, and invalid parameters raise explicit `ValueError`.
- [x] **Duration Boundary Gate:** 19, 20, 21, 63, 126, 199, 200, 251, 252, and 253 bars verified against exact documented behaviors.
- [x] **Calendar Coverage Gate:** 252 bars with calendar coverage (340–395 days, max gap $\le 14$ days) populates 1Y; compressed calendars or excessive gaps suppress 1Y.
- [x] **OHLCV Hardening Gate:** Ambiguous duplicate headers, non-numeric strings, negative prices, volume $< 0$, range violations, and contradictory duplicate rows rejected.
- [x] **Benchmark Alignment Gate:** Common-date inner join, duplicate date deduplication, positive base price verification, and identical 1Y relative return matching verified.
- [x] **Corporate Action & Provenance Gate:** `PriceAdjustmentBasis` retained across analysis, chart, CSV export, and research brief with privacy disclaimer.
- [x] **Compilation Gate:** `python -m compileall src scripts tests fundamentals_lens_app.py` passes cleanly.
- [x] **Diff Cleanliness Gate:** `git diff --check` reports zero whitespace or formatting errors.
- [x] **Visual QA Gate:** All 7 desktop/mobile screenshots verified via Chrome DevTools Protocol with DOM mounting and non-zero chart dimensions.

---

## 2. Mathematical Indicator Fixture Results

### 2.1 Simple Moving Average (SMA)
- **Input:** `[10.0, 20.0, 30.0, 40.0, 50.0]`, `period = 3`
- **Output:** `[NaN, NaN, 20.0, 30.0, 40.0]`
- **Status:** PASS (`test_sma_deterministic_numerical_correctness`).
- **Parameter Guard:** `period <= 0` raises `ValueError: period must be a positive integer >= 1`. PASS (`test_sma_invalid_period_raises`).

### 2.2 Exponential Moving Average (EMA)
- **Formula:** $\alpha = \frac{2}{N + 1}$. For $N = 3$, $\alpha = 0.5$.
- **Input:** `[10.0, 20.0, 30.0, 40.0]`
- **Step Calculations:**
  - $y_0 = 10.0$
  - $y_1 = 0.5 \times 20.0 + 0.5 \times 10.0 = 15.0$
  - $y_2 = 0.5 \times 30.0 + 0.5 \times 15.0 = 22.5$
  - $y_3 = 0.5 \times 40.0 + 0.5 \times 22.5 = 31.25$
- **Output:** Exactly matches theoretical sequence. PASS (`test_ema_deterministic_numerical_correctness`).

### 2.3 Relative Strength Index (Wilder's RSI - 14)
- **Flat Series Corner Case:** Constant prices `[100.0] * 30`. Returns exactly `50.0` (neutral). PASS (`test_rsi_flat_series_returns_neutral_50`).
- **All-Gains Monotonic Rise:** `[100.0 + i for i in range(30)]`. Zero loss. Returns `100.0`. PASS (`test_rsi_monotonically_rising_returns_100`).
- **All-Losses Monotonic Fall:** `[100.0 - i for i in range(30)]`. Zero gain. Returns `0.0`. PASS (`test_rsi_monotonically_falling_returns_0`).
- **Alternating Series:** `[100.0, 105.0] * 20`. Valid values strictly bounded in $[0.0, 100.0]$. PASS (`test_rsi_bounds_and_oscillations`).
- **Parameter Guard:** `period <= 0` raises `ValueError`. PASS (`test_rsi_invalid_period_raises`).

### 2.4 Moving Average Convergence Divergence (MACD - 12, 26, 9)
- **Constant Series:** `[100.0] * 40`. Fast EMA = 100, Slow EMA = 100. MACD Line = 0.0, Signal Line = 0.0, Histogram = 0.0. PASS (`test_macd_constant_prices_zero_histogram`).
- **Parameter Guard:** `fast >= slow` raises `ValueError: fast period must be strictly less than slow period`. PASS (`test_macd_parameter_validation`).

### 2.5 Bollinger Bands (20, 2.0 std, sample std ddof=1)
- **Hand-Calculated Fixture:** `[10.0, 12.0, 14.0, 16.0, 18.0]`, `period = 5`, `num_std = 2.0`.
  - Mean = $14.0$
  - Deviations squared: $16 + 4 + 0 + 4 + 16 = 40$
  - Sample variance ($\text{ddof}=1$) = $40 / 4 = 10.0 \implies \sigma = \sqrt{10} \approx 3.162277$
  - Middle Band = $14.00$
  - Upper Band = $14.00 + 2.0 \times 3.162277 = 20.32$
  - Lower Band = $14.00 - 2.0 \times 3.162277 = 7.68$
- **Output:** Matches within $10^{-4}$ tolerance. PASS (`test_bollinger_bands_sample_std_ddof1`).
- **Constant Series:** $\sigma = 0 \implies Upper = Middle = Lower = 50.00$. PASS (`test_bollinger_bands_constant_prices`).

### 2.6 Average True Range (ATR - 14)
- **Initial True Range:** $\text{TR}_0 = High_0 - Low_0$. Subsequent $\text{TR}_t = \max(H-L, |H-C_{t-1}|, |L-C_{t-1}|)$.
- **Wilder's Smoothing:** Initial 14-bar SMA, followed by exponential smoothing with $\alpha = 1/14$. PASS (`test_atr_true_range_and_smoothing`).

---

## 3. Duration Boundary & Calendar Coverage Acceptance Matrix

| Bar Count | Trading Days Spanned | Calendar Days | Max Gap | Expected 1M Return | Expected 3M Return | Expected 6M Return | Expected SMA(200) | Expected 1Y Return | 52W Label Status | Test Case | Outcome |
|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---|:---:|
| **19** | 19 | ~27 | 3 | Rejected | Rejected | Rejected | Rejected | Rejected | Rejected | `test_duration_boundary_19_bars_rejected` | **PASS (Error)** |
| **20** | 20 | ~28 | 3 | `None` | `None` | `None` | `N/A` | `None` | Trading Range (20 bars) | `test_duration_boundary_20_bars_passes_validation` | **PASS** |
| **21** | 21 | ~29 | 3 | Populated | `None` | `None` | `N/A` | `None` | Trading Range (21 bars) | `test_duration_boundary_21_bars` | **PASS** |
| **63** | 63 | ~90 | 3 | Populated | Populated | `None` | `N/A` | `None` | Trading Range (63 bars) | `test_duration_boundary_63_bars` | **PASS** |
| **126** | 126 | ~180 | 3 | Populated | Populated | Populated | `N/A` | `None` | Trading Range (126 bars) | `test_duration_boundary_126_bars` | **PASS** |
| **199** | 199 | ~280 | 3 | Populated | Populated | Populated | `N/A (< 200 bars)` | `None` | Trading Range (199 bars) | `test_duration_boundary_199_vs_200_bars` | **PASS** |
| **200** | 200 | ~282 | 3 | Populated | Populated | Populated | Populated | `None` | Trading Range (200 bars) | `test_duration_boundary_199_vs_200_bars` | **PASS** |
| **251** | 251 | ~355 | 3 | Populated | Populated | Populated | Populated | `None` | Available-History (251 bars) | `test_duration_boundary_251_bars_suppresses_1y_and_52w` | **PASS** |
| **252** (Adequate) | 252 | 365 | 3 | Populated | Populated | Populated | Populated | Populated | 52-Week Range | `test_duration_boundary_252_bars_adequate_coverage` | **PASS** |
| **252** (Compressed) | 252 | 251 | 1 | Populated | Populated | Populated | Populated | `None` | Available-History (252 bars) | `test_duration_boundary_252_bars_insufficient_coverage_suppresses_1y` | **PASS** |
| **252** (Excessive Gap) | 252 | 360 | 25 | Populated | Populated | Populated | Populated | `None` | Available-History (252 bars) | `test_duration_boundary_excessive_calendar_gap_suppresses_1y` | **PASS** |
| **253** | 253 | 366 | 3 | Populated | Populated | Populated | Populated | Populated | 52-Week Range | `test_duration_boundary_253_bars` | **PASS** |

---

## 4. Benchmark Alignment & Performance Consistency

### 4.1 Common Date Overlap Logic
```python
df_bench_src = df[["Date", "Date_Str", "Close"]].drop_duplicates(subset=["Date"])
bm_bench_src = benchmark_df[["Date", "Close"]].drop_duplicates(subset=["Date"])
merged = pd.merge(df_bench_src, bm_bench_src, on="Date", how="inner").sort_values("Date")
```
- Eliminates Cartesian duplicate row expansion.
- Filters non-positive and non-finite prices.
- Re-bases both series to 100 on initial common date.

### 4.2 Relative Performance Verification
- When asset and benchmark share identical dates (260 bars):
  - `summary.change_1y` is computed on asset.
  - `summary.benchmark_change_1y` is computed on benchmark.
  - `summary.relative_performance_1y` matches `change_1y - benchmark_change_1y` within numerical precision. PASS (`test_benchmark_alignment_identical_dates_1y_match`).
- When benchmark overlap is short (50 bars):
  - `summary.benchmark_change_1y = None`
  - `summary.relative_performance_1y = None`
  - `summary.relative_performance_period` is populated for the common 50 bars. PASS (`test_benchmark_alignment_partial_overlap_suppresses_1y`).

---

## 5. Visual QA & Browser Screenshot Verification

Captured via Chrome DevTools Protocol WebSocket communication with automated DOM mounting assertions:

| Screenshot File | Viewport | Target Page | Key Verified Elements | Chart Dimensions |
|:---|:---:|:---|:---|:---:|
| `01_overview_desktop.png` | 1280 × 900 | Overview | Hero banner, KPIs, Universe Table | 478 × 450 px |
| `02_company_analysis_desktop.png` | 1280 × 950 | Company Analysis | 5-year bar charts, statement breakdown | 810 × 450 px |
| `03_peer_comparison_desktop.png` | 1280 × 950 | Peer Comparison | Peer comparison charts, metrics matrix | 810 × 450 px |
| `04_technical_analysis_desktop.png` | 1280 × 900 | Technical Analysis | Candlestick, Volume, SMAs, Bollinger, KPIs | 810 × 490 px |
| `05_data_integrity_desktop.png` | 1280 × 950 | Data Integrity | Audit trail, 258 passing checks summary | N/A (Table) |
| `06_company_analysis_mobile.png` | 390 × 844 | Company Analysis (Mobile) | Responsive single-column layout | 358 × 450 px |
| `07_technical_analysis_mobile.png` | 390 × 844 | Technical Analysis (Mobile)| Responsive mobile candlestick & volume | 358 × 490 px |

---

## 6. Verification Command Outputs

### 6.1 Data Validation Engine (`scripts/validate_fundamentals_data.py`)
```
================================================================================
VALIDATION SUMMARY & EVIDENCE AUDIT TRAIL
================================================================================
Total Companies Evaluated:               15
Total Checks Executed:                   258
Total Passed:                            258
Total Warnings:                          0
Total Failed:                            0
Total Unverified:                        0
Companies Passing 100% Gates:            15 / 15
================================================================================
RESULT: ALL DATA INTEGRITY GATES PASSED (100% PASS RATE)
```

### 6.2 Python Compilation Check
```
python -m compileall src scripts tests fundamentals_lens_app.py
Listing 'src'...
Listing 'scripts'...
Listing 'tests'...
Listing 'tests\\fundamentals_lens'...
Compiling 'tests\\fundamentals_lens\\test_phase17_technical_engine.py'...
Compiling 'fundamentals_lens_app.py'...
(Zero syntax or bytecode compilation errors)
```

### 6.3 Git Diff Quality Check
```
git diff --check
(Zero whitespace or indentation issues detected)
```
