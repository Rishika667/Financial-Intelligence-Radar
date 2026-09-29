import pytest
import os
from streamlit.testing.v1 import AppTest
from test_app import setup_mock_db

def test_idempotent_refreshes(tmp_path, monkeypatch):
    import financial_radar.store
    import financial_radar.pipeline
    test_db = setup_mock_db()
    monkeypatch.setattr(financial_radar.store, "connect", lambda *args, **kwargs: test_db)
    
    class MockSECClient:
        def __init__(self, ua): pass
        def submissions(self, cik, fetch_historical=False):
            return {"filings": {"recent": {"accessionNumber": ["0001"], "form": ["10-K"], "reportDate": ["2023-09-30"], "primaryDocument": ["10k.htm"]}}}
        def company_facts(self, cik):
            return {
                "facts": {
                    "us-gaap": {
                        "Revenues": {"units": {"USD": [{"end": "2023-09-30", "val": 100.0, "accn": "0001", "filed": "2023-11-03", "form": "10-K", "start": "2022-09-25"}]}},
                    }
                }
            }
            
    monkeypatch.setattr("financial_radar.core.SECClient", MockSECClient)
    
    os.environ["SEC_USER_AGENT"] = "Test Analyst"
    
    at = AppTest.from_file("../app.py", default_timeout=30)
    at.run()
    
    # 1. Select and Save
    at.tabs[0].multiselect[0].set_value(["AAPL"]).run()
    at.tabs[0].button[0].click().run()
    
    # 2. Refresh 1
    at.tabs[0].button[2].click().run()
    obs_count_1 = test_db.execute("SELECT count(*) FROM observations").fetchone()[0]
    
    # 3. Refresh 2
    at.tabs[0].button[2].click().run()
    obs_count_2 = test_db.execute("SELECT count(*) FROM observations").fetchone()[0]
    
    # 4. Refresh 3
    at.tabs[0].button[2].click().run()
    obs_count_3 = test_db.execute("SELECT count(*) FROM observations").fetchone()[0]
    
    assert obs_count_1 > 0
    assert obs_count_1 == obs_count_2 == obs_count_3, "Observations were duplicated across refreshes!"
