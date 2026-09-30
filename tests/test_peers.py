from datetime import date
from financial_radar.models import Observation, DataQuality
from financial_radar.peers import peer_context, find_peer_group, peer_context_for_company


def o(company, metric, value, unit="USD", end=date(2025, 6, 30), pt="QUARTER", qual=DataQuality.REPORTED, comp=True):
    return Observation(
        company, metric, value, unit, end, pt, qual, (), comparable=comp
    )


def test_peer_context_with_enough_peers():
    obs = [o("AAPL", "revenue", 100), o("MSFT", "revenue", 120), o("GOOG", "revenue", 90)]
    ctx = peer_context("AAPL", "revenue", obs, ["MSFT", "GOOG"])
    assert ctx["available"] is True
    assert ctx["company_value"] == 100
    assert ctx["peer_median"] == 105  # median of 120, 90
    assert ctx["n_peers"] == 2


def test_peer_context_insufficient_peers():
    obs = [o("AAPL", "revenue", 100), o("MSFT", "revenue", 120)]
    ctx = peer_context("AAPL", "revenue", obs, ["MSFT"])
    assert ctx["available"] is False


def test_peer_context_no_company_value():
    obs = [o("MSFT", "revenue", 120), o("GOOG", "revenue", 90)]
    ctx = peer_context("AAPL", "revenue", obs, ["MSFT", "GOOG"])
    assert ctx["available"] is False


def test_find_peer_group():
    pg = {"groups": [{"id": "tech", "members": ["AAPL", "MSFT", "GOOG"]}]}
    gid, members = find_peer_group("AAPL", pg)
    assert gid == "tech"
    assert "AAPL" not in members
    assert "MSFT" in members


def test_find_peer_group_not_found():
    pg = {"groups": [{"id": "tech", "members": ["MSFT"]}]}
    gid, members = find_peer_group("AAPL", pg)
    assert gid is None
    assert members == []


def test_peer_context_for_company():
    obs = [
        o("AAPL", "revenue", 100), o("MSFT", "revenue", 120),
        o("GOOG", "revenue", 90),
        o("AAPL", "net_income", 20), o("MSFT", "net_income", 30),
        o("GOOG", "net_income", 15),
    ]
    pg = {"version": "2026.1", "groups": [{"id": "tech", "members": ["AAPL", "MSFT", "GOOG"]}]}
    result = peer_context_for_company("AAPL", obs, pg)
    assert result["group_id"] == "tech"
    assert len(result["contexts"]) == 2  # revenue and net_income
    assert result["version"] == "2026.1"


def test_incomparable_excluded_from_peers():
    obs = [
        o("AAPL", "revenue", 100),
        o("MSFT", "revenue", 120),
        o("GOOG", "revenue", 90, comp=False)  # Not comparable
    ]
    ctx = peer_context("AAPL", "revenue", obs, ["MSFT", "GOOG"])
    assert ctx["n_peers"] == 1
    assert ctx["available"] is False  # only 1 peer, need >= 2


def test_strict_peer_matching():
    """Verify that peers must match unit, period type, and period end."""
    obs = [
        o("AAPL", "revenue", 100, unit="USD", end=date(2025, 6, 30), pt="QUARTER"),
        
        o("MSFT", "revenue", 120, unit="USD", end=date(2025, 6, 30), pt="QUARTER"), # Valid
        o("GOOG", "revenue", 110, unit="USD", end=date(2025, 6, 30), pt="QUARTER"), # Valid
        
        # Mismatches
        o("META", "revenue", 90, unit="EUR", end=date(2025, 6, 30), pt="QUARTER"), # Wrong unit
        o("AMZN", "revenue", 90, unit="USD", end=date(2025, 3, 31), pt="QUARTER"), # Wrong end
        o("NFLX", "revenue", 90, unit="USD", end=date(2025, 6, 30), pt="YTD_6M"),  # Wrong type
        o("TSLA", "revenue", 90, unit="USD", end=date(2025, 6, 30), pt="QUARTER", qual=DataQuality.CALCULATION_INVALID), # Wrong quality
    ]
    ctx = peer_context("AAPL", "revenue", obs, ["MSFT", "GOOG", "META", "AMZN", "NFLX", "TSLA"])
    assert ctx["n_peers"] == 2
    assert ctx["available"] is True
    assert ctx["peer_median"] == 115

def test_45_day_fiscal_alignment():
    from financial_radar.peers import peer_context_for_company
    from financial_radar.models import Observation, DataQuality
    from datetime import date
    o = lambda c, m, v, u, pe, pt: Observation(c, m, v, u, pe, pt, DataQuality.REPORTED)
    
    obs = [
        o("AAPL", "revenue", 100, "USD", date(2023, 9, 30), "QUARTER"),
        # Valid peer, same period type, same unit, 35 days apart
        o("MSFT", "revenue", 120, "USD", date(2023, 11, 4), "QUARTER"),
        o("GOOG", "revenue", 90, "USD", date(2023, 9, 30), "QUARTER"),
        # Invalid peer, different period type (ANNUAL)
        o("MSFT", "revenue", 500, "USD", date(2023, 11, 4), "ANNUAL"),
        # Invalid peer, >45 days apart
        o("GOOG", "revenue", 1000, "USD", date(2023, 8, 14), "QUARTER"),
        # Invalid peer, different unit
        o("META", "revenue", 80, "EUR", date(2023, 9, 30), "QUARTER")
    ]
    
    pg = {"version": "v1", "groups": [{"id": "G1", "members": ["AAPL", "MSFT", "GOOG", "META"]}]}
    ctx = peer_context_for_company("AAPL", obs, pg)
    
    contexts = ctx['contexts']
    assert len(contexts) == 1
    assert contexts[0]["metric"] == "revenue"
    
    assert contexts[0]["peer_median"] == 105.0
     # AAPL (100) vs MSFT (120), AAPL is lowest
