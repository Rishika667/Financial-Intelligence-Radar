import pytest
from streamlit.testing.v1 import AppTest
import sqlite3
import pandas as pd
import os
import json

def setup_mock_db():
    db = sqlite3.connect(":memory:", check_same_thread=False)
    db.row_factory = sqlite3.Row
    from financial_radar.store import DDL
    db.executescript(DDL)
    return db

def test_fresh_install_workflow(tmp_path, monkeypatch):
    os.environ["SEC_USER_AGENT"] = "Test Analyst test@example.com"
    import financial_radar.store
    import financial_radar.pipeline
    test_db = setup_mock_db()
    monkeypatch.setattr(financial_radar.store, "connect", lambda *args, **kwargs: test_db)
    monkeypatch.setattr(financial_radar.pipeline, "load_universe", lambda: [{"ticker": "AAPL", "sector": "Tech", "cik": "0000320193"}])
    
    at = AppTest.from_file("../app.py", default_timeout=30)
    at.run()
    
    assert not at.exception
    # Setup & Preflight is shown
    assert "1. Company Selection" in at.tabs[0].subheader[0].value
    
    # Save watchlist with AAPL
    at.tabs[0].button[0].click().run()
    assert not at.exception
    
    # Test SEC connectivity
    at.tabs[0].button[1].click().run()
    assert not at.exception
    
    # Assert AAPL is passed to tabs
    pass
