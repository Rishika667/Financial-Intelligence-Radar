"""
Unit tests for Pure-Python Technical Analysis MVP Engine (Workstream D).
Tests: Dataframe validation, indicators (SMA, EMA, RSI, MACD, BB, ATR),
technical summary calculations, benchmark relative performance, and template generation.
"""

import io
import pytest
import pandas as pd
import numpy as np
from pathlib import Path

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
from fundamentals_lens.models import TechnicalSummary


@pytest.fixture
def sample_ohlcv_df():
    # 30 days of synthetic trading data
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


def test_validate_ohlcv_dataframe_valid(sample_ohlcv_df):
    is_valid, err, clean_df = validate_ohlcv_dataframe(sample_ohlcv_df)
    assert is_valid is True
    assert err is None
    assert len(clean_df) == 30
    assert list(clean_df.columns[:6]) == ["Date", "Open", "High", "Low", "Close", "Volume"]


def test_validate_ohlcv_dataframe_case_insensitive():
    # Headers in lowercase or mixed case with 24 distinct dates
    dates = pd.date_range("2026-01-01", periods=24, freq="D").strftime("%Y-%m-%d")
    df = pd.DataFrame({
        "date": dates,
        "OPEN": [100.0] * 24,
        "high": [105.0] * 24,
        "Low": [98.0] * 24,
        "CLOSE": [102.0] * 24,
        "volume": [500000] * 24
    })
    is_valid, err, clean_df = validate_ohlcv_dataframe(df)
    assert is_valid is True
    assert err is None
    assert "Close" in clean_df.columns


def test_validate_ohlcv_dataframe_missing_columns():
    df = pd.DataFrame({
        "Date": ["2026-01-01"],
        "Close": [100.0]
    })
    is_valid, err, clean_df = validate_ohlcv_dataframe(df)
    assert is_valid is False
    assert "Missing required columns" in err
    assert clean_df is None


def test_validate_ohlcv_dataframe_insufficient_bars():
    df = pd.DataFrame({
        "Date": pd.date_range("2026-01-01", periods=10, freq="D"),
        "Open": [100.0] * 10,
        "High": [105.0] * 10,
        "Low": [95.0] * 10,
        "Close": [102.0] * 10,
        "Volume": [1000] * 10
    })
    is_valid, err, clean_df = validate_ohlcv_dataframe(df)
    assert is_valid is False
    assert "Insufficient trading observations" in err


def test_validate_ohlcv_dataframe_high_low_violation():
    dates = pd.date_range("2026-01-01", periods=25, freq="D")
    df = pd.DataFrame({
        "Date": dates,
        "Open": [100.0] * 25,
        "High": [90.0] * 25,  # High lower than Low!
        "Low": [95.0] * 25,
        "Close": [92.0] * 25,
        "Volume": [1000] * 25
    })
    is_valid, err, clean_df = validate_ohlcv_dataframe(df)
    assert is_valid is False
    assert "Price invariant violation (High < Low)" in err


def test_calculate_sma(sample_ohlcv_df):
    sma20 = calculate_sma(sample_ohlcv_df["Close"], 20)
    assert len(sma20) == 30
    assert sma20.iloc[18] is np.nan or pd.isna(sma20.iloc[18])
    assert pd.notna(sma20.iloc[19])
    # Known 20-period average of linearly increasing series: mean of 100.0 to 109.5 is 104.75
    assert round(sma20.iloc[19], 2) == 104.75


def test_calculate_rsi(sample_ohlcv_df):
    rsi = calculate_rsi(sample_ohlcv_df["Close"], 14)
    # Strictly non-negative, bounded between 0 and 100
    valid_rsi = rsi.dropna()
    assert (valid_rsi >= 0.0).all()
    assert (valid_rsi <= 100.0).all()
    # Since prices are steadily rising each day, RSI will be very high (approaching 100)
    assert valid_rsi.iloc[-1] > 90.0


def test_calculate_macd(sample_ohlcv_df):
    macd, signal, hist = calculate_macd(sample_ohlcv_df["Close"], 12, 26, 9)
    assert len(macd) == 30
    # Invariant: hist = macd - signal
    diff = (macd - signal).round(2)
    assert np.allclose(hist.dropna(), diff.dropna(), atol=0.01)


def test_calculate_bollinger_bands(sample_ohlcv_df):
    upper, mid, lower = calculate_bollinger_bands(sample_ohlcv_df["Close"], 20, 2.0)
    valid_idx = upper.dropna().index
    assert (upper.loc[valid_idx] >= mid.loc[valid_idx]).all()
    assert (mid.loc[valid_idx] >= lower.loc[valid_idx]).all()


def test_calculate_atr(sample_ohlcv_df):
    atr = calculate_atr(sample_ohlcv_df["High"], sample_ohlcv_df["Low"], sample_ohlcv_df["Close"], 14)
    valid_atr = atr.dropna()
    assert (valid_atr > 0).all()


def test_compute_technical_summary(sample_ohlcv_df):
    _, _, clean_df = validate_ohlcv_dataframe(sample_ohlcv_df)
    summary = compute_technical_summary(clean_df, ticker="TEST_TICKER")
    assert isinstance(summary, TechnicalSummary)
    assert summary.ticker == "TEST_TICKER"
    assert summary.total_bars == 30
    assert summary.last_close == sample_ohlcv_df["Close"].iloc[-1]
    assert summary.high_52w >= summary.last_close
    assert summary.low_52w <= summary.last_close
    assert summary.annualized_volatility is not None
    assert summary.max_drawdown is not None
    assert summary.sma_20_status.startswith("ABOVE") or summary.sma_20_status.startswith("BELOW")


def test_benchmark_relative_performance(sample_ohlcv_df):
    _, _, clean_df = validate_ohlcv_dataframe(sample_ohlcv_df)
    # Synthetic benchmark with slower growth
    bench_df = sample_ohlcv_df.copy()
    bench_df["Close"] = 100.0 + (bench_df.index * 0.1)
    _, _, clean_bench = validate_ohlcv_dataframe(bench_df)

    summary = compute_technical_summary(clean_df, ticker="ALPHA", benchmark_df=clean_bench, benchmark_ticker="SPY")
    assert summary.benchmark_ticker == "SPY"
    assert summary.benchmark_change_1y is not None
    assert summary.relative_performance_1y is not None
    # ALPHA grew faster than benchmark (+0.5/day vs +0.1/day), so relative performance should be positive
    assert summary.relative_performance_1y > 0


def test_csv_template():
    tpl = get_ohlcv_csv_template()
    assert "Date,Open,High,Low,Close,Volume" in tpl
    df = pd.read_csv(io.StringIO(tpl))
    assert len(df) == 5
    # Headers match required
    assert set(["Date", "Open", "High", "Low", "Close", "Volume"]).issubset(set(df.columns))
