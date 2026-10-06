import pytest
from datetime import date
from financial_radar.models import Observation, DataQuality
from financial_radar.peers import peer_context

def test_peer_context_positioning():
    # Setup company and 2 peers
    members = ["P1", "P2"]
    obs = [
        Observation("C", "revenue", 100, "USD", date(2025,1,1), "QUARTER", DataQuality.REPORTED, tuple(), comparable=True, fiscal_year=2025, fiscal_period="Q1"),
        Observation("P1", "revenue", 80, "USD", date(2025,1,1), "QUARTER", DataQuality.REPORTED, tuple(), comparable=True, fiscal_year=2025, fiscal_period="Q1"),
        Observation("P2", "revenue", 90, "USD", date(2025,1,1), "QUARTER", DataQuality.REPORTED, tuple(), comparable=True, fiscal_year=2025, fiscal_period="Q1")
    ]
    
    ctx = peer_context("C", "revenue", obs, members)
    assert ctx["available"] == True
    assert ctx["n_peers"] == 2
    assert ctx["peer_median"] == 85.0
    assert ctx["position"] == "Above Median"
    assert ctx["unavailable_peers"] == []

    # Insufficient peers
    obs_missing = [
        Observation("C", "revenue", 100, "USD", date(2025,1,1), "QUARTER", DataQuality.REPORTED, tuple(), comparable=True, fiscal_year=2025, fiscal_period="Q1"),
        Observation("P1", "revenue", 80, "USD", date(2025,1,1), "QUARTER", DataQuality.REPORTED, tuple(), comparable=True, fiscal_year=2025, fiscal_period="Q1")
    ]
    ctx_missing = peer_context("C", "revenue", obs_missing, members)
    assert ctx_missing["available"] == False
    assert ctx_missing["n_peers"] == 1
    assert ctx_missing["peer_median"] is None
    assert ctx_missing["position"] == "Unavailable"
    assert ctx_missing["unavailable_peers"] == ["P2"]
