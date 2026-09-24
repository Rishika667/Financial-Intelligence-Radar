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
