"""
Unit tests for Pure-Python Technical Analysis MVP Engine (Workstream D & Phase 8 Integrity).
Tests:
- Dataframe validation with structured OHLCVValidationReport
- Strict OHLC range invariants (High >= max(O,C,L), Low <= min(O,C,H))
- Duplicate dates and contradictory duplicate rows
- Non-finite numbers and positivity constraints
- Indicator calculations (SMA, EMA, RSI with flat series handling, MACD, BB, ATR)
- Duration-guarded technical summary (1Y returns, 52W High/Low coverage)
- Benchmark duration guards (no 1Y label on short overlapping histories)
- Template generation and format
"""

import io
import pytest
import pandas as pd
import numpy as np

from fundamentals_lens.technical import (
    validate_ohlcv_dataframe,
    calculate_sma,
    calculate_ema,
    calculate_rsi,
    calculate_macd,
    calculate_bollinger_bands,
    calculate_atr,
    compute_technical_indicators,
    compute_technical_summary,
    get_ohlcv_csv_template,
)
from fundamentals_lens.models import TechnicalSummary, OHLCVValidationReport


@pytest.fixture
def sample_short_ohlcv_df():
    """30 trading days of sample data."""
    dates = pd.date_range("2026-01-01", periods=30, freq="B")
    data = []
    base_price = 100.0
    for i, d in enumerate(dates):
        close = base_price + (i * 0.5)
        high = close + 1.5
        low = close - 1.2
        open_p = close - 0.2
        vol = 1000000 + (i * 10000)
        data.append({
            "Date": d.strftime("%Y-%m-%d"),
            "Open": open_p,
            "High": high,
            "Low": low,
            "Close": close,
            "Volume": vol
        })
    return pd.DataFrame(data)


@pytest.fixture
def sample_260_ohlcv_df():
    """260 trading days of sample data (full annual horizon)."""
    dates = pd.date_range("2025-10-01", periods=260, freq="B")
    data = []
    base_price = 100.0
    for i, d in enumerate(dates):
        close = base_price + (i * 0.2)
        high = close + 1.0
        low = close - 1.0
        open_p = close - 0.1
        vol = 500000
        data.append({
            "Date": d.strftime("%Y-%m-%d"),
            "Open": open_p,
            "High": high,
            "Low": low,
            "Close": close,
            "Volume": vol
        })
    return pd.DataFrame(data)


def test_validate_ohlcv_dataframe_valid(sample_short_ohlcv_df):
    is_valid, err, clean_df, report = validate_ohlcv_dataframe(sample_short_ohlcv_df)
    assert is_valid is True
    assert err is None
    assert len(clean_df) == 30
    assert isinstance(report, OHLCVValidationReport)
    assert report.is_valid is True
    assert report.error_count == 0


def test_validate_ohlcv_dataframe_case_insensitive():
    dates = pd.date_range("2026-01-01", periods=24, freq="D").strftime("%Y-%m-%d")
    df = pd.DataFrame({
        "date": dates,
        "OPEN": [100.0] * 24,
        "high": [105.0] * 24,
        "Low": [98.0] * 24,
        "CLOSE": [102.0] * 24,
        "volume": [500000] * 24
    })
    is_valid, err, clean_df, report = validate_ohlcv_dataframe(df)
    assert is_valid is True
    assert "Close" in clean_df.columns


def test_validate_ohlcv_dataframe_missing_columns():
    df = pd.DataFrame({
        "Date": ["2026-01-01"],
        "Close": [100.0]
    })
    is_valid, err, clean_df, report = validate_ohlcv_dataframe(df)
    assert is_valid is False
    assert "Missing required headers" in err
    assert clean_df is None
    assert report.is_valid is False


def test_validate_ohlcv_dataframe_insufficient_bars():
    df = pd.DataFrame({
        "Date": pd.date_range("2026-01-01", periods=10, freq="D"),
        "Open": [100.0] * 10,
        "High": [105.0] * 10,
        "Low": [95.0] * 10,
        "Close": [102.0] * 10,
        "Volume": [1000] * 10
    })
    is_valid, err, clean_df, report = validate_ohlcv_dataframe(df)
    assert is_valid is False
    assert "Insufficient trading observations" in err
    assert report.valid_rows == 10


def test_validate_ohlcv_dataframe_range_invariants():
    # 1. High < Low
    dates = pd.date_range("2026-01-01", periods=25, freq="D")
    df1 = pd.DataFrame({
        "Date": dates,
        "Open": [100.0] * 25,
        "High": [90.0] * 25,
        "Low": [95.0] * 25,
        "Close": [92.0] * 25,
        "Volume": [1000] * 25
    })
    is_valid1, err1, _, report1 = validate_ohlcv_dataframe(df1)
    assert is_valid1 is False
    assert "Price invariant violation" in err1
    assert len(report1.invariant_violation_dates) > 0

    # 2. High < Open (even if High >= Low)
    df2 = pd.DataFrame({
        "Date": dates,
        "Open": [105.0] * 25,
        "High": [102.0] * 25,
        "Low": [95.0] * 25,
        "Close": [98.0] * 25,
        "Volume": [1000] * 25
    })
    is_valid2, err2, _, _ = validate_ohlcv_dataframe(df2)
    assert is_valid2 is False
    assert "Price invariant violation" in err2

    # 3. Low > Close (even if High >= Low)
    df3 = pd.DataFrame({
        "Date": dates,
        "Open": [100.0] * 25,
        "High": [108.0] * 25,
        "Low": [99.0] * 25,
        "Close": [95.0] * 25,
        "Volume": [1000] * 25
    })
    is_valid3, err3, _, _ = validate_ohlcv_dataframe(df3)
    assert is_valid3 is False
    assert "Price invariant violation" in err3


def test_validate_ohlcv_dataframe_duplicates():
    # Duplicate dates with contradictory prices
    dates = ["2026-01-01", "2026-01-01"] + [f"2026-01-{i:02d}" for i in range(2, 25)]
    df = pd.DataFrame({
        "Date": dates,
        "Open": [100.0, 105.0] + [100.0] * 23,
        "High": [110.0, 115.0] + [110.0] * 23,
        "Low": [95.0, 98.0] + [95.0] * 23,
        "Close": [105.0, 108.0] + [105.0] * 23,
        "Volume": [1000] * 25
    })
    is_valid, err, _, report = validate_ohlcv_dataframe(df, allow_drop_duplicates=False)
    assert is_valid is False
    assert "Contradictory duplicate date entries detected" in err
    assert "2026-01-01" in report.duplicate_dates


def test_validate_ohlcv_dataframe_non_finite_and_non_positive():
    dates = pd.date_range("2026-01-01", periods=25, freq="D")
    # NaN in close
    df_nan = pd.DataFrame({
        "Date": dates,
        "Open": [100.0] * 25,
        "High": [105.0] * 25,
        "Low": [95.0] * 25,
        "Close": [102.0] * 24 + [np.nan],
        "Volume": [1000] * 25
    })
    is_valid_nan, err_nan, _, report_nan = validate_ohlcv_dataframe(df_nan)
    assert is_valid_nan is False
    assert "missing (NaN) or infinite values" in err_nan

    # Zero or negative price
    df_zero = pd.DataFrame({
        "Date": dates,
        "Open": [100.0] * 25,
        "High": [105.0] * 25,
        "Low": [0.0] * 25,  # Invalid zero price
        "Close": [102.0] * 25,
        "Volume": [1000] * 25
    })
    is_valid_zero, err_zero, _, _ = validate_ohlcv_dataframe(df_zero)
    assert is_valid_zero is False
    assert "non-positive price values" in err_zero


def test_calculate_sma(sample_short_ohlcv_df):
    sma20 = calculate_sma(sample_short_ohlcv_df["Close"], 20)
    assert len(sma20) == 30
    assert pd.isna(sma20.iloc[18])
    assert pd.notna(sma20.iloc[19])
    assert round(sma20.iloc[19], 2) == 104.75


def test_calculate_rsi_normal_and_flat(sample_short_ohlcv_df):
    # Rising series: high RSI
    rsi = calculate_rsi(sample_short_ohlcv_df["Close"], 14)
    valid_rsi = rsi.dropna()
    assert (valid_rsi >= 0.0).all()
    assert (valid_rsi <= 100.0).all()
    assert valid_rsi.iloc[-1] > 90.0

    # Flat series: RSI must be exactly 50.0 (neutral)
    flat_series = pd.Series([100.0] * 30)
    rsi_flat = calculate_rsi(flat_series, 14)
    valid_flat = rsi_flat.dropna()
    assert (valid_flat == 50.0).all()


def test_calculate_macd(sample_short_ohlcv_df):
    macd, signal, hist = calculate_macd(sample_short_ohlcv_df["Close"], 12, 26, 9)
    assert len(macd) == 30
    diff = (macd - signal).round(2)
    assert np.allclose(hist.dropna(), diff.dropna(), atol=0.01)


def test_calculate_bollinger_bands(sample_short_ohlcv_df):
    upper, mid, lower = calculate_bollinger_bands(sample_short_ohlcv_df["Close"], 20, 2.0)
    valid_idx = upper.dropna().index
    assert (upper.loc[valid_idx] >= mid.loc[valid_idx]).all()
    assert (mid.loc[valid_idx] >= lower.loc[valid_idx]).all()


def test_calculate_atr(sample_short_ohlcv_df):
    atr = calculate_atr(sample_short_ohlcv_df["High"], sample_short_ohlcv_df["Low"], sample_short_ohlcv_df["Close"], 14)
    valid_atr = atr.dropna()
    assert len(valid_atr) > 0
    assert (valid_atr > 0).all()


def test_compute_technical_summary_duration_guards(sample_short_ohlcv_df, sample_260_ohlcv_df):
    # 1. Short Series (30 bars): change_1y MUST BE None, is_full_52w MUST BE False
    _, _, clean_short, _ = validate_ohlcv_dataframe(sample_short_ohlcv_df)
    summary_short = compute_technical_summary(clean_short, ticker="SHORT_ASSET")
    assert summary_short.total_bars == 30
    assert summary_short.change_1y is None
    assert summary_short.is_full_52w is False
    assert summary_short.high_52w is not None

    # 2. Full Series (260 bars): change_1y populated, is_full_52w is True
    _, _, clean_long, _ = validate_ohlcv_dataframe(sample_260_ohlcv_df)
    summary_long = compute_technical_summary(clean_long, ticker="LONG_ASSET")
    assert summary_long.total_bars == 260
    assert summary_long.change_1y is not None
    assert summary_long.is_full_52w is True


def test_benchmark_duration_guards_not_falsely_labeled_1y(sample_short_ohlcv_df, sample_260_ohlcv_df):
    # Short overlapping window (30 bars): benchmark_change_1y MUST BE None!
    _, _, clean_short, _ = validate_ohlcv_dataframe(sample_short_ohlcv_df)
    bench_short = sample_short_ohlcv_df.copy()
    bench_short["Close"] = 100.0 + (bench_short.index * 0.1)
    bench_short["Open"] = bench_short["Close"] - 0.1
    bench_short["High"] = bench_short["Close"] + 0.5
    bench_short["Low"] = bench_short["Close"] - 0.5
    is_v, err, clean_bench_short, _ = validate_ohlcv_dataframe(bench_short)
    assert is_v is True, f"Benchmark validation failed: {err}"

    summary_short = compute_technical_summary(
        clean_short,
        ticker="ASSET_SHORT",
        benchmark_df=clean_bench_short,
        benchmark_ticker="BENCH_SHORT"
    )
    assert summary_short.benchmark_ticker == "BENCH_SHORT"
    assert summary_short.common_benchmark_bars == 30
    # Must NOT label 30 bars as 1-year performance!
    assert summary_short.benchmark_change_1y is None
    assert summary_short.relative_performance_1y is None
    # But period return should be captured for the available common window
    assert summary_short.benchmark_period_return is not None
    assert summary_short.relative_performance_period is not None

    # Full 260-bar overlapping window: benchmark_change_1y IS populated
    _, _, clean_long, _ = validate_ohlcv_dataframe(sample_260_ohlcv_df)
    bench_long = sample_260_ohlcv_df.copy()
    bench_long["Close"] = 100.0 + (bench_long.index * 0.05)
    bench_long["Open"] = bench_long["Close"] - 0.05
    bench_long["High"] = bench_long["Close"] + 0.5
    bench_long["Low"] = bench_long["Close"] - 0.5
    is_vl, err_l, clean_bench_long, _ = validate_ohlcv_dataframe(bench_long)
    assert is_vl is True, f"Benchmark long validation failed: {err_l}"

    summary_long = compute_technical_summary(
        clean_long,
        ticker="ASSET_LONG",
        benchmark_df=clean_bench_long,
        benchmark_ticker="BENCH_LONG"
    )
    assert summary_long.common_benchmark_bars == 260
    assert summary_long.benchmark_change_1y is not None
    assert summary_long.relative_performance_1y is not None


def test_csv_template():
    tpl = get_ohlcv_csv_template()
    assert "Date,Open,High,Low,Close,Volume" in tpl
    assert "# Invariants:" in tpl
    # Load ignoring comments
    df = pd.read_csv(io.StringIO(tpl), comment="#")
    assert len(df) == 5
    assert set(["Date", "Open", "High", "Low", "Close", "Volume"]).issubset(set(df.columns))


def test_validate_ohlcv_dataframe_strict_iso_date_format():
    # Slash-delimited dates like DD/MM/YYYY or MM/DD/YYYY should fail strict ISO format
    bad_dates = [f"2026/01/{i:02d}" for i in range(1, 26)]
    df = pd.DataFrame({
        "Date": bad_dates,
        "Open": [100.0] * 25,
        "High": [105.0] * 25,
        "Low": [95.0] * 25,
        "Close": [102.0] * 25,
        "Volume": [1000] * 25
    })
    is_valid, err, _, report = validate_ohlcv_dataframe(df)
    assert is_valid is False
    assert "strictly conform to ISO 8601 YYYY-MM-DD" in err
    assert report.is_valid is False


def test_technical_summary_251_252_253_boundaries():
    """Verify exact 251, 252, and 253 bar boundaries with daily business days."""
    dates_251 = pd.date_range("2025-10-15", periods=251, freq="B").strftime("%Y-%m-%d")
    df_251 = pd.DataFrame({
        "Date": dates_251,
        "Open": [100.0] * 251,
        "High": [105.0] * 251,
        "Low": [95.0] * 251,
        "Close": [102.0] * 251,
        "Volume": [1000] * 251
    })
    _, _, clean_251, _ = validate_ohlcv_dataframe(df_251)
    summary_251 = compute_technical_summary(clean_251, ticker="ASSET_251")
    assert summary_251.total_bars == 251
    assert summary_251.change_1y is None
    assert summary_251.is_full_52w is False

    dates_252 = pd.date_range("2025-10-15", periods=252, freq="B").strftime("%Y-%m-%d")
    closes_252 = [100.0 + (i * 0.1) for i in range(252)]
    df_252 = pd.DataFrame({
        "Date": dates_252,
        "Open": [c - 0.05 for c in closes_252],
        "High": [c + 1.0 for c in closes_252],
        "Low": [c - 1.0 for c in closes_252],
        "Close": closes_252,
        "Volume": [1000] * 252
    })
    is_v, err, clean_252, _ = validate_ohlcv_dataframe(df_252)
    assert is_v is True, err
    summary_252 = compute_technical_summary(clean_252, ticker="ASSET_252")
    assert summary_252.total_bars == 252
    assert summary_252.is_full_52w is True
    # 252 bars spans only 251 return intervals; standardized N+1 rule requires 253 bars for 252-interval return
    assert summary_252.change_1y is None

    dates_253 = pd.date_range("2025-10-15", periods=253, freq="B").strftime("%Y-%m-%d")
    closes_253 = [100.0 + (i * 0.1) for i in range(253)]
    df_253 = pd.DataFrame({
        "Date": dates_253,
        "Open": [c - 0.05 for c in closes_253],
        "High": [c + 1.0 for c in closes_253],
        "Low": [c - 1.0 for c in closes_253],
        "Close": closes_253,
        "Volume": [1000] * 253
    })
    is_v, err, clean_253, _ = validate_ohlcv_dataframe(df_253)
    assert is_v is True, err
    summary_253 = compute_technical_summary(clean_253, ticker="ASSET_253")
    assert summary_253.total_bars == 253
    assert summary_253.has_adequate_calendar_coverage is True
    assert summary_253.is_full_52w is True
    assert summary_253.change_1y is not None


def test_technical_summary_sparse_dates_spanning_years_suppresses_1y():
    """Verify that 252 bars sparse over 5 years (1 bar/week) suppresses 1Y return."""
    dates_sparse = pd.date_range("2020-01-01", periods=252, freq="7D").strftime("%Y-%m-%d")
    df_sparse = pd.DataFrame({
        "Date": dates_sparse,
        "Open": [100.0] * 252,
        "High": [105.0] * 252,
        "Low": [95.0] * 252,
        "Close": [102.0] * 252,
        "Volume": [1000] * 252
    })
    _, _, clean_sparse, _ = validate_ohlcv_dataframe(df_sparse)
    summary_sparse = compute_technical_summary(clean_sparse, ticker="ASSET_SPARSE")
    assert summary_sparse.total_bars == 252
    # 252 bars * 7 days = ~1764 days (not ~365 days)
    assert summary_sparse.coverage_calendar_days > 1000
    assert summary_sparse.has_adequate_calendar_coverage is False
    assert summary_sparse.is_full_52w is False
    assert summary_sparse.change_1y is None


def test_technical_summary_irregular_large_gap_suppresses_1y():
    """Verify that 252 bars containing an anomalous large gap (> 14 days) suppresses 1Y return."""
    # 126 bars in 2025, 40-day hiatus gap, then 126 bars
    part1 = pd.date_range("2025-06-01", periods=126, freq="B")
    gap_date = part1[-1] + pd.Timedelta(days=40)
    part2 = pd.date_range(gap_date, periods=126, freq="B")
    all_dates = list(part1.strftime("%Y-%m-%d")) + list(part2.strftime("%Y-%m-%d"))
    assert len(all_dates) == 252

    df_gap = pd.DataFrame({
        "Date": all_dates,
        "Open": [100.0] * 252,
        "High": [105.0] * 252,
        "Low": [95.0] * 252,
        "Close": [102.0] * 252,
        "Volume": [1000] * 252
    })
    _, _, clean_gap, _ = validate_ohlcv_dataframe(df_gap)
    summary_gap = compute_technical_summary(clean_gap, ticker="ASSET_GAP")
    assert summary_gap.max_consecutive_gap_days >= 35
    assert summary_gap.has_adequate_calendar_coverage is False
    assert summary_gap.is_full_52w is False
    assert summary_gap.change_1y is None


def test_technical_summary_currency_inference():
    """Verify that Indian tickers resolve currency to INR instead of defaulting silently to USD."""
    dates = pd.date_range("2026-01-01", periods=30, freq="B").strftime("%Y-%m-%d")
    df = pd.DataFrame({
        "Date": dates,
        "Open": [3000.0] * 30,
        "High": [3050.0] * 30,
        "Low": [2950.0] * 30,
        "Close": [3020.0] * 30,
        "Volume": [100000] * 30
    })
    _, _, clean_df, _ = validate_ohlcv_dataframe(df)
    summary_tcs = compute_technical_summary(clean_df, ticker="TCS")
    assert summary_tcs.currency == "INR"

    summary_infy = compute_technical_summary(clean_df, ticker="INFY.NS")
    assert summary_infy.currency == "INR"

    summary_aapl = compute_technical_summary(clean_df, ticker="AAPL")
    assert summary_aapl.currency == "USD"


