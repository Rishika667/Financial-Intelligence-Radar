from pathlib import Path
import pytest
from streamlit.testing.v1 import AppTest

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
    
    # Switch company
    assert len(at.selectbox) > 0
    at.selectbox[0].set_value("TCS")
    at.run()
    assert len(at.exception) == 0, [e.value for e in at.exception]


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


def test_streamlit_app_technical_analysis_page():
    at = AppTest.from_file(str(APP_PATH), default_timeout=30)
    at.run()
    assert len(at.exception) == 0
    # Switch to Price & Technical Analysis
    at.sidebar.radio[0].set_value("Price & Technical Analysis")
    at.run()
    assert len(at.exception) == 0, [e.value for e in at.exception]
    # Check that radio or selectbox exists
    assert len(at.radio) > 0
