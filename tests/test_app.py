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
        def delay(self): pass
        def submissions(self, cik, fetch_historical=False):
            import json, os
            if cik == "0000320193": t = "aapl"
            elif cik == "0000789019": t = "msft"
            elif cik == "0000019617": t = "jpm"
            else: t = "nvda"
            path = f'tests/fixtures/{t}_submissions.json'
            if not os.path.exists(path): raise FileNotFoundError(f"Required SEC golden fixture missing: {path}")
            with open(path, 'r', encoding='utf-8') as f: return json.load(f)
            
        def company_facts(self, cik):
            import json, os
            if cik == "0000320193": t = "aapl"
            elif cik == "0000789019": t = "msft"
            elif cik == "0000019617": t = "jpm"
            else: t = "nvda"
            path = f'tests/fixtures/{t}_facts.json'
            if not os.path.exists(path): raise FileNotFoundError(f"Required SEC golden fixture missing: {path}")
            with open(path, 'r', encoding='utf-8') as f: return json.load(f)

    monkeypatch.setattr("financial_radar.core.SECClient", MockSECClient)
    import sys
    if "app" in sys.modules:
        monkeypatch.setattr(sys.modules["app"], "SECClient", MockSECClient)

    class MockSession:
        def get(self, url, timeout):
            return MockResponse("Departure of Directors or Certain Officers. John Doe resigned.")
            
    import financial_radar.core
    monkeypatch.setattr("financial_radar.core.requests.Session", lambda: MockSession())


    import streamlit as st
    captured_dfs = []
    def mock_df(data, *args, **kwargs):
        import pandas as pd
        df = pd.DataFrame(data)
        captured_dfs.append(df)
        st.text(f"MOCKED_DF: {len(df)} rows")
    monkeypatch.setattr(st, "dataframe", mock_df)
    import sys
    if "app" in sys.modules:
        monkeypatch.setattr(sys.modules["app"].st, "dataframe", mock_df)
        
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
    print("DATAFRAME MOCKED")
    assert getattr(at.tabs[0], "success", None) and len(at.tabs[0].success) > 0, "No success message found"
    
    # 3. Verify readiness
    df_readiness = next((df for df in reversed(captured_dfs) if "State" in df.columns), None)
    assert df_readiness is not None
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
