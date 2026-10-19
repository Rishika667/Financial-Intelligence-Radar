"""
Phase 20 Technical Analysis Edge Cases & Parameter Guard Tests.
Verifies:
1. P1-4: validate_ohlcv_dataframe_with_report handles non-contiguous, string, and DatetimeIndex gracefully.
2. Parameter type guards on calculate_sma, calculate_ema, calculate_rsi, calculate_macd,
   calculate_bollinger_bands, and calculate_atr.
"""
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
    calculate_atr
)


def _make_sample_df(n=30, index=None):
    dates = pd.date_range("2024-01-01", periods=n, freq="D").strftime("%Y-%m-%d").tolist()
    data = {
        "Date": dates,
        "Open": [100.0 + i for i in range(n)],
        "High": [105.0 + i for i in range(n)],
        "Low": [95.0 + i for i in range(n)],
        "Close": [102.0 + i for i in range(n)],
        "Volume": [10000 + i * 100 for i in range(n)]
    }
    df = pd.DataFrame(data)
    if index is not None:
        df.index = index
    return df


def test_validate_ohlcv_non_contiguous_integer_index_with_errors():
    """Verify that offending row diagnostic extraction succeeds with non-contiguous integer index."""
    df = _make_sample_df(30, index=[i * 10 for i in range(30)])  # index: 0, 10, 20, 30... 290
    # Inject error at label 50 (positional row 5)
    df.loc[50, "High"] = 80.0  # Range violation: High < Open (105 < 80)

    is_valid, err, clean, report = validate_ohlcv_dataframe_with_report(df, ticker="TEST")
    assert is_valid is False
    assert report.error_count > 0
    assert len(report.sample_offending_rows) > 0
    sample = report.sample_offending_rows[0]
    assert sample["row_index"] == 50
    assert sample["position"] == 5
    assert "Range invariant violation" in sample["error"]


def test_validate_ohlcv_string_index_with_errors():
    """Verify that offending row diagnostic extraction succeeds with string index labels."""
    str_index = [f"row_{i}" for i in range(30)]
    df = _make_sample_df(30, index=str_index)
    # Inject bad date at row_3
    df.loc["row_3", "Date"] = "not-a-date"

    is_valid, err, clean, report = validate_ohlcv_dataframe_with_report(df, ticker="TEST")
    assert is_valid is False
    assert report.error_count > 0
    assert len(report.sample_offending_rows) > 0
    sample = report.sample_offending_rows[0]
    assert sample["position"] == 3
    assert "not-a-date" in sample["raw_data"]


def test_validate_ohlcv_datetime_index_with_errors():
    """Verify that offending row diagnostic extraction succeeds with DatetimeIndex."""
    dt_index = pd.date_range("2024-01-01", periods=30, freq="D")
    df = _make_sample_df(30, index=dt_index)
    # Inject non-positive price at position 10
    df.iloc[10, df.columns.get_loc("Close")] = -5.0

    is_valid, err, clean, report = validate_ohlcv_dataframe_with_report(df, ticker="TEST")
    assert is_valid is False
    assert report.error_count > 0
    assert any("Non-positive price" in s["error"] for s in report.sample_offending_rows)


def test_sma_parameter_type_guards():
    s = pd.Series([10.0, 20.0, 30.0, 40.0])
    with pytest.raises(ValueError, match="period must be a positive integer"):
        calculate_sma(s, 14.5)  # float
    with pytest.raises(ValueError, match="period must be a positive integer"):
        calculate_sma(s, "14")  # str
    with pytest.raises(ValueError, match="period must be a positive integer"):
        calculate_sma(s, True)  # bool
    with pytest.raises(ValueError, match="period must be a positive integer"):
        calculate_sma(s, 0)  # 0


def test_ema_parameter_type_guards():
    s = pd.Series([10.0, 20.0, 30.0, 40.0])
    with pytest.raises(ValueError, match="period must be a positive integer"):
        calculate_ema(s, 14.5)
    with pytest.raises(ValueError, match="period must be a positive integer"):
        calculate_ema(s, "14")
    with pytest.raises(ValueError, match="period must be a positive integer"):
        calculate_ema(s, 0)


def test_rsi_parameter_type_guards():
    s = pd.Series([10.0] * 30)
    with pytest.raises(ValueError, match="period must be a positive integer"):
        calculate_rsi(s, 14.5)
    with pytest.raises(ValueError, match="period must be a positive integer"):
        calculate_rsi(s, "14")
    with pytest.raises(ValueError, match="period must be a positive integer"):
        calculate_rsi(s, 0)


def test_macd_parameter_type_guards():
    s = pd.Series([10.0] * 40)
    with pytest.raises(ValueError, match="MACD periods must be positive integers"):
        calculate_macd(s, fast=12.5, slow=26, signal=9)
    with pytest.raises(ValueError, match="MACD periods must be positive integers"):
        calculate_macd(s, fast=12, slow="26", signal=9)
    with pytest.raises(ValueError, match="MACD periods must be positive integers"):
        calculate_macd(s, fast=12, slow=26, signal=True)
    with pytest.raises(ValueError, match="strictly less than slow period"):
        calculate_macd(s, fast=26, slow=26, signal=9)


def test_bollinger_bands_parameter_type_guards():
    s = pd.Series([10.0] * 30)
    with pytest.raises(ValueError, match="period must be a positive integer"):
        calculate_bollinger_bands(s, period=20.5)
    with pytest.raises(ValueError, match="num_std must be non-negative"):
        calculate_bollinger_bands(s, period=20, num_std=-1.0)
    with pytest.raises(ValueError, match="ddof must be 0"):
        calculate_bollinger_bands(s, period=20, ddof=2)
    with pytest.raises(ValueError, match="ddof must be 0"):
        calculate_bollinger_bands(s, period=20, ddof=True)


def test_atr_parameter_type_guards():
    h = pd.Series([105.0] * 30)
    l = pd.Series([95.0] * 30)
    c = pd.Series([100.0] * 30)
    with pytest.raises(ValueError, match="period must be a positive integer"):
        calculate_atr(h, l, c, 14.5)
    with pytest.raises(ValueError, match="period must be a positive integer"):
        calculate_atr(h, l, c, "14")
    with pytest.raises(ValueError, match="period must be a positive integer"):
        calculate_atr(h, l, c, 0)
