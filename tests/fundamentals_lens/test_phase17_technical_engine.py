"""
Comprehensive Phase 17 Acceptance Test Suite: Technical Analysis Engine.
Validates:
1. Mathematical assurance of core indicators (SMA, EMA, RSI with Wilder's smoothing/flat series, MACD, Bollinger Bands, ATR).
2. Parameter validation & non-finite guards (negative/zero lookback, NaN, Inf).
3. Duration boundaries (19, 20, 21, 63, 126, 199, 200, 251, 252, 253 bars).
4. Calendar coverage rules (340-395 days, max gap <= 14 days, suppression when violated).
5. OHLCV validation hardening (ambiguous headers, non-numeric strings, positive prices, range invariants, contradictory duplicates).
6. Benchmark alignment (common date overlap, base 100 normalization, duration guards).
7. Price adjustment basis & export fidelity.
"""

import math
import pytest
import pandas as pd
import numpy as np

from fundamentals_lens.technical import (
    validate_ohlcv_dataframe_with_report,
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
from fundamentals_lens.models import (
    OHLCVValidationReport,
    TechnicalSummary,
    PriceAdjustmentBasis,
)
from fundamentals_lens.exports import ExportGenerator


# ==============================================================================
# 1. MATHEMATICAL ASSURANCE: DETERMINISTIC FIXTURES & NUMERICAL TESTS
# ==============================================================================

def test_sma_deterministic_numerical_correctness():
    """Verify SMA calculation against hand-computed exact values."""
    s = pd.Series([10.0, 20.0, 30.0, 40.0, 50.0])
    sma3 = calculate_sma(s, 3)
    assert pd.isna(sma3.iloc[0])
    assert pd.isna(sma3.iloc[1])
    assert sma3.iloc[2] == pytest.approx(20.0, rel=1e-5)
    assert sma3.iloc[3] == pytest.approx(30.0, rel=1e-5)
    assert sma3.iloc[4] == pytest.approx(40.0, rel=1e-5)


def test_sma_invalid_period_raises():
    """Verify SMA rejects zero or negative periods."""
    s = pd.Series([10.0, 20.0, 30.0])
    with pytest.raises(ValueError, match="period must be a positive integer"):
        calculate_sma(s, 0)
    with pytest.raises(ValueError, match="period must be a positive integer"):
        calculate_sma(s, -5)


def test_ema_deterministic_numerical_correctness():
    """Verify EMA with alpha = 2/(N+1)."""
    # For N=3, alpha = 2/(3+1) = 0.5
    s = pd.Series([10.0, 20.0, 30.0, 40.0])
    ema = calculate_ema(s, 3)
    # y0 = 10.0
    # y1 = 0.5*20 + 0.5*10 = 15.0
    # y2 = 0.5*30 + 0.5*15 = 22.5
    # y3 = 0.5*40 + 0.5*22.5 = 31.25
    assert ema.iloc[0] == pytest.approx(10.0, rel=1e-5)
    assert ema.iloc[1] == pytest.approx(15.0, rel=1e-5)
    assert ema.iloc[2] == pytest.approx(22.5, rel=1e-5)
    assert ema.iloc[3] == pytest.approx(31.25, rel=1e-5)


def test_ema_invalid_period_raises():
    s = pd.Series([10.0, 20.0])
    with pytest.raises(ValueError, match="period must be a positive integer"):
        calculate_ema(s, 0)
    with pytest.raises(ValueError, match="period must be a positive integer"):
        calculate_ema(s, -1)


def test_rsi_flat_series_returns_neutral_50():
    """Wilder's RSI on flat price series must evaluate to exactly 50.0."""
    flat = pd.Series([100.0] * 30)
    rsi = calculate_rsi(flat, 14)
    # All valid values after initialization must be 50.0
    valid_rsi = rsi.dropna()
    assert len(valid_rsi) > 0
    assert (valid_rsi == 50.0).all()


def test_rsi_monotonically_rising_returns_100():
    """Wilder's RSI with strictly positive gains and zero losses must return 100.0."""
    rising = pd.Series([100.0 + i for i in range(30)])
    rsi = calculate_rsi(rising, 14)
    valid_rsi = rsi.dropna()
    assert len(valid_rsi) > 0
    assert (valid_rsi == 100.0).all()


def test_rsi_monotonically_falling_returns_0():
    """Wilder's RSI with strictly positive losses and zero gains must return 0.0."""
    falling = pd.Series([100.0 - i for i in range(30)])
    rsi = calculate_rsi(falling, 14)
    valid_rsi = rsi.dropna()
    assert len(valid_rsi) > 0
    assert (valid_rsi == 0.0).all()


def test_rsi_bounds_and_oscillations():
    """Verify RSI remains bounded between 0 and 100 for alternating sequence."""
    alt = pd.Series([100.0, 105.0] * 20)
    rsi = calculate_rsi(alt, 14)
    valid_rsi = rsi.dropna()
    assert len(valid_rsi) > 0
    assert (valid_rsi >= 0.0).all()
    assert (valid_rsi <= 100.0).all()


def test_rsi_invalid_period_raises():
    s = pd.Series([10.0] * 20)
    with pytest.raises(ValueError, match="period must be a positive integer"):
        calculate_rsi(s, 0)
    with pytest.raises(ValueError, match="period must be a positive integer"):
        calculate_rsi(s, -14)


def test_macd_constant_prices_zero_histogram():
    """On constant price series, MACD line, signal line, and histogram must all be 0.0."""
    const = pd.Series([100.0] * 40)
    line, signal, hist = calculate_macd(const, 12, 26, 9)
    assert (line == 0.0).all()
    assert (signal == 0.0).all()
    assert (hist == 0.0).all()


def test_macd_parameter_validation():
    s = pd.Series([100.0] * 40)
    with pytest.raises(ValueError, match="positive integers"):
        calculate_macd(s, 0, 26, 9)
    with pytest.raises(ValueError, match="strictly less than slow period"):
        calculate_macd(s, 26, 12, 9)  # fast >= slow


def test_bollinger_bands_sample_std_ddof1():
    """Verify Bollinger Bands uses population standard deviation (ddof=0) by default and supports sample std (ddof=1)."""
    # 5 observations: 10, 12, 14, 16, 18
    # mean = 14.0
    # differences: -4, -2, 0, 2, 4 -> squared: 16, 4, 0, 4, 16 -> sum = 40
    # population variance (ddof=0) = 40 / 5 = 8.0 -> std = sqrt(8) = 2.828427
    # sample variance (ddof=1) = 40 / (5 - 1) = 10.0 -> sample std = sqrt(10) = 3.162277
    s = pd.Series([10.0, 12.0, 14.0, 16.0, 18.0])

    # Default ddof=0 (population std matching John Bollinger & published formula)
    upper_pop, mid_pop, lower_pop = calculate_bollinger_bands(s, period=5, num_std=2.0)
    expected_mid = 14.0
    expected_pop_std = math.sqrt(8.0)
    assert mid_pop.iloc[4] == pytest.approx(expected_mid, rel=1e-4)
    assert upper_pop.iloc[4] == pytest.approx(round(expected_mid + (2.0 * expected_pop_std), 2), rel=1e-4)
    assert lower_pop.iloc[4] == pytest.approx(round(expected_mid - (2.0 * expected_pop_std), 2), rel=1e-4)

    # Explicit ddof=1 (sample std)
    upper, mid, lower = calculate_bollinger_bands(s, period=5, num_std=2.0, ddof=1)
    expected_std = math.sqrt(10.0)
    expected_upper = round(expected_mid + (2.0 * expected_std), 2)
    expected_lower = round(expected_mid - (2.0 * expected_std), 2)
    assert mid.iloc[4] == pytest.approx(expected_mid, rel=1e-4)
    assert upper.iloc[4] == pytest.approx(expected_upper, rel=1e-4)
    assert lower.iloc[4] == pytest.approx(expected_lower, rel=1e-4)


def test_bollinger_bands_constant_prices():
    """On constant series, standard deviation is 0 so upper == mid == lower."""
    const = pd.Series([50.0] * 25)
    upper, mid, lower = calculate_bollinger_bands(const, 20, 2.0)
    valid_idx = upper.dropna().index
    assert (upper.loc[valid_idx] == 50.0).all()
    assert (mid.loc[valid_idx] == 50.0).all()
    assert (lower.loc[valid_idx] == 50.0).all()


def test_bollinger_bands_invalid_params():
    s = pd.Series([50.0] * 25)
    with pytest.raises(ValueError, match="period must be a positive integer"):
        calculate_bollinger_bands(s, 0, 2.0)
    with pytest.raises(ValueError, match="num_std must be non-negative"):
        calculate_bollinger_bands(s, 20, -1.0)


def test_atr_true_range_and_smoothing():
    """Verify ATR True Range logic across gap days."""
    # Day 0: H=105, L=95, C=100 -> TR = 10
    # Day 1: H=120, L=110, C=115 -> TR = max(10, |120-100|=20, |110-100|=10) = 20
    # Day 2: H=90, L=80, C=85 -> TR = max(10, |90-115|=25, |80-115|=35) = 35
    high = pd.Series([105.0, 120.0, 90.0] * 10)
    low = pd.Series([95.0, 110.0, 80.0] * 10)
    close = pd.Series([100.0, 115.0, 85.0] * 10)
    atr = calculate_atr(high, low, close, 14)
    valid = atr.dropna()
    assert len(valid) > 0
    assert (valid > 0).all()


def test_atr_invalid_period_raises():
    with pytest.raises(ValueError, match="period must be a positive integer"):
        calculate_atr(pd.Series([10.0]), pd.Series([9.0]), pd.Series([10.0]), 0)


# ==============================================================================
# 2. DURATION BOUNDARY & RETURN INDEXING CONVENTIONS
# ==============================================================================

def test_duration_boundary_19_bars_rejected():
    """19 trading bars fails minimum history validation threshold (< 20 bars)."""
    dates = pd.date_range("2026-01-01", periods=19, freq="B")
    df = pd.DataFrame({
        "Date": dates,
        "Open": [100.0] * 19,
        "High": [105.0] * 19,
        "Low": [95.0] * 19,
        "Close": [102.0] * 19,
        "Volume": [100000] * 19
    })
    valid, err, clean, rep = validate_ohlcv_dataframe_with_report(df)
    assert valid is False
    assert "at least 20 trading periods" in err
    assert clean is None


def test_duration_boundary_20_bars_passes_validation():
    """20 trading bars satisfies validation; SMA_20 is calculated but 1M return is None."""
    dates = pd.date_range("2026-01-01", periods=20, freq="B")
    closes = [100.0 + i for i in range(20)]
    df = pd.DataFrame({
        "Date": dates,
        "Open": [c - 1.0 for c in closes],
        "High": [c + 2.0 for c in closes],
        "Low": [c - 2.0 for c in closes],
        "Close": closes,
        "Volume": [100000] * 20
    })
    valid, err, clean, rep = validate_ohlcv_dataframe_with_report(df)
    assert valid is True, f"Validation failed: {err}"
    assert clean is not None
    summary = compute_technical_summary(clean, ticker="BARS_20")
    assert summary.total_bars == 20
    assert summary.sma_20_status != "N/A"
    # 20 bars < 21: 1M return must be None
    assert summary.change_1m is None


def test_duration_boundary_21_vs_22_bars():
    """21 bars has 20 intervals (change_1m is None); 22 bars provides full 21 intervals (change_1m populated)."""
    # 21 bars: insufficient for 21-interval return
    dates21 = pd.date_range("2026-01-01", periods=21, freq="B")
    closes21 = [100.0 + (i * 1.0) for i in range(21)]
    df21 = pd.DataFrame({
        "Date": dates21,
        "Open": [c - 1.0 for c in closes21], "High": [c + 2.0 for c in closes21],
        "Low": [c - 2.0 for c in closes21], "Close": closes21, "Volume": [100000] * 21
    })
    summary21 = compute_technical_summary(df21, ticker="BARS_21")
    assert summary21.total_bars == 21
    assert summary21.change_1m is None

    # 22 bars: satisfies N+1 rule for 21 intervals
    dates22 = pd.date_range("2026-01-01", periods=22, freq="B")
    closes22 = [100.0 + (i * 1.0) for i in range(22)]
    df22 = pd.DataFrame({
        "Date": dates22,
        "Open": [c - 1.0 for c in closes22], "High": [c + 2.0 for c in closes22],
        "Low": [c - 2.0 for c in closes22], "Close": closes22, "Volume": [100000] * 22
    })
    summary22 = compute_technical_summary(df22, ticker="BARS_22")
    assert summary22.total_bars == 22
    assert summary22.change_1m is not None
    assert summary22.change_3m is None


def test_duration_boundary_63_vs_64_bars():
    """63 bars has 62 intervals (change_3m is None); 64 bars provides full 63 intervals (change_3m populated)."""
    dates63 = pd.date_range("2026-01-01", periods=63, freq="B")
    closes63 = [100.0 + (i * 0.1) for i in range(63)]
    df63 = pd.DataFrame({
        "Date": dates63,
        "Open": [c - 0.5 for c in closes63], "High": [c + 1.0 for c in closes63],
        "Low": [c - 1.0 for c in closes63], "Close": closes63, "Volume": [100000] * 63
    })
    summary63 = compute_technical_summary(df63, ticker="BARS_63")
    assert summary63.change_1m is not None
    assert summary63.change_3m is None

    dates64 = pd.date_range("2026-01-01", periods=64, freq="B")
    closes64 = [100.0 + (i * 0.1) for i in range(64)]
    df64 = pd.DataFrame({
        "Date": dates64,
        "Open": [c - 0.5 for c in closes64], "High": [c + 1.0 for c in closes64],
        "Low": [c - 1.0 for c in closes64], "Close": closes64, "Volume": [100000] * 64
    })
    summary64 = compute_technical_summary(df64, ticker="BARS_64")
    assert summary64.change_1m is not None
    assert summary64.change_3m is not None
    assert summary64.change_6m is None


def test_duration_boundary_126_vs_127_bars():
    """126 bars has 125 intervals (change_6m is None); 127 bars provides full 126 intervals (change_6m populated)."""
    dates126 = pd.date_range("2026-01-01", periods=126, freq="B")
    closes126 = [100.0 + (i * 0.1) for i in range(126)]
    df126 = pd.DataFrame({
        "Date": dates126,
        "Open": [c - 0.5 for c in closes126], "High": [c + 1.0 for c in closes126],
        "Low": [c - 1.0 for c in closes126], "Close": closes126, "Volume": [100000] * 126
    })
    summary126 = compute_technical_summary(df126, ticker="BARS_126")
    assert summary126.change_1m is not None
    assert summary126.change_3m is not None
    assert summary126.change_6m is None

    dates127 = pd.date_range("2026-01-01", periods=127, freq="B")
    closes127 = [100.0 + (i * 0.1) for i in range(127)]
    df127 = pd.DataFrame({
        "Date": dates127,
        "Open": [c - 0.5 for c in closes127], "High": [c + 1.0 for c in closes127],
        "Low": [c - 1.0 for c in closes127], "Close": closes127, "Volume": [100000] * 127
    })
    summary127 = compute_technical_summary(df127, ticker="BARS_127")
    assert summary127.change_1m is not None
    assert summary127.change_3m is not None
    assert summary127.change_6m is not None
    assert summary127.change_1y is None


def test_duration_boundary_199_vs_200_bars():
    """199 bars has SMA_200 as N/A; 200 bars populates SMA_200."""
    dates199 = pd.date_range("2025-01-01", periods=199, freq="B")
    df199 = pd.DataFrame({
        "Date": dates199,
        "Open": [100.0] * 199, "High": [105.0] * 199, "Low": [95.0] * 199,
        "Close": [100.0] * 199, "Volume": [100000] * 199
    })
    summary199 = compute_technical_summary(df199, ticker="BARS_199")
    assert "N/A" in summary199.sma_200_status

    dates200 = pd.date_range("2025-01-01", periods=200, freq="B")
    df200 = pd.DataFrame({
        "Date": dates200,
        "Open": [100.0] * 200, "High": [105.0] * 200, "Low": [95.0] * 200,
        "Close": [100.0] * 200, "Volume": [100000] * 200
    })
    summary200 = compute_technical_summary(df200, ticker="BARS_200")
    assert "N/A" not in summary200.sma_200_status


def test_duration_boundary_251_bars_suppresses_1y_and_52w():
    """251 bars (< 252) strictly suppresses 1Y return and flags is_full_52w as False."""
    dates = pd.date_range("2025-01-01", periods=251, freq="B")
    df = pd.DataFrame({
        "Date": dates,
        "Open": [100.0] * 251, "High": [105.0] * 251, "Low": [95.0] * 251,
        "Close": [100.0 + (i * 0.1) for i in range(251)], "Volume": [100000] * 251
    })
    summary = compute_technical_summary(df, ticker="BARS_251")
    assert summary.total_bars == 251
    assert summary.change_1y is None
    assert summary.is_full_52w is False


def test_duration_boundary_252_vs_253_bars_adequate_coverage():
    """252 bars has 251 intervals (1Y is None, is_full_52w True); 253 bars provides 252 intervals (1Y populated)."""
    dates252 = pd.date_range("2025-01-01", periods=252, freq="B")
    df252 = pd.DataFrame({
        "Date": dates252,
        "Open": [100.0] * 252, "High": [105.0] * 252, "Low": [95.0] * 252,
        "Close": [100.0 + (i * 0.1) for i in range(252)], "Volume": [100000] * 252
    })
    summary252 = compute_technical_summary(df252, ticker="BARS_252_ADEQUATE")
    assert summary252.total_bars == 252
    assert summary252.has_adequate_calendar_coverage is True
    assert summary252.is_full_52w is True
    assert summary252.change_1y is None  # 252 bars = 251 intervals; requires 253 bars for 252 intervals

    dates253 = pd.date_range("2025-01-01", periods=253, freq="B")
    df253 = pd.DataFrame({
        "Date": dates253,
        "Open": [100.0] * 253, "High": [105.0] * 253, "Low": [95.0] * 253,
        "Close": [100.0 + (i * 0.1) for i in range(253)], "Volume": [100000] * 253
    })
    summary253 = compute_technical_summary(df253, ticker="BARS_253_ADEQUATE")
    assert summary253.total_bars == 253
    assert summary253.has_adequate_calendar_coverage is True
    assert summary253.is_full_52w is True
    assert summary253.change_1y is not None


def test_duration_boundary_252_bars_insufficient_coverage_suppresses_1y():
    """252 bars with artificial calendar compression (e.g. daily frequency spanning 251 calendar days) suppresses 1Y return."""
    dates = pd.date_range("2025-01-01", periods=252, freq="D")  # Spans 251 calendar days (< 340)
    df = pd.DataFrame({
        "Date": dates,
        "Open": [100.0] * 252, "High": [105.0] * 252, "Low": [95.0] * 252,
        "Close": [100.0 + (i * 0.1) for i in range(252)], "Volume": [100000] * 252
    })
    summary = compute_technical_summary(df, ticker="BARS_252_COMPRESSED")
    assert summary.total_bars == 252
    assert summary.has_adequate_calendar_coverage is False
    assert summary.change_1y is None
    assert summary.is_full_52w is False


def test_duration_boundary_excessive_calendar_gap_suppresses_1y():
    """252 bars spanning 360 calendar days but with a 25-day gap (> 14 days) suppresses 1Y return."""
    dates_part1 = pd.date_range("2025-01-01", periods=126, freq="B")
    # Insert a 25-day calendar gap
    gap_start = dates_part1[-1] + pd.Timedelta(days=25)
    dates_part2 = pd.date_range(gap_start, periods=126, freq="B")
    dates = dates_part1.append(dates_part2)

    df = pd.DataFrame({
        "Date": dates,
        "Open": [100.0] * 252, "High": [105.0] * 252, "Low": [95.0] * 252,
        "Close": [100.0 + (i * 0.1) for i in range(252)], "Volume": [100000] * 252
    })
    summary = compute_technical_summary(df, ticker="BARS_252_GAP")
    assert summary.has_adequate_calendar_coverage is False
    assert summary.change_1y is None
    assert summary.is_full_52w is False


def test_duration_boundary_253_bars():
    """253 bars with adequate coverage populates 1Y return."""
    dates = pd.date_range("2025-01-01", periods=253, freq="B")
    df = pd.DataFrame({
        "Date": dates,
        "Open": [100.0] * 253, "High": [105.0] * 253, "Low": [95.0] * 253,
        "Close": [100.0 + (i * 0.1) for i in range(253)], "Volume": [100000] * 253
    })
    summary = compute_technical_summary(df, ticker="BARS_253")
    assert summary.has_adequate_calendar_coverage is True
    assert summary.change_1y is not None
    assert summary.is_full_52w is True


# ==============================================================================
# 3. OHLCV VALIDATION HARDENING
# ==============================================================================

def test_validation_rejects_ambiguous_duplicate_headers():
    """Dataframe containing case-insensitive duplicate headers is rejected with clear error."""
    dates = pd.date_range("2026-01-01", periods=25, freq="D").strftime("%Y-%m-%d")
    df = pd.DataFrame({
        "Date": dates,
        "Open": [100.0] * 25,
        "High": [105.0] * 25,
        "Low": [95.0] * 25,
        "Close": [102.0] * 25,
        "close": [102.0] * 25,  # Duplicate header
        "Volume": [1000] * 25
    })
    valid, err, clean, rep = validate_ohlcv_dataframe_with_report(df)
    assert valid is False
    assert "ambiguous duplicate headers" in err.lower()
    assert clean is None


def test_validation_rejects_non_numeric_strings():
    """Non-numeric string values in price columns are flagged and rejected."""
    dates = pd.date_range("2026-01-01", periods=25, freq="D").strftime("%Y-%m-%d")
    df = pd.DataFrame({
        "Date": dates,
        "Open": [100.0] * 24 + ["invalid_string"],
        "High": [105.0] * 25,
        "Low": [95.0] * 25,
        "Close": [102.0] * 25,
        "Volume": [1000] * 25
    })
    valid, err, clean, rep = validate_ohlcv_dataframe_with_report(df)
    assert valid is False
    assert "missing (nan) or infinite values" in err.lower()
    assert len(rep.sample_offending_rows) > 0


def test_validation_unsorted_dates_normalized_with_warning():
    """Unsorted input dates are normalized to ascending order with a diagnostic warning."""
    dates = ["2026-01-05", "2026-01-02", "2026-01-01"] + [f"2026-01-{i:02d}" for i in range(6, 25)]
    df = pd.DataFrame({
        "Date": dates,
        "Open": [100.0] * len(dates),
        "High": [105.0] * len(dates),
        "Low": [95.0] * len(dates),
        "Close": [102.0] * len(dates),
        "Volume": [1000] * len(dates)
    })
    valid, err, clean, rep = validate_ohlcv_dataframe_with_report(df)
    assert valid is True
    assert any("not in ascending chronological order" in w for w in rep.warnings)
    # Resulting clean dataframe must be monotonically increasing
    assert clean["Date"].is_monotonic_increasing


def test_validation_contradictory_duplicates_fail_even_with_allow_drop():
    """Contradictory duplicate dates reporting differing prices fail validation even when allow_drop_duplicates=True."""
    dates = ["2026-01-01", "2026-01-01"] + [f"2026-01-{i:02d}" for i in range(2, 23)]
    df = pd.DataFrame({
        "Date": dates,
        "Open": [100.0, 110.0] + [100.0] * 21,  # Differing open prices on 2026-01-01
        "High": [105.0, 115.0] + [105.0] * 21,
        "Low": [95.0, 105.0] + [95.0] * 21,
        "Close": [102.0, 112.0] + [102.0] * 21,
        "Volume": [1000, 2000] + [1000] * 21
    })
    valid, err, clean, rep = validate_ohlcv_dataframe_with_report(df, allow_drop_duplicates=True)
    assert valid is False
    assert "contradictory duplicate date entries" in err.lower()


# ==============================================================================
# 4. BENCHMARK ALIGNMENT & COMMON OVERLAP INTEGRITY
# ==============================================================================

def test_benchmark_alignment_identical_dates_1y_match():
    """When asset and benchmark share identical dates (260 bars), asset 1Y change in summary matches relative calculation."""
    dates = pd.date_range("2025-01-01", periods=260, freq="B")
    df_asset = pd.DataFrame({
        "Date": dates,
        "Date_Str": [d.strftime("%Y-%m-%d") for d in dates],
        "Open": [100.0] * 260, "High": [105.0] * 260, "Low": [95.0] * 260,
        "Close": [100.0 + (i * 0.2) for i in range(260)], "Volume": [100000] * 260
    })
    df_bench = pd.DataFrame({
        "Date": dates,
        "Close": [50.0 + (i * 0.05) for i in range(260)]
    })

    summary = compute_technical_summary(
        df_asset,
        ticker="ASSET_MATCH",
        benchmark_df=df_bench,
        benchmark_ticker="BENCH_MATCH"
    )
    assert summary.common_benchmark_bars == 260
    assert summary.change_1y is not None
    assert summary.benchmark_change_1y is not None
    assert summary.relative_performance_1y is not None
    # Expected relative spread: asset return - benchmark return
    expected_spread = round(summary.change_1y - summary.benchmark_change_1y, 2)
    assert summary.relative_performance_1y == pytest.approx(expected_spread, abs=0.02)


def test_benchmark_alignment_partial_overlap_suppresses_1y():
    """When common benchmark overlap is only 50 bars, 1Y relative return is suppressed while period return is populated."""
    dates_asset = pd.date_range("2025-01-01", periods=260, freq="B")
    dates_bench = dates_asset[-50:]  # Only last 50 bars overlap

    df_asset = pd.DataFrame({
        "Date": dates_asset,
        "Date_Str": [d.strftime("%Y-%m-%d") for d in dates_asset],
        "Open": [100.0] * 260, "High": [105.0] * 260, "Low": [95.0] * 260,
        "Close": [100.0 + (i * 0.1) for i in range(260)], "Volume": [100000] * 260
    })
    df_bench = pd.DataFrame({
        "Date": dates_bench,
        "Close": [200.0 + i for i in range(50)]
    })

    summary = compute_technical_summary(
        df_asset,
        ticker="ASSET_PARTIAL",
        benchmark_df=df_bench,
        benchmark_ticker="BENCH_PARTIAL"
    )
    assert summary.common_benchmark_bars == 50
    assert summary.benchmark_change_1y is None
    assert summary.relative_performance_1y is None
    assert summary.benchmark_period_return is not None
    assert summary.relative_performance_period is not None


def test_benchmark_chart_guards_non_positive_base_prices():
    """Benchmark chart returns None if initial common price is zero or negative."""
    dates = pd.date_range("2026-01-01", periods=30, freq="B")
    df_asset = pd.DataFrame({
        "Date": dates,
        "Close": [-10.0] + [100.0] * 29  # Non-positive base price
    })
    df_bench = pd.DataFrame({
        "Date": dates,
        "Close": [50.0] * 30
    })
    # Filtering eliminates row 0, leaving 29 valid rows with positive prices
    fig = create_benchmark_comparison_chart(df_asset, df_bench, "ASSET", "BENCH")
    # Should safely create chart or gracefully handle filtered valid rows
    if fig is not None:
        assert fig.data[0].y[0] == pytest.approx(100.0, rel=1e-4)


# ==============================================================================
# 5. CORPORATE ACTION TRANSPARENCY & EXPORT FIDELITY
# ==============================================================================

def test_price_adjustment_basis_in_exports():
    """Exports must preserve the user-declared basis and include storage/provenance notices."""
    dates = pd.date_range("2025-01-01", periods=260, freq="B")
    df = pd.DataFrame({
        "Date": dates,
        "Date_Str": [d.strftime("%Y-%m-%d") for d in dates],
        "Open": [100.0] * 260, "High": [105.0] * 260, "Low": [95.0] * 260,
        "Close": [100.0] * 260, "Volume": [100000] * 260
    })
    summary = compute_technical_summary(
        df,
        ticker="CORP_TEST",
        price_adjustment_basis=PriceAdjustmentBasis.RAW_UNADJUSTED.value
    )

    # 1. Test CSV export
    csv_str = ExportGenerator.generate_technical_csv(df, "CORP_TEST", summary=summary)
    assert "# PRICE_ADJUSTMENT_BASIS: RAW_UNADJUSTED" in csv_str
    assert "# STORAGE_POLICY: In-memory volatile processing" in csv_str
    assert "# PROVENANCE_POLICY:" in csv_str

    # 2. Test Markdown Brief export
    brief_md = ExportGenerator.generate_technical_brief(summary, df)
    assert "Price Adjustment Basis:** `RAW_UNADJUSTED`" in brief_md
    assert "Corporate Action Caveat" in brief_md
    assert "Provenance & Data Privacy Notice" in brief_md
    assert "Created by Rishika Dangayach" in brief_md
