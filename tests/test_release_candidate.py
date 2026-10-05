import pytest
from streamlit.testing.v1 import AppTest
import os
import json

def test_release_candidate_end_to_end(tmp_path, monkeypatch):
    os.environ["SEC_USER_AGENT"] = "Test Analyst test@example.com"
    import financial_radar.store
    import financial_radar.pipeline
    db_path = str(tmp_path / "test.sqlite")
    test_db = financial_radar.store.connect(db_path)
    monkeypatch.setattr(financial_radar.store, "connect", lambda *args, **kwargs: test_db)
    
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

    
    class MockResponse:
        def __init__(self, text): self.text = text
        def raise_for_status(self): pass
        
    class MockSession:
        def __init__(self): self.headers = {}
        def get(self, url, timeout): return MockResponse("Departure of Directors or Certain Officers. John Doe resigned.")
            
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
    at.tabs[0].multiselect[0].set_value(["AAPL", "MSFT"]).run()
    at.tabs[0].button[0].click().run()
    
    # 2. Refresh
    at.tabs[0].button[2].click().run()
    assert not at.exception
    
    # 3. Check Research mode values and synthesis
    at.tabs[3].selectbox[0].set_value("AAPL").run()
    assert "AAPL" in at.tabs[3].header[0].value
    
    # Check that synthesis executed successfully
    assert any("OBSERVED" in str(m.value) for m in at.tabs[3].markdown)
    
    # Check Attention queue portfolio
    at.tabs[2].run()
    exp = [e for e in at.tabs[2].expander]
    if exp:
        texts = [str(m.value) for m in exp[0].markdown]
        assert any("Portfolio Context:" in t for t in texts), f"Could not find Portfolio Context in: {texts}"
