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

def test_research_mode_evidence_display(monkeypatch):
    test_db = os.path.abspath("test_research_radar.sqlite")
    if os.path.exists(test_db):
        os.remove(test_db)
        
    c = connect(test_db)
    ingest_company(MockClient(), c, {"ticker": "AAPL", "cik": "320193"})
    c.execute("INSERT INTO portfolio (ticker, weight, exposure) VALUES ('AAPL', 0.05, 10000)")
    c.execute("INSERT INTO watchlist (ticker, active, cik) VALUES ('AAPL', 1, '320193')")
    c.commit()

    monkeypatch.setenv("DB_PATH", test_db)
    os.environ["DB_PATH"] = test_db

    at = AppTest.from_file("../app.py", default_timeout=30)
    at.run()
    assert not at.exception
    
    research_tab = at.tabs[3]
    
    markdowns = [m.value for m in research_tab.markdown]
    headers = [h.value for h in research_tab.header]
    subheaders = [sh.value for sh in research_tab.subheader]
    all_text = " ".join(markdowns + headers + subheaders)
    
    assert "1. Executive Snapshot" in all_text, "Executive Snapshot missing"
    assert "2. Analyst Synthesis" in all_text, "Analyst Synthesis missing"
    assert "3. Financial Performance" in all_text, "Financial Performance missing"
    assert "4. Signals & Evidence" in all_text, "Signals & Evidence missing"
    assert "5. Peer Context" in all_text, "Peer Context missing"
    
    # Check for AAPL specific financial values
    metrics_text = [m.value for m in research_tab.metric]
    metric_labels = [m.label for m in research_tab.metric]
    
    assert any("Revenue" in lbl for lbl in metric_labels), "Revenue metric missing"
    assert any("Gross Margin" in lbl for lbl in metric_labels), "Gross Margin metric missing"
    assert any("Operating Margin" in lbl for lbl in metric_labels), "Operating Margin metric missing"
    assert any("Net Income" in lbl for lbl in metric_labels), "Net Income metric missing"
    
    infos = [i.value for i in research_tab.info]
    assert "Insufficient data for trend charts." not in infos
    
    c.close()
