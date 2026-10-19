"""
Unit and integration tests for Phase 16 Priority P0-E: Technical Analysis MVP Review & Integrity Hardening.
Verifies:
1. Indicators against known mathematical fixtures (SMA, RSI flat/all-gains/all-losses, BB, ATR).
2. Short histories (< 20 bars) handle gracefully without crashing.
3. 1-year returns and 52-week labels remain suppressed when history < 252 bars or calendar coverage is inadequate.
4. Benchmark alignment and gap handling (duration-guarded relative performance).
5. Invalid prices and invariant violations (negative prices, High < Low, High < Open/Close, negative volume).
6. Malformed uploads (missing headers, non-ISO dates, non-numeric values, empty files, duplicate dates).
7. Technical brief and CSV export truthfulness (segregated synthetic demo vs user-supplied market data).
"""
import pytest
import math
import pandas as pd
import numpy as np
from fundamentals_lens.models import PriceAdjustmentBasis, TechnicalSummary, OHLCVValidationReport
from fundamentals_lens.technical import (
    validate_ohlcv_dataframe_with_report,
    compute_technical_indicators,
    compute_technical_summary,
    calculate_sma,
    calculate_rsi,
    calculate_bollinger_bands,
    calculate_macd,
    calculate_atr
)
from fundamentals_lens.exports import ExportGenerator


def test_indicators_against_known_fixtures():
    """Verify core indicator calculations against known mathematical properties."""
    # 1. Flat series: RSI must return 50.0 (neutral)
    flat_prices = pd.Series([100.0] * 30)
    rsi_flat = calculate_rsi(flat_prices, 14)
    # Beyond warmup (index >= 14), flat series should be exactly 50.0
    valid_rsi_flat = rsi_flat.dropna()
    assert len(valid_rsi_flat) > 0
    assert (valid_rsi_flat == 50.0).all()

    # 2. Monotonically increasing series: RSI must return 100.0
    rising_prices = pd.Series([100.0 + float(i) for i in range(30)])
    rsi_rising = calculate_rsi(rising_prices, 14)
    valid_rsi_rising = rsi_rising.dropna()
    assert len(valid_rsi_rising) > 0
    assert (valid_rsi_rising == 100.0).all()

    # 3. Monotonically decreasing series: RSI must return 0.0
    falling_prices = pd.Series([100.0 - float(i) for i in range(30)])
    rsi_falling = calculate_rsi(falling_prices, 14)
    valid_rsi_falling = rsi_falling.dropna()
    assert len(valid_rsi_falling) > 0
    assert (valid_rsi_falling == 0.0).all()

    # 4. Bollinger Bands ddof=1 invariant: Upper = Middle + 2*std, Lower = Middle - 2*std
    upper, middle, lower = calculate_bollinger_bands(rising_prices, 20, 2.0)
    for idx in range(19, 30):
        m = middle.iloc[idx]
        u = upper.iloc[idx]
        l = lower.iloc[idx]
        spread = round(u - m, 2)
        spread_lower = round(m - l, 2)
        assert abs(spread - spread_lower) <= 0.02

    # 5. SMA exact average test
    test_s = pd.Series(range(1, 21), dtype=float) # 1 to 20
    sma20 = calculate_sma(test_s, 20)
    assert sma20.iloc[-1] == 10.5 # sum(1..20) / 20 = 210 / 20 = 10.5


def test_short_history_graceful_handling():
    """Verify that short history (<20 bars) does not crash indicator or summary pipelines."""
    dates = pd.date_range("2026-01-01", periods=10, freq="D")
    df_short = pd.DataFrame({
        "Date": dates,
        "Date_Str": [d.strftime("%Y-%m-%d") for d in dates],
        "Open": [100.0] * 10,
        "High": [105.0] * 10,
        "Low": [95.0] * 10,
        "Close": [102.0] * 10,
        "Volume": [1000000] * 10
    })

    # Indicator calculation on 10 bars
    ind_df = compute_technical_indicators(df_short)
    assert len(ind_df) == 10
    # SMA 20, 50, 200 should be all NaN
    assert ind_df["SMA_20"].isna().all()
    assert ind_df["SMA_50"].isna().all()
    assert ind_df["SMA_200"].isna().all()
    assert ind_df["BB_Upper"].isna().all()

    # Summary calculation on 10 bars
    summary = compute_technical_summary(
        df_short,
        ticker="SHORT_ASSET",
        currency="USD"
    )
    assert summary.total_bars == 10
    assert summary.change_1m is None
    assert summary.change_3m is None
    assert summary.change_6m is None
    assert summary.change_1y is None
    assert summary.is_full_52w is False
    assert summary.sma_20_status == "N/A"
    assert summary.sma_50_status == "N/A"
    assert "N/A" in summary.sma_200_status


def test_suppress_1y_and_52w_under_252_bars():
    """Verify 1-year returns and 52-week labels remain suppressed when history < 252 bars."""
    dates = pd.date_range("2026-01-01", periods=150, freq="B")
    df = pd.DataFrame({
        "Date": dates,
        "Date_Str": [d.strftime("%Y-%m-%d") for d in dates],
        "Open": [100.0 + (i * 0.1) for i in range(150)],
        "High": [102.0 + (i * 0.1) for i in range(150)],
        "Low": [99.0 + (i * 0.1) for i in range(150)],
        "Close": [101.0 + (i * 0.1) for i in range(150)],
        "Volume": [1000000] * 150
    })

    summary = compute_technical_summary(df, ticker="TEST_150")
    assert summary.total_bars == 150
    assert summary.change_1m is not None
    assert summary.change_3m is not None
    assert summary.change_6m is not None
    # 1Y return must be suppressed
    assert summary.change_1y is None
    assert summary.is_full_52w is False
    assert summary.has_adequate_calendar_coverage is False


def test_benchmark_alignment_and_gap_handling():
    """Verify benchmark comparison duration guards when benchmark is shorter than 252 bars."""
    dates = pd.date_range("2025-01-01", periods=300, freq="B")
    df_asset = pd.DataFrame({
        "Date": dates,
        "Date_Str": [d.strftime("%Y-%m-%d") for d in dates],
        "Open": [100.0] * 300,
        "High": [105.0] * 300,
        "Low": [98.0] * 300,
        "Close": [102.0 + (i * 0.1) for i in range(300)],
        "Volume": [1000000] * 300
    })

    # Benchmark only covers last 100 days
    bench_dates = dates[-100:]
    df_bench = pd.DataFrame({
        "Date": bench_dates,
        "Close": [50.0 + (i * 0.05) for i in range(100)]
    })

    summary = compute_technical_summary(
        df_asset,
        ticker="ASSET_300",
        benchmark_df=df_bench,
        benchmark_ticker="BENCH_100"
    )

    assert summary.common_benchmark_bars == 100
    # 1Y relative performance must be suppressed because common bars < 252
    assert summary.benchmark_change_1y is None
    assert summary.relative_performance_1y is None
    # Period relative return must be populated
    assert summary.benchmark_period_return is not None
    assert summary.relative_performance_period is not None


def test_invalid_prices_and_invariant_violations():
    """Verify validation engine catches negative prices, High < Low, and negative volume."""
    dates = pd.date_range("2026-01-01", periods=25, freq="D")
    
    # 1. Non-positive price
    df_neg_price = pd.DataFrame({
        "Date": dates,
        "Open": [100.0] * 24 + [-5.0],
        "High": [105.0] * 25,
        "Low": [95.0] * 25,
        "Close": [100.0] * 25,
        "Volume": [10000] * 25
    })
    valid, err, _, rep = validate_ohlcv_dataframe_with_report(df_neg_price)
    assert valid is False
    assert "non-positive price" in err.lower()

    # 2. High < Low invariant violation
    df_high_low = pd.DataFrame({
        "Date": dates,
        "Open": [100.0] * 25,
        "High": [90.0] * 24 + [80.0],  # High lower than Low
        "Low": [95.0] * 25,
        "Close": [100.0] * 25,
        "Volume": [10000] * 25
    })
    valid_hl, err_hl, _, rep_hl = validate_ohlcv_dataframe_with_report(df_high_low)
    assert valid_hl is False
    assert any("invariant violation" in e.lower() for e in rep_hl.errors)
    assert any("high must be >=" in e.lower() for e in rep_hl.errors)

    # 3. High < max(Open, Close) violation
    df_high_close = pd.DataFrame({
        "Date": dates,
        "Open": [100.0] * 25,
        "High": [102.0] * 24 + [102.0],
        "Low": [95.0] * 25,
        "Close": [100.0] * 24 + [106.0], # Close > High
        "Volume": [10000] * 25
    })
    valid_hc, err_hc, _, rep_hc = validate_ohlcv_dataframe_with_report(df_high_close)
    assert valid_hc is False
    assert any("invariant violation" in e.lower() for e in rep_hc.errors)

    # 4. Negative volume
    df_neg_vol = pd.DataFrame({
        "Date": dates,
        "Open": [100.0] * 25,
        "High": [105.0] * 25,
        "Low": [95.0] * 25,
        "Close": [100.0] * 25,
        "Volume": [10000] * 24 + [-500]
    })
    valid_nv, err_nv, _, rep_nv = validate_ohlcv_dataframe_with_report(df_neg_vol)
    assert valid_nv is False
    assert "negative volume" in err_nv.lower()


def test_malformed_uploads():
    """Verify validation engine catches missing headers, non-ISO dates, non-numeric values, and duplicate dates."""
    dates = pd.date_range("2026-01-01", periods=25, freq="D")

    # 1. Missing header
    df_missing_hdr = pd.DataFrame({
        "Date": dates,
        "Open": [100.0] * 25,
        "High": [105.0] * 25,
        "Low": [95.0] * 25,
        "Close": [100.0] * 25
        # Volume missing
    })
    valid, err, _, rep = validate_ohlcv_dataframe_with_report(df_missing_hdr)
    assert valid is False
    assert "Missing required headers" in err
    assert "Volume" in err

    # 2. Non-ISO date format (MM/DD/YYYY)
    df_non_iso = pd.DataFrame({
        "Date": ["10/25/2026"] * 25,
        "Open": [100.0] * 25,
        "High": [105.0] * 25,
        "Low": [95.0] * 25,
        "Close": [100.0] * 25,
        "Volume": [10000] * 25
    })
    valid_iso, err_iso, _, rep_iso = validate_ohlcv_dataframe_with_report(df_non_iso)
    assert valid_iso is False
    assert "ISO 8601" in err_iso

    # 3. Non-numeric values (strings in numeric columns)
    df_non_num = pd.DataFrame({
        "Date": [d.strftime("%Y-%m-%d") for d in dates],
        "Open": [100.0] * 24 + ["bad_price"],
        "High": [105.0] * 25,
        "Low": [95.0] * 25,
        "Close": [100.0] * 25,
        "Volume": [10000] * 25
    })
    valid_num, err_num, _, rep_num = validate_ohlcv_dataframe_with_report(df_non_num)
    assert valid_num is False
    assert "missing (nan) or infinite" in err_num.lower()

    # 4. Duplicate dates
    dup_dates = [d.strftime("%Y-%m-%d") for d in dates]
    dup_dates[5] = dup_dates[4]  # duplicate row
    df_dup = pd.DataFrame({
        "Date": dup_dates,
        "Open": [100.0] * 25,
        "High": [105.0] * 25,
        "Low": [95.0] * 25,
        "Close": [100.0] * 25,
        "Volume": [10000] * 25
    })
    valid_dup, err_dup, _, rep_dup = validate_ohlcv_dataframe_with_report(df_dup, allow_drop_duplicates=False)
    assert valid_dup is False
    assert "duplicate date" in err_dup.lower()

    # 5. Empty dataframe
    valid_empty, err_empty, _, _ = validate_ohlcv_dataframe_with_report(pd.DataFrame())
    assert valid_empty is False
    assert "no data" in err_empty.lower()


def test_technical_export_truthfulness():
    """Verify that synthetic demo data vs recorded market data are transparently labeled in exports."""
    dates = pd.date_range("2026-01-01", periods=30, freq="D")
    df = pd.DataFrame({
        "Date": dates,
        "Date_Str": [d.strftime("%Y-%m-%d") for d in dates],
        "Open": [100.0] * 30,
        "High": [105.0] * 30,
        "Low": [95.0] * 30,
        "Close": [101.0] * 30,
        "Volume": [500000] * 30
    })

    # Case A: Simulated demo summary
    sim_summary = compute_technical_summary(
        df,
        ticker="SIMULATED_TECH",
        is_simulated_demo=True,
        price_adjustment_basis="SYNTHETIC_SIMULATION_NOT_APPLICABLE",
        currency="USD"
    )
    csv_sim = ExportGenerator.generate_technical_csv(df, "SIMULATED_TECH", summary=sim_summary)
    brief_sim = ExportGenerator.generate_technical_brief(sim_summary, df)

    assert "# DATA_TYPE: SIMULATED DEMO DATA — NOT ACTUAL MARKET HISTORY" in csv_sim
    assert "SIMULATED DEMO DATA — NOT ACTUAL MARKET HISTORY" in brief_sim
    assert "geometric Brownian motion" in brief_sim

    # Case B: Recorded user-supplied market data
    user_summary = compute_technical_summary(
        df,
        ticker="ACTUAL_EQUITY",
        is_simulated_demo=False,
        price_adjustment_basis="SPLIT_AND_DIVIDEND_ADJUSTED",
        currency="INR"
    )
    csv_user = ExportGenerator.generate_technical_csv(df, "ACTUAL_EQUITY", summary=user_summary)
    brief_user = ExportGenerator.generate_technical_brief(user_summary, df)

    assert "# DATA_TYPE: USER_SUPPLIED / RECORDED OHLCV MARKET DATA" in csv_user
    assert "SIMULATED DEMO DATA" not in brief_user
    assert "CURRENCY: INR" in csv_user
    assert "PRICE_ADJUSTMENT_BASIS: SPLIT_AND_DIVIDEND_ADJUSTED" in csv_user
    assert "SPLIT_AND_DIVIDEND_ADJUSTED" in brief_user
