from datetime import date
from financial_radar.models import Observation, DataQuality
from financial_radar.peers import peer_context, find_peer_group, peer_context_for_company


def o(company, metric, value):
    return Observation(
        company, metric, value, "USD", date(2025, 6, 30),
        "QUARTER", DataQuality.REPORTED,
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
    good = o("MSFT", "revenue", 120)
    bad = Observation(
        "GOOG", "revenue", 90, "USD", date(2025, 6, 30),
        "QUARTER", DataQuality.REPORTED, comparable=False,
    )
    obs = [o("AAPL", "revenue", 100), good, bad]
    ctx = peer_context("AAPL", "revenue", obs, ["MSFT", "GOOG"])
    assert ctx["n_peers"] == 1
    assert ctx["available"] is False  # only 1 peer, need >= 2
