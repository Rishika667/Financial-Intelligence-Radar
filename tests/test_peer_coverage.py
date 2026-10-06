import pytest
from datetime import date
from financial_radar.models import Observation, DataQuality
from financial_radar.peers import peer_context

def test_peer_coverage_and_strict_fiscal():
    members = ["P1", "P2", "P3"]
    # Anchor Company
    obs = [Observation("C", "revenue", 100, "USD", date(2025,1,1), "QUARTER", DataQuality.REPORTED, tuple(), comparable=True, fiscal_year=2025, fiscal_period="Q1")]
    
    # 0 peers
    ctx_0 = peer_context("C", "revenue", obs, members)
    assert ctx_0["available"] == False
    assert ctx_0["n_peers"] == 0
    assert ctx_0["coverage_count"] == 0
    assert ctx_0["total_peer_count"] == 3
    assert ctx_0["position"] == "Unavailable"
    
    # 1 peer (P1)
    obs.append(Observation("P1", "revenue", 80, "USD", date(2025,1,1), "QUARTER", DataQuality.REPORTED, tuple(), comparable=True, fiscal_year=2025, fiscal_period="Q1"))
    ctx_1 = peer_context("C", "revenue", obs, members)
    assert ctx_1["available"] == False
    assert ctx_1["coverage_count"] == 1
    assert ctx_1["peer_median"] is None
    
    # 2 peers (P1, P2) -> P2 has conflicting fiscal metadata but identical date
    obs.append(Observation("P2", "revenue", 90, "USD", date(2025,1,1), "QUARTER", DataQuality.REPORTED, tuple(), comparable=True, fiscal_year=2024, fiscal_period="Q4"))
    ctx_2 = peer_context("C", "revenue", obs, members)
    # Because of strict matching, P2 is skipped even though dates align perfectly!
    assert ctx_2["available"] == False
    assert ctx_2["coverage_count"] == 1
    
    # 2 valid peers (P1, P3) -> P3 missing fiscal metadata, relying on date
    obs.append(Observation("P3", "revenue", 120, "USD", date(2025,1,10), "QUARTER", DataQuality.REPORTED, tuple(), comparable=True, fiscal_year=None, fiscal_period=None))
    ctx_3 = peer_context("C", "revenue", obs, members)
    assert ctx_3["available"] == True
    assert ctx_3["coverage_count"] == 2
    assert ctx_3["peer_median"] == 100.0 # median of 80 and 120
    assert ctx_3["position"] == "At Median" # 100 == 100

    # Test company accidentally included in members
    ctx_self = peer_context("C", "revenue", obs, members + ["C"])
    assert ctx_self["available"] == True
    assert "C" not in ctx_self["unavailable_peers"]
    assert ctx_self["total_peer_count"] == 3 # 'C' wasn't matched because the inner loop filters p_obs by company=p where p == 'C', but wait...
    
    # Actually if members includes C, it WILL find C's own observation!
    # Let's see if the code in pipeline.py prevents it (it does via find_peer_group).
    # But peer_context itself doesn't explicitly `continue` if p == company.
    # The prompt said: "3. Explicitly exclude the company itself."
