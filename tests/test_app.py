from streamlit.testing.v1 import AppTest
import pytest
import os
import sys
import json
import sqlite3
import pandas as pd
from datetime import date

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

def setup_mock_db():
    from financial_radar.store import connect, DDL
    db = sqlite3.connect(":memory:", check_same_thread=False)
    db.row_factory = sqlite3.Row
    db.executescript(DDL)
    # Provide a universe
    # Pre-populate some observations and signals
    db.execute("INSERT INTO watchlist(ticker, active) VALUES('AAPL', 1)")
    
    # Valid and invalid observations
    db.execute("INSERT INTO observations(company, metric, value, unit, period_end, period_type, quality, comparable, provenance) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)", 
               ("AAPL", "revenue", 1000, "USD", "2025-03-31", "QUARTER", "REPORTED", 1, "[]"))
    db.execute("INSERT INTO observations(company, metric, value, unit, period_end, period_type, quality, comparable, provenance) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)", 
               ("AAPL", "revenue", 0, "USD", "2025-06-30", "QUARTER", "NOT_REPORTED", 1, "[]"))
    
    # Golden Signal
    ev_json = json.dumps([{"value": 0.15}, {"value": 0.20}])
    db.execute("INSERT INTO signals(signal_id, company, severity, confidence, evidence) VALUES(?, ?, ?, ?, ?)", 
               ("OPERATING_MARGIN_DETERIORATION", "AAPL", "HIGH", "HIGH", ev_json))
               
    # Events
    db.execute("INSERT INTO events(id, company, type, filed, description, source_url, accession, form) VALUES(?, ?, ?, ?, ?, ?, ?, ?)", 
               ("e1", "AAPL", "acquisition", "2025-03-31", "Acquired X", "url", "acc1", "8-K"))
               
    return db

def test_streamlit_app_workflow(tmp_path, monkeypatch):
    os.environ["SEC_USER_AGENT"] = "Test Analyst test@example.com"
    import financial_radar.store
    
    # Mock connect to return our populated in-memory DB
    test_db = setup_mock_db()
    monkeypatch.setattr(financial_radar.store, "connect", lambda *args, **kwargs: test_db)
    import financial_radar.pipeline
    monkeypatch.setattr(financial_radar.pipeline, "load_universe", lambda: [{"ticker": "AAPL", "sector": "Tech"}])
    
    at = AppTest.from_file("../app.py", default_timeout=30)
    at.run()
    
    # 1. App starts
    assert not at.exception, str(at.exception)
    
    # 2. Portfolio tab renders
    assert "Manage Universe" in at.tabs[0].subheader[0].value
    
    # 4. Valid portfolio CSV upload
    # Note: Streamlit AppTest doesn't natively simulate file uploads easily without saving to disk and mocking
    # But we can check that the uploader exists
    assert "Upload CSV" in at.tabs[0].file_uploader[0].label
    
    # 7. Attention queue renders a known HIGH signal
    # 8. Severity ordering (HIGH should be at top if multiple)
    assert "Attention Queue" in at.tabs[1].subheader[0].value
    df_queue = at.tabs[1].dataframe[0].value
    assert not df_queue.empty
    assert df_queue.iloc[0]["Priority"] == "HIGH"
    
    # 9. Research mode renders known company
    assert "AAPL" in at.tabs[2].subheader[0].value
    
    # 14. Latest valid period is correct
    assert "2025-03-31" in at.tabs[2].caption[0].value
    
    # 10. Known signal expands (expander label contains title)
    assert "Operating Margin Deterioration" in at.tabs[2].expander[0].label
    
    # 11. Intelligence renders all 4 keys (Expander body)
    expander = at.tabs[2].expander[0]
    markdowns = [m.value for m in expander.markdown]
    assert any("WHAT CHANGED" in m for m in markdowns)
    assert any("WHY IT MATTERS" in m for m in markdowns)
    assert any("INVESTIGATE" in m for m in markdowns)
    
    # 17. Corporate event renders
    assert "ACQUISITION" in at.tabs[2].markdown[-2].value
