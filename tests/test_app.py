import pytest
from streamlit.testing.v1 import AppTest
import sqlite3
import pandas as pd
import os
import json
from datetime import date

def setup_mock_db():
    db = sqlite3.connect(":memory:", check_same_thread=False)
    db.row_factory = sqlite3.Row
    from financial_radar.store import DDL
    db.executescript(DDL)
    return db

def test_refresh_workflow(tmp_path, monkeypatch):
    """
    Deterministic mocked SEC integration test:
    fresh database -> zero active companies -> select AAPL -> save monitored ->
    SEC preflight -> refresh AAPL -> normalization -> observations -> signals -> readiness -> Research Mode
    """
    os.environ["SEC_USER_AGENT"] = "Test Analyst test@example.com"
    import financial_radar.store
    import financial_radar.pipeline
    test_db = setup_mock_db()
    monkeypatch.setattr(financial_radar.store, "connect", lambda *args, **kwargs: test_db)
    
    # Mock SEC client fetching
    class MockSECClient:
        def __init__(self, ua): pass
        def submissions(self, cik, fetch_historical=False):
            return {"filings": {"recent": {"accessionNumber": ["0001"], "form": ["10-K"], "reportDate": ["2023-09-30"], "primaryDocument": ["10k.htm"]}}}
        def company_facts(self, cik):
            return {
                "facts": {
                    "us-gaap": {
                        "Revenues": {"units": {"USD": [{"end": "2023-09-30", "val": 383285000000.0, "accn": "0001", "filed": "2023-11-03", "form": "10-K", "start": "2022-09-25"}]}},
                        "NetIncomeLoss": {"units": {"USD": [{"end": "2023-09-30", "val": 96995000000.0, "accn": "0001", "filed": "2023-11-03", "form": "10-K", "start": "2022-09-25"}]}},
                        "OperatingIncomeLoss": {"units": {"USD": [{"end": "2023-09-30", "val": 114301000000.0, "accn": "0001", "filed": "2023-11-03", "form": "10-K", "start": "2022-09-25"}]}},
                        "NetCashProvidedByUsedInOperatingActivities": {"units": {"USD": [{"end": "2023-09-30", "val": 110543000000.0, "accn": "0001", "filed": "2023-11-03", "form": "10-K", "start": "2022-09-25"}]}},
                        "CashAndCashEquivalentsAtCarryingValue": {"units": {"USD": [{"end": "2023-09-30", "val": 29965000000.0, "accn": "0001", "filed": "2023-11-03", "form": "10-K"}]}},
                    }
                }
            }
            
    monkeypatch.setattr("financial_radar.core.SECClient", MockSECClient)
    # Actually monkeypatch it where app.py imports it
    # import app removed
    # removed

    at = AppTest.from_file("../app.py", default_timeout=30)
    at.run()
    
    assert not at.exception
    
    # 1. Zero active companies initially
    assert "No active companies" in at.tabs[2].info[0].value
    
    # 2. Setup screen appears, select AAPL
    at.tabs[0].multiselect[0].set_value(["AAPL"]).run()
    assert not at.exception
    
    # 3. Save selection
    at.tabs[0].button[0].click().run()
    assert not at.exception
    
    # 4. Refresh AAPL
    at.tabs[0].button[2].click().run()
    assert not at.exception
    
    # 5. Verify readiness
    df_readiness = at.tabs[0].dataframe[1].value
    assert "READY" in str(df_readiness.iloc[0]["State"])
    
    # 6. Verify Research mode
    # Select AAPL
    at.tabs[3].selectbox[0].set_value("AAPL").run()
    assert not at.exception
    
    # 7. Check values
    assert "AAPL" in at.tabs[3].header[0].value
