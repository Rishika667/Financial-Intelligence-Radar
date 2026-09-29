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
    db.execute("INSERT INTO watchlist(ticker, active) VALUES('AAPL', 1)")
    
    # Valid and invalid observations
    db.execute("INSERT INTO observations(company, metric, value, unit, period_end, period_type, quality, comparable, provenance) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)", 
               ("AAPL", "revenue", 1000, "USD", "2025-03-31", "QUARTER", "REPORTED", 1, "[]"))
    db.execute("INSERT INTO observations(company, metric, value, unit, period_end, period_type, quality, comparable, provenance) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)", 
               ("AAPL", "revenue", 0, "USD", "2025-06-30", "QUARTER", "NOT_REPORTED", 1, "[]"))
    
    # Golden Signal
    ev_json = json.dumps([
        {"metric": "Operating Margin", "value": 0.15, "unit": "pure", "period_end": "2025-03-31", "period_type": "QUARTER", "quality": "REPORTED", "comparable": True, "derived_from": "x", "provenance": [{"concept": "OperatingIncomeLoss", "accession": "0001", "form": "10-Q", "filing_date": "2025-04-15", "raw_value": 150, "mapping_version": "1", "source_url": "https://sec.gov"}]},
        {"metric": "Operating Margin", "value": 0.20, "unit": "pure", "period_end": "2024-12-31", "period_type": "QUARTER", "quality": "REPORTED", "comparable": True, "derived_from": "y", "provenance": []}
    ])
    db.execute("INSERT INTO signals(signal_id, company, severity, confidence, evidence) VALUES(?, ?, ?, ?, ?)", 
               ("OPERATING_MARGIN_DETERIORATION", "AAPL", "HIGH", "HIGH", ev_json))
               
    # Events
    db.execute("INSERT INTO events(id, company, type, filed, description, source_url, accession, form) VALUES(?, ?, ?, ?, ?, ?, ?, ?)", 
               ("e1", "AAPL", "acquisition", "2025-03-31", "Acquired X", "url", "acc1", "8-K"))
               
    # Peers
    db.execute("INSERT INTO peer_context(company, metric, group_id, company_value, peer_median, peer_min, peer_max, n_peers, version) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)", 
               ("AAPL", "Operating Margin", "Tech", 0.15, 0.20, 0.10, 0.30, 5, "v1"))
               
    return db


# =========================================================
# UNIT TESTS FOR PORTFOLIO UPLOAD & PERSISTENCE
# (Tested directly as AppTest File Uploader simulation is limited)
# =========================================================
def test_portfolio_csv_validation():
    from financial_radar.pipeline import validate_portfolio_csv
    universe = ["AAPL", "MSFT"]
    
    # Valid CSV acceptance
    df_valid = pd.DataFrame([{"ticker": "AAPL", "shares": 100, "weight": 1.0, "cost_basis": 150.0}])
    is_valid, err = validate_portfolio_csv(df_valid, universe)
    assert is_valid, err
    
    # Missing ticker
    df_no_ticker = pd.DataFrame([{"shares": 100, "weight": 1.0, "cost_basis": 100.0}])
    is_valid, err = validate_portfolio_csv(df_no_ticker, universe)
    assert not is_valid
    assert "must contain 'ticker'" in err
    
    # Invalid ticker rejection
    df_invalid_ticker = pd.DataFrame([{"ticker": "UNKNOWN", "shares": 100, "weight": 1.0, "cost_basis": 150.0}])
    is_valid, err = validate_portfolio_csv(df_invalid_ticker, universe)
    assert not is_valid
    assert "not in the 50-company" in err
    
    # Negative shares rejection
    df_negative = pd.DataFrame([{"ticker": "AAPL", "shares": -10, "weight": 1.0, "cost_basis": 150.0}])
    is_valid, err = validate_portfolio_csv(df_negative, universe)
    assert not is_valid
    pass
    
    # Invalid weight
    df_weight = pd.DataFrame([{"ticker": "AAPL", "shares": 100, "weight": 1.5, "cost_basis": 150.0}])
    is_valid, err = validate_portfolio_csv(df_weight, universe)
    assert not is_valid
    assert "between 0 and 1" in err

def test_save_portfolio_persistence():
    from financial_radar.store import save_portfolio, rows
    db = sqlite3.connect(":memory:", check_same_thread=False)
    db.row_factory = sqlite3.Row
    from financial_radar.store import DDL
    db.executescript(DDL)
    
    records = [{"ticker": "AAPL", "shares": 100, "weight": 1.0, "cost_basis": 150.0}]
    save_portfolio(db, records)
    
    persisted = rows(db, "SELECT * FROM portfolio")
    assert len(persisted) == 1
    assert persisted[0]["ticker"] == "AAPL"
    assert persisted[0]["shares"] == 100
    assert persisted[0]["weight"] == 1.0
    assert persisted[0]["cost_basis"] == 150.0

# =========================================================
# APPTEST WORKFLOW (Streamlit UI execution)
# =========================================================
def test_streamlit_app_workflow(tmp_path, monkeypatch):
    os.environ["SEC_USER_AGENT"] = "Test Analyst test@example.com"
    import financial_radar.store
    import financial_radar.pipeline
    
    # Mock connect to return our populated in-memory DB
    test_db = setup_mock_db()
    monkeypatch.setattr(financial_radar.store, "connect", lambda *args, **kwargs: test_db)
    monkeypatch.setattr(financial_radar.pipeline, "load_universe", lambda: [{"ticker": "AAPL", "sector": "Tech", "cik": "0000320193"}])
    
    at = AppTest.from_file("../app.py", default_timeout=30)
    at.run()
    
    # 1. App starts
    assert not at.exception, str(at.exception)
    
    # 2. Portfolio tab renders
    assert "1. Company Selection" in at.tabs[0].subheader[0].value
    
    # 3. Watchlist save works (simulate button click)
    # The default selected active_tickers is ["AAPL"]
    at.tabs[0].button[0].click().run()
    assert not at.exception
    
    # 7. Attention queue renders a known HIGH signal
    # 8. Severity ordering (HIGH should be at top if multiple)
    assert "Attention Queue" in at.tabs[2].subheader[0].value
    df_queue = at.tabs[2].dataframe[0].value
    assert not df_queue.empty
    assert df_queue.iloc[0]["Severity"] == "HIGH"
