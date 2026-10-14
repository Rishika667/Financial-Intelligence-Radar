import json
import os
import sqlite3
import pytest
from unittest.mock import MagicMock, patch
from datetime import date

from financial_radar.config import get_sec_user_agent, is_public_demo_mode, validate_user_agent
from financial_radar.core import SECClient
from financial_radar.intelligence import generate_intelligence, group_cluster_evidence_by_metric
from financial_radar.models import Observation, DataQuality, Signal
from financial_radar.store import DDL, save_portfolio, rows, save_analyst_review, get_all_analyst_reviews


def test_sec_user_agent_config_precedence(monkeypatch):
    """
    get_sec_user_agent() must read from OS environment first, then st.secrets,
    and return empty string gracefully without crashing if unconfigured.
    """
    # 1. Environment variable present
    monkeypatch.setenv("SEC_USER_AGENT", "EnvAnalyst analyst@example.com")
    assert get_sec_user_agent() == "EnvAnalyst analyst@example.com"

    # 2. Environment variable empty, but st.secrets present
    monkeypatch.delenv("SEC_USER_AGENT", raising=False)
    fake_st = MagicMock()
    fake_st.secrets = {"SEC_USER_AGENT": "SecretAnalyst secret@example.com"}
    monkeypatch.setitem(os.sys.modules, "streamlit", fake_st)
    assert get_sec_user_agent() == "SecretAnalyst secret@example.com"

    # 3. Neither present - must return empty string without raising
    fake_st.secrets = {}
    assert get_sec_user_agent() == ""

    # 4. Streamlit secrets raises exception - must handle gracefully
    type(fake_st).secrets = property(lambda self: (_ for _ in ()).throw(FileNotFoundError("secrets.toml missing")))
    assert get_sec_user_agent() == ""


def test_public_demo_mode_config(monkeypatch):
    """
    is_public_demo_mode() must detect truthy flags from OS environment or st.secrets.
    """
    # 1. Env flag true
    monkeypatch.setenv("PUBLIC_DEMO_MODE", "true")
    assert is_public_demo_mode() is True

    monkeypatch.setenv("PUBLIC_DEMO_MODE", "1")
    assert is_public_demo_mode() is True

    # 2. Env flag false
    monkeypatch.setenv("PUBLIC_DEMO_MODE", "0")
    assert is_public_demo_mode() is False

    # 3. Streamlit secrets fallback
    monkeypatch.delenv("PUBLIC_DEMO_MODE", raising=False)
    fake_st = MagicMock()
    fake_st.secrets = {"PUBLIC_DEMO_MODE": "true"}
    monkeypatch.setitem(os.sys.modules, "streamlit", fake_st)
    assert is_public_demo_mode() is True


def test_validate_user_agent():
    """
    validate_user_agent must enforce identity and contact email rules.
    """
    assert validate_user_agent("Analyst Research analyst@example.com") is True
    assert validate_user_agent("") is False
    assert validate_user_agent("test") is False
    assert validate_user_agent("NoEmailProvided") is False


def test_sec_client_bounded_retry_and_backoff(monkeypatch, tmp_path):
    """
    SECClient must retry transient 429 and 503 errors respecting Retry-After,
    and raise on non-retryable 404 immediately without spinning.
    """
    client = SECClient("Analyst analyst@example.com", raw_dir=str(tmp_path), min_interval_seconds=0.0)

    # 1. Transient 429 followed by 200
    resp_429 = MagicMock()
    resp_429.status_code = 429
    resp_429.headers = {"Retry-After": "0.01"}

    resp_200 = MagicMock()
    resp_200.status_code = 200
    resp_200.json.return_value = {"status": "ok"}
    resp_200.raise_for_status.return_value = None

    with patch.object(client.s, "get", side_effect=[resp_429, resp_200]) as mock_get:
        data = client.get_json("https://data.sec.gov/test.json", "test.json", max_retries=2)
        assert data == {"status": "ok"}
        assert mock_get.call_count == 2

    # 2. Non-retryable 404 should fail immediately
    resp_404 = MagicMock()
    resp_404.status_code = 404
    import requests
    http_error_404 = requests.exceptions.HTTPError(response=resp_404)
    resp_404.raise_for_status.side_effect = http_error_404

    with patch.object(client.s, "get", return_value=resp_404) as mock_get:
        with pytest.raises(requests.exceptions.HTTPError):
            client.get_json("https://data.sec.gov/missing.json", "missing.json", max_retries=3)
        assert mock_get.call_count == 1


def test_multi_factor_cluster_evidence_grouping_prevents_cross_metric_pairing():
    """
    group_cluster_evidence_by_metric must group observations by metric so that
    different metrics (e.g. gross_margin and free_cash_flow) are never paired
    together as a false current/prior pair.
    """
    cluster_ev = [
        {"metric": "gross_margin", "value": 0.35, "unit": "pure", "period_end": "2023-12-31"},
        {"metric": "gross_margin", "value": 0.40, "unit": "pure", "period_end": "2022-12-31"},
        {"metric": "free_cash_flow", "value": 10000000, "unit": "USD", "period_end": "2023-12-31"},
        {"metric": "free_cash_flow", "value": 50000000, "unit": "USD", "period_end": "2022-12-31"},
    ]

    grouped = group_cluster_evidence_by_metric(cluster_ev)
    assert "gross_margin" in grouped
    assert "free_cash_flow" in grouped

    gm_group = grouped["gross_margin"]
    assert gm_group["current"]["value"] == 0.35
    assert gm_group["prior"]["value"] == 0.40
    assert gm_group["current"]["metric"] == "gross_margin"
    assert gm_group["prior"]["metric"] == "gross_margin"

    fcf_group = grouped["free_cash_flow"]
    assert fcf_group["current"]["value"] == 10000000
    assert fcf_group["prior"]["value"] == 50000000
    assert fcf_group["current"]["metric"] == "free_cash_flow"
    assert fcf_group["prior"]["metric"] == "free_cash_flow"

    # Multi-factor cluster intelligence explanation
    intel = generate_intelligence("MULTI_FACTOR_DETERIORATION_CLUSTER", "ACME", "Tech", json.dumps(cluster_ev))
    assert "Simultaneous deterioration detected across 2 fundamental metrics" in intel["what_changed"]
    assert "Gross Margin" in intel["what_changed"]
    assert "Free Cash Flow" in intel["what_changed"]
    assert "Do not treat individual metrics within the cluster as a single two-point comparison" in intel["why_it_matters"]


def test_public_demo_mode_state_isolation():
    """
    In public demo mode, user portfolio modifications and analyst reviews
    must remain session-scoped and never mutate the persistent shared database.
    """
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.executescript(DDL)

    # Initial DB state has no holdings or reviews
    assert len(rows(c, "SELECT * FROM portfolio")) == 0
    assert len(rows(c, "SELECT * FROM analyst_reviews")) == 0

    # Simulate visitor session state in demo mode
    session_portfolio = {
        "AAPL": {"ticker": "AAPL", "shares": 100, "weight": 0.15, "cost_basis": 150.0, "exposure": 18000.0}
    }
    session_reviews = {
        "AAPL_GROSS_MARGIN_COMPRESSION_123": {"status": "UNDER_REVIEW", "note": "Private research note", "updated_at": "2026-10-15T00:00:00"}
    }

    # Verify that persistent shared database was NOT mutated
    assert len(rows(c, "SELECT * FROM portfolio")) == 0
    assert len(rows(c, "SELECT * FROM analyst_reviews")) == 0

    # Non-demo mode persists to DB
    save_portfolio(c, [session_portfolio["AAPL"]])
    assert len(rows(c, "SELECT * FROM portfolio")) == 1

    save_analyst_review(c, "AAPL_GROSS_MARGIN_COMPRESSION_123", "AAPL", "GROSS_MARGIN_COMPRESSION", "UNDER_REVIEW", "Shared note")
    assert len(rows(c, "SELECT * FROM analyst_reviews")) == 1


def test_defensible_ratio_explanations():
    """
    Ratios must acknowledge that movements reflect changes in numerator,
    denominator, or both, avoiding unsubstantiated causality claims.
    """
    ev_rec = json.dumps([
        {"metric": "receivables_revenue_ratio", "value": 0.35, "unit": "pure", "period_end": "2023-12-31"},
        {"metric": "receivables_revenue_ratio", "value": 0.15, "unit": "pure", "period_end": "2022-12-31"},
    ])
    res_rec = generate_intelligence("RECEIVABLES_REVENUE_DIVERGENCE", "ACME", "Tech", ev_rec)
    what_rec = res_rec.get("what_changed", "")
    assert "This may reflect a change in the balance-sheet measure, revenue, or both" in what_rec

    ev_inv = json.dumps([
        {"metric": "inventory_sales_ratio", "value": 0.35, "unit": "pure", "period_end": "2023-12-31"},
        {"metric": "inventory_sales_ratio", "value": 0.15, "unit": "pure", "period_end": "2022-12-31"},
    ])
    res_inv = generate_intelligence("INVENTORY_SALES_DIVERGENCE", "ACME", "Tech", ev_inv)
    what_inv = res_inv.get("what_changed", "")
    assert "This may reflect a change in inventory levels, sales, or both" in what_inv
    assert "receivables" not in what_inv.lower()
