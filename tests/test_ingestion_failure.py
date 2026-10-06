import pytest
from datetime import date
from financial_radar.pipeline import ingest_company
from financial_radar.store import connect, save_observations, rows
from financial_radar.models import Observation, DataQuality

class FakeFailingSECClient:
    def submissions(self, cik):
        raise Exception("API rate limit exceeded")
    def company_facts(self, cik):
        raise Exception("API rate limit exceeded")

def test_ingestion_failure_preserves_data():
    c = connect(':memory:')
    
    # Insert previous valid data
    o = Observation("AAPL", "revenue", 100, "USD", date(2024,12,31), "QUARTER", DataQuality.REPORTED, tuple())
    save_observations(c, [o])
    
    # Run failing ingestion
    client = FakeFailingSECClient()
    try:
        ingest_company(client, c, {"ticker": "AAPL", "cik": "0000320193"})
    except Exception:
        pass # Expected
        
    # Check that previous data remains
    obs = rows(c, "SELECT * FROM observations WHERE company='AAPL'")
    assert len(obs) == 1
    assert obs[0]["value"] == 100
    
    # Check that failure signal is visible
    sigs = rows(c, "SELECT * FROM signals WHERE company='AAPL'")
    assert len(sigs) == 1
    assert sigs[0]["signal_id"] == "INGESTION_FAILED"
    assert sigs[0]["severity"] == "HIGH"
