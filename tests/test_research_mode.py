import pytest
from streamlit.testing.v1 import AppTest
import json
from pathlib import Path
import sys
sys.path.append("src")
from financial_radar.store import connect
from financial_radar.pipeline import ingest_company
from financial_radar.core import SECClient
import os

class MockClient(SECClient):
    def __init__(self):
        super().__init__("Test@example.com")
    def submissions(self, cik):
        return json.loads(Path("tests/fixtures/aapl_submissions.json").read_text(encoding="utf-8"))
    def company_facts(self, cik):
        return json.loads(Path("tests/fixtures/aapl_facts.json").read_text(encoding="utf-8"))

def test_research_mode_strong_assertions(monkeypatch):
    test_db = os.path.abspath("test_research_radar2.sqlite")
    if os.path.exists(test_db):
        try:
            os.remove(test_db)
        except PermissionError:
            pass

        
    c = connect(test_db)
    ingest_company(MockClient(), c, {"ticker": "AAPL", "cik": "320193"})
    c.execute("INSERT INTO watchlist (ticker, active, cik) VALUES ('AAPL', 1, '320193')")
    
    from financial_radar.models import Signal, Observation, DataQuality
    from datetime import date
    
    # Inject a fake signal to test evidence display
    s = Signal("GROSS_MARGIN_COMPRESSION", "AAPL", "HIGH", "HIGH", "Margin fell", 
        (Observation("AAPL", "gross_margin", 0.40, "pure", date(2023,9,30), "QUARTER", DataQuality.REPORTED, tuple([
            {"source_url": "https://www.sec.gov/Archives/edgar/data/320193/123/a.htm"}
        ])),)
    )
    c.execute("INSERT INTO signals VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", (
        s.signal_id, s.company, s.severity, s.confidence, s.explanation, 
        None, json.dumps([{"metric": "gross_margin", "provenance": [{"source_url": "https://www.sec.gov/Archives/edgar/data/320193/123/a.htm"}]}]), "v1", "[]"
    ))
    c.commit()

    monkeypatch.setenv("DB_PATH", test_db)
    os.environ["DB_PATH"] = test_db

    at = AppTest.from_file("../app.py", default_timeout=30)
    at.run()
    assert not at.exception
    
    research_tab = at.tabs[3]
    all_md = " ".join([m.value for m in research_tab.markdown] + [h.value for h in research_tab.header] + [s.value for s in research_tab.subheader] + [i.value for i in research_tab.info])
    
    metrics = [m.value for m in research_tab.metric]
    
    # 1. Assert JPM false banking cluster doesn't appear
    assert "Banking Analytics" not in all_md
    
    # 2. Assert Actual SEC Evidence URL
    assert "https://www.sec.gov/Archives/edgar/data/320193/" in all_md, "Must contain actual SEC evidence URL"
    
    # 3. Assert precise numeric formatting
    assert any("B" in str(v) or "M" in str(v) for v in metrics), "Metrics should be formatted with B/M suffixes"
    
    # 4. Assert readiness state
    main_md = " ".join([m.value for m in at.main.markdown])
    readiness_df = at.tabs[0].dataframe[0].value
    assert len(readiness_df) > 0
    assert "READY" in readiness_df["State"].values or "PARTIAL" in readiness_df["State"].values
    
    c.close()
    if os.path.exists(test_db):
        try:
            os.remove(test_db)
        except PermissionError:
            pass

