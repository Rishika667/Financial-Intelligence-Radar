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
            t = "aapl" if cik == "0000320193" else "msft" if cik == "0000789019" else "nvda"
            try:
                with open(f'tests/fixtures/{t}_submissions.json', 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                # Fallback to structural mock if file missing
                return {"filings": {"recent": {"accessionNumber": ["0001", "0002"], "form": ["10-K", "8-K"], "reportDate": ["2023-09-30", "2023-10-01"], "primaryDocument": ["10k.htm", "8k.htm"], "filingDate": ["2023-11-03", "2023-10-05"]}}}
                
        def company_facts(self, cik):
            t = "aapl" if cik == "0000320193" else "msft" if cik == "0000789019" else "nvda"
            try:
                with open(f'tests/fixtures/{t}_facts.json', 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return {"facts": {"us-gaap": {"Revenues": {"units": {"USD": [{"end": "2023-09-30", "val": 383000000.0, "accn": "0001", "filed": "2023-11-03", "form": "10-K", "start": "2022-09-25"}, {"end": "2022-09-24", "val": 394000000.0, "accn": "0001", "filed": "2023-11-03", "form": "10-K", "start": "2021-09-26"}]}}}}}
                
    monkeypatch.setattr("financial_radar.core.SECClient", MockSECClient)
    
    class MockResponse:
        def __init__(self, text): self.text = text
        def raise_for_status(self): pass
        
    class MockSession:
        def get(self, url, timeout): return MockResponse("Departure of Directors or Certain Officers. John Doe resigned.")
            
    monkeypatch.setattr("financial_radar.core.requests.Session", lambda: MockSession())
    
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
