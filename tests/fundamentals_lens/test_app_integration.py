from pathlib import Path
import pytest
import pandas as pd
from streamlit.testing.v1 import AppTest

from fundamentals_lens.technical import (
    validate_ohlcv_dataframe_with_report,
    PriceAdjustmentBasis,
    compute_technical_indicators,
    compute_technical_summary,
    create_price_candlestick_chart,
    create_benchmark_comparison_chart
)

APP_PATH = Path(__file__).resolve().parent.parent.parent / "fundamentals_lens_app.py"


def test_streamlit_app_overview_page():
    at = AppTest.from_file(str(APP_PATH), default_timeout=30)
    at.run()
    assert len(at.exception) == 0, [e.value for e in at.exception]
    assert len(at.sidebar.radio) > 0
    assert at.sidebar.radio[0].value == "Overview"


def test_streamlit_app_company_analysis_page():
    at = AppTest.from_file(str(APP_PATH), default_timeout=30)
    at.run()
    assert len(at.exception) == 0
    # Switch to Company Analysis
    at.sidebar.radio[0].set_value("Company Analysis")
    at.run()
    assert len(at.exception) == 0, [e.value for e in at.exception]
    
    # Initial company check
    assert len(at.selectbox) > 0
    init_company = at.selectbox[0].value

    # Switch company to TCS and assert behavioral state mutation
    at.selectbox[0].set_value("TCS")
    at.run()
    assert len(at.exception) == 0, [e.value for e in at.exception]
    assert at.selectbox[0].value == "TCS"
    assert at.selectbox[0].value != init_company

    # Assert rendered markdown/header dynamically reflects the newly selected company
    rendered_text = " ".join(m.value for m in at.markdown) + " " + " ".join(h.value for h in at.header)
    assert "TCS" in rendered_text or "Tata Consultancy Services" in rendered_text


def test_streamlit_app_peer_comparison_page():
    at = AppTest.from_file(str(APP_PATH), default_timeout=30)
    at.run()
    assert len(at.exception) == 0
    # Switch to Peer Comparison
    at.sidebar.radio[0].set_value("Peer Comparison")
    at.run()
    assert len(at.exception) == 0, [e.value for e in at.exception]

    # Test automotive group with caveats
    assert len(at.selectbox) >= 2
    at.selectbox[0].set_value("group_d_india_auto")
    at.run()
    assert len(at.exception) == 0, [e.value for e in at.exception]


def test_streamlit_app_peer_comparison_indexed_view():
    at = AppTest.from_file(str(APP_PATH), default_timeout=30)
    at.run()
    assert len(at.exception) == 0
    at.sidebar.radio[0].set_value("Peer Comparison")
    at.run()
    assert len(at.exception) == 0
    assert len(at.checkbox) > 0
    at.checkbox[0].check()
    at.run()
    assert len(at.exception) == 0, [e.value for e in at.exception]


def test_streamlit_app_data_integrity_page():
    at = AppTest.from_file(str(APP_PATH), default_timeout=30)
    at.run()
    assert len(at.exception) == 0
    # Switch to Data Integrity
    at.sidebar.radio[0].set_value("Data Integrity & Methodology")
    at.run()
    assert len(at.exception) == 0, [e.value for e in at.exception]


def test_streamlit_app_technical_analysis_page_and_demo_switching():
    at = AppTest.from_file(str(APP_PATH), default_timeout=30)
    at.run()
    assert len(at.exception) == 0
    # Switch to Price & Technical Analysis
    at.sidebar.radio[0].set_value("Price & Technical Analysis")
    at.run()
    assert len(at.exception) == 0, [e.value for e in at.exception]
    assert len(at.radio) > 0

    # Test switching demo asset if selectbox is available
    demo_sb = None
    for sb in at.selectbox:
        if "Demo Asset" in getattr(sb, "label", ""):
            demo_sb = sb
            break

    if demo_sb is not None and len(demo_sb.options) > 1:
        initial_val = demo_sb.value
        target_val = demo_sb.options[1]
        demo_sb.set_value(target_val)
        at.run()
        assert len(at.exception) == 0, [e.value for e in at.exception]
        assert demo_sb.value == target_val
        assert demo_sb.value != initial_val


def test_streamlit_app_technical_analysis_indicator_toggles_and_benchmark():
    at = AppTest.from_file(str(APP_PATH), default_timeout=30)
    at.run()
    assert len(at.exception) == 0
    at.sidebar.radio[0].set_value("Price & Technical Analysis")
    at.run()
    assert len(at.exception) == 0, [e.value for e in at.exception]

    # Select comparative benchmark if available
    if len(at.selectbox) >= 2:
        bm_opts = at.selectbox[1].options
        for opt in bm_opts:
            if "SIMULATED_MARKET_BENCHMARK" in opt:
                at.selectbox[1].set_value(opt)
                at.run()
                assert len(at.exception) == 0, [e.value for e in at.exception]
                assert at.selectbox[1].value == opt
                break

    # Toggle checkboxes if present and assert behavioral state mutation
    if len(at.checkbox) > 0:
        orig_state = at.checkbox[0].value
        if orig_state is True:
            at.checkbox[0].uncheck()
        else:
            at.checkbox[0].check()
        at.run()
        assert len(at.exception) == 0, [e.value for e in at.exception]
        assert at.checkbox[0].value != orig_state


def test_technical_analysis_invalid_csv_diagnostics():
    """Verify that validate_ohlcv_dataframe_with_report flags violations and produces diagnostics."""
    # Test 1: Non-positive price
    bad_df_1 = pd.DataFrame({
        "Date": ["2026-01-01", "2026-01-02", "2026-01-03"],
        "Open": [100.0, 0.0, 105.0],
        "High": [105.0, 102.0, 110.0],
        "Low": [98.0, 95.0, 100.0],
        "Close": [102.0, 100.0, 108.0],
        "Volume": [1000, 1000, 1000]
    })
    valid, err, clean, rep = validate_ohlcv_dataframe_with_report(
        bad_df_1, ticker="TEST_BAD1", price_adjustment_basis=PriceAdjustmentBasis.RAW_UNADJUSTED
    )
    assert not valid
    assert "strictly positive" in err
    assert rep.is_valid is False
    assert rep.error_count > 0

    # Test 2: Range invariant violation (High < Open or Low > High)
    bad_df_2 = pd.DataFrame({
        "Date": ["2026-01-01", "2026-01-02", "2026-01-03"],
        "Open": [100.0, 115.0, 105.0],
        "High": [105.0, 110.0, 110.0],  # High 110 < Open 115
        "Low": [98.0, 95.0, 100.0],
        "Close": [102.0, 105.0, 108.0],
        "Volume": [1000, 1000, 1000]
    })
    valid2, err2, clean2, rep2 = validate_ohlcv_dataframe_with_report(
        bad_df_2, ticker="TEST_BAD2", price_adjustment_basis=PriceAdjustmentBasis.RAW_UNADJUSTED
    )
    assert not valid2
    assert "invariant violation" in err2 or "High must be >=" in err2
    assert rep2.is_valid is False


def test_streamlit_app_technical_analysis_radio_toggle_to_upload():
    """Verify that toggling data source radio to 'Upload Custom OHLCV CSV' mounts file uploader."""
    at = AppTest.from_file(str(APP_PATH), default_timeout=30)
    at.run()
    assert len(at.exception) == 0

    at.sidebar.radio[0].set_value("Price & Technical Analysis")
    at.run()
    assert len(at.exception) == 0

    # Locate data source radio
    src_radio = None
    for r in at.radio:
        for opt in r.options:
            if "Upload Custom" in opt:
                src_radio = r
                break
        if src_radio:
            break

    if src_radio:
        src_radio.set_value(src_radio.options[1])
        at.run()
        assert len(at.exception) == 0, [e.value for e in at.exception]
        assert len(at.file_uploader) > 0


def test_technical_analysis_valid_csv_metrics_and_traces():
    """Verify that valid OHLCV data creates indicators, summary, and proper chart traces."""
    dates = pd.date_range("2025-01-01", periods=100, freq="B").strftime("%Y-%m-%d")
    valid_df = pd.DataFrame({
        "Date": dates,
        "Open": [100.0 + i * 0.5 for i in range(100)],
        "High": [102.0 + i * 0.5 for i in range(100)],
        "Low": [99.0 + i * 0.5 for i in range(100)],
        "Close": [101.0 + i * 0.5 for i in range(100)],
        "Volume": [1000000 + i * 1000 for i in range(100)]
    })

    valid, err, clean_df, rep = validate_ohlcv_dataframe_with_report(
        valid_df, ticker="TEST_VALID", price_adjustment_basis=PriceAdjustmentBasis.SPLIT_ADJUSTED_ONLY
    )
    assert valid is True
    assert rep.is_valid is True

    # Compute indicators
    ind_df = compute_technical_indicators(clean_df)
    assert "SMA_20" in ind_df.columns
    assert "SMA_50" in ind_df.columns
    assert "RSI_14" in ind_df.columns
    assert "MACD" in ind_df.columns
    assert "BB_Upper" in ind_df.columns
    assert "BB_Lower" in ind_df.columns
    assert "ATR_14" in ind_df.columns

    # Compute summary
    summary = compute_technical_summary(ind_df, ticker="TEST_VALID")
    assert summary.total_bars == 100
    assert summary.last_close > 0

    # Create candlestick chart with SMA and Bollinger Bands
    fig = create_price_candlestick_chart(
        ind_df,
        ticker="TEST_VALID",
        show_sma=True,
        show_bb=True
    )
    trace_types = [t.type for t in fig.data]
    assert "candlestick" in trace_types
    assert "bar" in trace_types  # Volume trace
    assert "scatter" in trace_types  # SMAs and Bollinger traces
    assert len(fig.data) >= 4  # Candlestick, Volume, SMA20, SMA50, BB_Upper, BB_Lower

    # Create benchmark comparison chart
    bm_fig = create_benchmark_comparison_chart(ind_df, ind_df, asset_ticker="TEST_VALID", benchmark_ticker="BENCHMARK")
    assert len(bm_fig.data) == 2
    # Base alignment to 100.0
    assert abs(bm_fig.data[0].y[0] - 100.0) < 0.001
    assert abs(bm_fig.data[1].y[0] - 100.0) < 0.001
