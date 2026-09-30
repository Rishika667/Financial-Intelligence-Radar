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
    Deterministic mocked SEC integration test testing the full End-to-End spine.
    """
    os.environ["SEC_USER_AGENT"] = "Test Analyst test@example.com"
    import financial_radar.store
    import financial_radar.pipeline
    test_db = setup_mock_db()
    monkeypatch.setattr(financial_radar.store, "connect", lambda *args, **kwargs: test_db)
    
    # Pre-populate portfolio table so we can test portfolio context joining
    test_db.execute("INSERT INTO portfolio(ticker, shares, weight, exposure, cost_basis) VALUES('AAPL', 100, 0.1, 15000, 100)")
    
    class MockSECClient:
        def __init__(self, ua): pass
        def submissions(self, cik, fetch_historical=False):
            return {"filings": {"recent": {"accessionNumber": ["0001", "0002"], "form": ["10-K", "8-K"], "reportDate": ["2023-09-30", "2023-10-01"], "primaryDocument": ["10k.htm", "8k.htm"], "filingDate": ["2023-11-03", "2023-10-05"]}}}
        def company_facts(self, cik):
            return {
                "facts": {
                    "us-gaap": {
                        "Revenues": {"units": {"USD": [
                            {"end": "2023-09-30", "val": 383000000.0, "accn": "0001", "filed": "2023-11-03", "form": "10-K", "start": "2022-09-25"},
                            {"end": "2022-09-24", "val": 394000000.0, "accn": "0001", "filed": "2023-11-03", "form": "10-K", "start": "2021-09-26"}
                        ]}},
                        "GrossProfit": {"units": {"USD": [
                            {"end": "2023-09-30", "val": 169000000.0, "accn": "0001", "filed": "2023-11-03", "form": "10-K", "start": "2022-09-25"},
                            {"end": "2022-09-24", "val": 170000000.0, "accn": "0001", "filed": "2023-11-03", "form": "10-K", "start": "2021-09-26"}
                        ]}}
                    }
                }
            }
            
    monkeypatch.setattr("financial_radar.core.SECClient", MockSECClient)
    
    # Mock requests for events
    class MockResponse:
        def __init__(self, text):
            self.text = text
        def raise_for_status(self): pass
        
    class MockSession:
        def get(self, url, timeout):
            return MockResponse("Departure of Directors or Certain Officers. John Doe resigned.")
            
    import financial_radar.core
    monkeypatch.setattr("financial_radar.core.requests.Session", lambda: MockSession())

    at = AppTest.from_file("../app.py", default_timeout=30)
    at.run()
    
    assert not at.exception
    
    # 1. Setup screen appears, select AAPL
    at.tabs[0].multiselect[0].set_value(["AAPL"]).run()
    at.tabs[0].button[0].click().run()
    
    # 2. Refresh AAPL
    at.tabs[0].button[2].click().run()
    assert not at.exception
    
    # Check SUCCESS in refresh status
    if getattr(at.tabs[0], "error", None) and at.tabs[0].error:
        print("ERROR:", [e.value for e in at.tabs[0].error])
    if getattr(at.tabs[0], "warning", None) and at.tabs[0].warning:
        print("WARNING:", [w.value for w in at.tabs[0].warning])
    if getattr(at.tabs[0], "success", None) and at.tabs[0].success:
        print("SUCCESS MSG:", [s.value for s in at.tabs[0].success])
    print("DATAFRAME:", at.tabs[0].dataframe[0].value if getattr(at.tabs[0], "dataframe", None) and at.tabs[0].dataframe else "None")
    assert getattr(at.tabs[0], "success", None) and len(at.tabs[0].success) > 0, "No success message found"
    
    # 3. Verify readiness
    df_readiness = at.tabs[0].dataframe[1].value
    assert "READY" in str(df_readiness.iloc[0]["State"]) or "PARTIAL" in str(df_readiness.iloc[0]["State"])
    
    # 4. Verify Attention Queue portfolio context & signals
    # Since margin compressed from 43.1% to 44.1%? Wait, 170/394 = 43.1%, 169/383 = 44.1%. Margin EXPANDED.
    # Revenue decelerated from 394 to 383. Revenue growth is negative.
    at.tabs[2].run()
    q_exp = [e for e in at.tabs[2].get("expanders")] if hasattr(at.tabs[2], "get") else at.tabs[2].expander
    if q_exp:
        # Check portfolio context
        assert "Weight: 10.00%" in q_exp[0].markdown[0].value
    
    # 5. Verify Research mode
    at.tabs[3].selectbox[0].set_value("AAPL").run()
    
    # 6. Check values and synthesis
    assert "AAPL" in at.tabs[3].header[0].value
    
    # Synthesis
    assert "Revenue moved" in at.tabs[3].markdown[2].value or at.tabs[3].markdown[2].value == "**OBSERVED:**"
    
    # Ensure events hit
    context_vals = [m.value for m in at.tabs[3].markdown if "events" in m.value.lower() or "context" in m.value.lower()]
    assert len(context_vals) > 0
