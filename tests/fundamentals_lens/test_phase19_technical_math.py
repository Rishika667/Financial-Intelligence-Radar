"""
Phase 19 Technical Analysis Engine: Mathematical Assurance & Invariant Verification Suite.

Validates:
1. Exact Wilder RSI initialization: SMA(14) seeding at index 14, followed by exponential recurrence.
2. Exact Wilder ATR initialization: SMA(14) seeding at index 13, followed by exponential recurrence.
3. Edge cases for RSI: Flat series (50.0), all-gains (100.0), all-losses (0.0), zero-loss, zero-gain.
4. Bollinger Bands standard deviation convention: population (ddof=0) default matching John Bollinger
   and published documentation; sample (ddof=1) support.
5. Return-window semantics: N+1 observations strictly required for full N-interval returns.
6. Zero-vs-missing handling: 0.0 annualized volatility and 0.0 max drawdown preserved as valid floats;
   empty inputs report last_close as None (not fabricated 0.0).
7. Benchmark alignment: Timestamp normalization, common-date inner join, duration guards.
"""

import math
import pytest
import pandas as pd
import numpy as np

from fundamentals_lens.technical import (
    calculate_sma,
    calculate_ema,
    calculate_rsi,
    calculate_macd,
    calculate_bollinger_bands,
    calculate_atr,
    compute_technical_indicators,
    compute_technical_summary,
    create_benchmark_comparison_chart,
)
from fundamentals_lens.models import TechnicalSummary


# ==============================================================================
# 1. WILDER'S RSI EXACT INITIALIZATION & RECURRENCE TESTS
# ==============================================================================

def test_wilder_rsi_hand_calculated_deterministic_series():
    """
    Hand-calculated 16-bar price series for RSI(14):
    Prices: [100, 102, 101, 103, 105, 104, 106, 108, 107, 109, 111, 110, 112, 114, 113, 115]
    Diffs (15 changes):
    t=1: +2 (G=2, L=0)
    t=2: -1 (G=0, L=1)
    t=3: +2 (G=2, L=0)
    t=4: +2 (G=2, L=0)
    t=5: -1 (G=0, L=1)
    t=6: +2 (G=2, L=0)
    t=7: +2 (G=2, L=0)
    t=8: -1 (G=0, L=1)
    t=9: +2 (G=2, L=0)
    t=10: +2 (G=2, L=0)
    t=11: -1 (G=0, L=1)
    t=12: +2 (G=2, L=0)
    t=13: +2 (G=2, L=0)
    t=14: -1 (G=0, L=1)
    First 14 changes (t=1..14):
    Gains: 2+0+2+2+0+2+2+0+2+2+0+2+2+0 = 18.0 -> Initial SMA Gain = 18.0 / 14 = 1.285714
    Losses: 0+1+0+0+1+0+0+1+0+0+1+0+0+1 = 5.0 -> Initial SMA Loss = 5.0 / 14 = 0.357143
    RS_14 = 1.285714 / 0.357143 = 3.600000
    RSI_14 = 100 - (100 / (1 + 3.6)) = 100 - (100 / 4.6) = 100 - 21.7391 = 78.2608 -> 78.26

    Change at t=15: Price 113 -> 115 (+2, Gain=2, Loss=0)
    Smoothed Gain_15 = (1.285714 * 13 + 2.0) / 14 = (16.714282 + 2.0) / 14 = 18.714282 / 14 = 1.336734
    Smoothed Loss_15 = (0.357143 * 13 + 0.0) / 14 = 4.642859 / 14 = 0.331633
    RS_15 = 1.336734 / 0.331633 = 4.030769
    RSI_15 = 100 - (100 / (1 + 4.030769)) = 100 - (100 / 5.030769) = 100 - 19.8776 = 80.1223 -> 80.12
    """
    prices = pd.Series([100.0, 102.0, 101.0, 103.0, 105.0, 104.0, 106.0, 108.0, 
                        107.0, 109.0, 111.0, 110.0, 112.0, 114.0, 113.0, 115.0])
    rsi = calculate_rsi(prices, period=14)
    assert len(rsi) == 16
    # Indices 0 to 13 must be NaN
    for i in range(14):
        assert pd.isna(rsi.iloc[i]), f"Index {i} should be NaN during warm-up"
    # Index 14: first valid value from initial SMA
    assert rsi.iloc[14] == pytest.approx(78.26, abs=0.02)
    # Index 15: subsequent smoothed Wilder recurrence
    assert rsi.iloc[15] == pytest.approx(80.12, abs=0.02)


def test_wilder_rsi_flat_series_and_edge_cases():
    """Verify exact behavior of RSI on flat series, all-gain, and all-loss."""
    flat = pd.Series([50.0] * 30)
    rsi_flat = calculate_rsi(flat, 14)
    # First 14 are NaN, then all remaining must be exactly 50.0
    assert rsi_flat.iloc[:14].isna().all()
    assert (rsi_flat.iloc[14:] == 50.0).all()

    rising = pd.Series([10.0 + i for i in range(30)])
    rsi_rising = calculate_rsi(rising, 14)
    assert (rsi_rising.iloc[14:] == 100.0).all()

    falling = pd.Series([100.0 - i for i in range(30)])
    rsi_falling = calculate_rsi(falling, 14)
    assert (rsi_falling.iloc[14:] == 0.0).all()


def test_wilder_rsi_warmup_length():
    """Series with fewer than period + 1 observations returns all NaN."""
    short_series = pd.Series([10.0, 11.0, 12.0, 11.0, 10.0])
    rsi = calculate_rsi(short_series, 14)
    assert rsi.isna().all()


# ==============================================================================
# 2. WILDER'S ATR EXACT INITIALIZATION & RECURRENCE TESTS
# ==============================================================================

def test_wilder_atr_hand_calculated_deterministic_series():
    """
    Verify ATR on a 16-bar deterministic fixture.
    14 bars of constant TR=10 (High=105, Low=95, Close=100) -> Initial SMA = 10.0 at index 13.
    Bar 14: Gap up: High=120, Low=110, Close=115 (prior close=100).
    TR_14 = max(120-110=10, |120-100|=20, |110-100|=10) = 20.0
    ATR_14 = (10.0 * 13 + 20.0) / 14 = 150.0 / 14 = 10.714285 -> 10.71
    Bar 15: Constant bar: High=120, Low=110, Close=115 (prior close=115).
    TR_15 = max(10, 5, 5) = 10.0
    ATR_15 = (10.714285 * 13 + 10.0) / 14 = 149.2857 / 14 = 10.6632 -> 10.66
    """
    high = pd.Series([105.0] * 14 + [120.0, 120.0])
    low = pd.Series([95.0] * 14 + [110.0, 110.0])
    close = pd.Series([100.0] * 14 + [115.0, 115.0])

    atr = calculate_atr(high, low, close, period=14)
    assert len(atr) == 16
    # Indices 0 to 12 must be NaN
    for i in range(13):
        assert pd.isna(atr.iloc[i]), f"Index {i} should be NaN during warm-up"
    # Index 13: initial SMA of the first 14 true ranges
    assert atr.iloc[13] == pytest.approx(10.00, abs=0.01)
    # Index 14: first Wilder recurrence smoothed with gap True Range 20.0
    assert atr.iloc[14] == pytest.approx(10.71, abs=0.01)
    # Index 15: subsequent Wilder recurrence
    assert atr.iloc[15] == pytest.approx(10.66, abs=0.01)


# ==============================================================================
# 3. BOLLINGER BANDS POPULATION (ddof=0) VS SAMPLE (ddof=1) CONVENTION
# ==============================================================================

def test_bollinger_bands_population_vs_sample_alignment():
    """
    Standardize on population standard deviation (ddof=0) matching John Bollinger's definition:
    sigma = sqrt( (1/N) * sum( (P_i - SMA)^2 ) ).
    Verify against hand-computed values:
    Series: [10, 12, 14, 16, 18], N=5, SMA=14.0
    Squared differences: [16, 4, 0, 4, 16], Sum = 40.0
    Population variance = 40 / 5 = 8.0 -> sigma_pop = sqrt(8) ~ 2.828427
    Sample variance = 40 / 4 = 10.0 -> sigma_samp = sqrt(10) ~ 3.162277
    """
    s = pd.Series([10.0, 12.0, 14.0, 16.0, 18.0])

    # Default call must use ddof=0
    up_pop, mid_pop, low_pop = calculate_bollinger_bands(s, period=5, num_std=2.0)
    assert mid_pop.iloc[4] == pytest.approx(14.0, abs=1e-4)
    assert up_pop.iloc[4] == pytest.approx(round(14.0 + 2.0 * math.sqrt(8.0), 2), abs=1e-4)
    assert low_pop.iloc[4] == pytest.approx(round(14.0 - 2.0 * math.sqrt(8.0), 2), abs=1e-4)

    # Optional ddof=1
    up_samp, mid_samp, low_samp = calculate_bollinger_bands(s, period=5, num_std=2.0, ddof=1)
    assert up_samp.iloc[4] == pytest.approx(round(14.0 + 2.0 * math.sqrt(10.0), 2), abs=1e-4)
    assert low_samp.iloc[4] == pytest.approx(round(14.0 - 2.0 * math.sqrt(10.0), 2), abs=1e-4)

    # Rejection of invalid ddof
    with pytest.raises(ValueError, match="ddof must be 0"):
        calculate_bollinger_bands(s, period=5, num_std=2.0, ddof=2)


# ==============================================================================
# 4. STANDARDIZED RETURN-WINDOW SEMANTICS (N+1 OBSERVATIONS)
# ==============================================================================

def test_return_window_requires_n_plus_one_observations():
    """
    Verify point-to-point return R_t(N) = (P_t / P_{t-N} - 1) * 100%.
    Full N-interval return requires >= N+1 observations:
    - 1M (21 intervals): requires 22 bars
    - 3M (63 intervals): requires 64 bars
    - 6M (126 intervals): requires 127 bars
    - 1Y (252 intervals): requires 253 bars + adequate calendar coverage
    """
    # 21 bars: 1M is None; 22 bars: 1M is populated
    d21 = pd.date_range("2026-01-01", periods=21, freq="B")
    c21 = [100.0 + i for i in range(21)]
    df21 = pd.DataFrame({"Date": d21, "Open": c21, "High": [c+1 for c in c21], "Low": [c-1 for c in c21], "Close": c21, "Volume": [1000]*21})
    s21 = compute_technical_summary(df21, ticker="T21")
    assert s21.change_1m is None

    d22 = pd.date_range("2026-01-01", periods=22, freq="B")
    c22 = [100.0 + i for i in range(22)]
    df22 = pd.DataFrame({"Date": d22, "Open": c22, "High": [c+1 for c in c22], "Low": [c-1 for c in c22], "Close": c22, "Volume": [1000]*22})
    s22 = compute_technical_summary(df22, ticker="T22")
    assert s22.change_1m is not None
    # 22 bars: P_21 / P_0 - 1 = 121 / 100 - 1 = +21.0%
    assert s22.change_1m == pytest.approx(21.00, abs=0.01)

    # 63 bars: 3M is None; 64 bars: 3M is populated
    d63 = pd.date_range("2026-01-01", periods=63, freq="B")
    c63 = [100.0 + i for i in range(63)]
    df63 = pd.DataFrame({"Date": d63, "Open": c63, "High": [c+1 for c in c63], "Low": [c-1 for c in c63], "Close": c63, "Volume": [1000]*63})
    s63 = compute_technical_summary(df63, ticker="T63")
    assert s63.change_3m is None

    d64 = pd.date_range("2026-01-01", periods=64, freq="B")
    c64 = [100.0 + i for i in range(64)]
    df64 = pd.DataFrame({"Date": d64, "Open": c64, "High": [c+1 for c in c64], "Low": [c-1 for c in c64], "Close": c64, "Volume": [1000]*64})
    s64 = compute_technical_summary(df64, ticker="T64")
    assert s64.change_3m is not None


# ==============================================================================
# 5. ZERO-VS-MISSING INTEGRITY (VOLATILITY, DRAWDOWN, EMPTY DATA)
# ==============================================================================

def test_zero_volatility_and_drawdown_preserved_as_valid_floats():
    """
    On a flat series, annualized daily volatility is exactly 0.0 and maximum drawdown is 0.0.
    These must be represented as 0.0 float values, never coerced to None or suppressed.
    """
    dates = pd.date_range("2026-01-01", periods=30, freq="B")
    df = pd.DataFrame({
        "Date": dates,
        "Open": [100.0] * 30,
        "High": [100.0] * 30,
        "Low": [100.0] * 30,
        "Close": [100.0] * 30,
        "Volume": [1000] * 30
    })
    summary = compute_technical_summary(df, ticker="FLAT_ZERO")
    assert summary.annualized_volatility == 0.0
    assert summary.max_drawdown == 0.0
    # Both must be distinct from None
    assert summary.annualized_volatility is not None
    assert summary.max_drawdown is not None


def test_empty_summary_does_not_fabricate_zero_last_close():
    """Empty technical summary must report last_close as None, not fabricated 0.0."""
    empty_df = pd.DataFrame()
    summary = compute_technical_summary(empty_df, ticker="EMPTY")
    assert summary.total_bars == 0
    assert summary.last_close is None
    assert summary.change_1m is None
    assert summary.change_1y is None
    assert summary.annualized_volatility is None
    assert summary.max_drawdown is None


# ==============================================================================
# 6. BENCHMARK ALIGNMENT & NORMALIZED COMPARISON GUARDS
# ==============================================================================

def test_benchmark_alignment_and_normalization():
    """
    Verify benchmark inner join on dates, normalization to base 100, and 1Y guard.
    """
    dates_common = pd.date_range("2025-01-01", periods=260, freq="B")
    asset_closes = [100.0 + (i * 0.2) for i in range(260)]
    bench_closes = [1000.0 + (i * 1.0) for i in range(260)]

    df_asset = pd.DataFrame({"Date": dates_common, "Open": asset_closes, "High": [c+1 for c in asset_closes], "Low": [c-1 for c in asset_closes], "Close": asset_closes, "Volume": [1000]*260})
    df_bench = pd.DataFrame({"Date": dates_common, "Open": bench_closes, "High": [c+5 for c in bench_closes], "Low": [c-5 for c in bench_closes], "Close": bench_closes, "Volume": [5000]*260})

    summary = compute_technical_summary(df_asset, ticker="ASSET", benchmark_df=df_bench, benchmark_ticker="INDEX")
    assert summary.common_benchmark_bars == 260
    assert summary.benchmark_change_1y is not None
    assert summary.relative_performance_1y is not None
    # Period return should also be populated
    assert summary.benchmark_period_return is not None
    assert summary.relative_performance_period is not None

    # Chart creation
    fig = create_benchmark_comparison_chart(df_asset, df_bench, "ASSET", "INDEX")
    assert fig is not None
    assert "Relative Performance vs. INDEX (Base = 100)" in fig.layout.title.text
    assert "260 common bars" in fig.layout.title.text
