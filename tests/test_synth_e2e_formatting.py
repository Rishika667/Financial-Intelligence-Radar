import pytest
from financial_radar.synthesis import synthesize_company
from financial_radar.store import connect, save_observations
from financial_radar.models import Observation, DataQuality
from datetime import date

def test_synthesis_end_to_end_formatting():
    c = connect(':memory:')
    
    # We don't need a real SEC event, just need observations to exist to trigger output
    obs = [
        Observation("AAPL", "revenue", 12400000000, "USD", date(2024,12,31), "QUARTER", DataQuality.REPORTED, tuple(), comparable=True, fiscal_year=2025, fiscal_period="Q1"),
        Observation("AAPL", "revenue", 10000000000, "USD", date(2023,12,31), "QUARTER", DataQuality.REPORTED, tuple(), comparable=True, fiscal_year=2024, fiscal_period="Q1"),
    ]
    save_observations(c, obs)
    
    # We must create the tables manually if store.py setup_db is not called natively inside connect
    c.execute("CREATE TABLE IF NOT EXISTS signals(company TEXT, signal_id TEXT, severity TEXT, confidence TEXT, explanation TEXT, evidence TEXT, suppressed INTEGER, suppression_reason TEXT, UNIQUE(company, signal_id))")
    c.execute("CREATE TABLE IF NOT EXISTS events(company TEXT, event_type TEXT, description TEXT, url TEXT, filed TEXT, form TEXT, UNIQUE(url, company))")
    
    synthesis = synthesize_company("AAPL", c)
    
    # We expect "$12.4B from $10.0B" in the output
    observed = " ".join(synthesis["observed"])
    
    assert "$12.4B" in observed
    assert "$10.0B" in observed
