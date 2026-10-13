import pytest
import json
from pathlib import Path
from financial_radar.store import connect, rows
from financial_radar.pipeline import ingest_company, evaluate
from financial_radar.core import SECClient
from financial_radar.metrics import get_comparison_pair


class MultiCompanyMockSECClient(SECClient):
    """Zero-network SECClient loading authoritative multi-period fixtures."""
    def __init__(self):
        super().__init__("TestAnalyst test@analystradar.org")
        self.cik_map = {
            "0000320193": "aapl",
            "0000789019": "msft",
            "0001045810": "nvda",
            "0000019617": "jpm",
            "0001018724": "amzn",
            "0001652044": "googl",
            "0001326801": "meta",
            "0001318605": "tsla",
            "0000200406": "jnj",
            "0000034088": "xom",
        }

    def _resolve(self, cik):
        clean = str(int(cik)).zfill(10)
        return self.cik_map.get(clean, "aapl")

    def submissions(self, cik, fetch_historical=False):
        ticker = self._resolve(cik)
        p = Path(f"tests/fixtures/{ticker}_submissions.json")
        assert p.exists(), f"Authoritative SEC submissions fixture missing: {p}"
        return json.loads(p.read_text(encoding="utf-8"))

    def company_facts(self, cik):
        ticker = self._resolve(cik)
        p = Path(f"tests/fixtures/{ticker}_facts.json")
        assert p.exists(), f"Authoritative SEC facts fixture missing: {p}"
        return json.loads(p.read_text(encoding="utf-8"))


TEN_COMPANIES = [
    {"ticker": "AAPL",  "cik": "0000320193", "sector": "Information Technology"},
    {"ticker": "MSFT",  "cik": "0000789019", "sector": "Information Technology"},
    {"ticker": "NVDA",  "cik": "0001045810", "sector": "Information Technology"},
    {"ticker": "JPM",   "cik": "0000019617", "sector": "Financials"},
    {"ticker": "AMZN",  "cik": "0001018724", "sector": "Consumer Discretionary"},
    {"ticker": "GOOGL", "cik": "0001652044", "sector": "Communication Services"},
    {"ticker": "META",  "cik": "0001326801", "sector": "Communication Services"},
    {"ticker": "TSLA",  "cik": "0001318605", "sector": "Consumer Discretionary"},
    {"ticker": "JNJ",   "cik": "0000200406", "sector": "Health Care"},
    {"ticker": "XOM",   "cik": "0000034088", "sector": "Energy"},
]


def test_ten_company_fixtures_exist_and_authentic():
    """All 10 distinct companies must have authentic, non-empty SEC fixtures."""
    client = MultiCompanyMockSECClient()
    assert len(TEN_COMPANIES) == 10, "Must test exactly 10 distinct companies"
    for comp in TEN_COMPANIES:
        subs = client.submissions(comp["cik"])
        facts = client.company_facts(comp["cik"])
        assert "filings" in subs, f"Submissions must contain filings for {comp['ticker']}"
        assert "facts" in facts, f"Facts must contain facts object for {comp['ticker']}"
        assert "us-gaap" in facts["facts"], f"Must contain us-gaap facts for {comp['ticker']}"


def test_ten_company_pipeline_multi_period_ingestion():
    """Execute end-to-end extraction, normalization, and persistence across all 10 companies."""
    c = connect(":memory:")
    client = MultiCompanyMockSECClient()

    for comp in TEN_COMPANIES:
        res = ingest_company(client, c, comp)
        assert res["observations"] > 0, f"Expected non-zero observations for {comp['ticker']}"

    # Verify all 10 distinct companies have persisted observations in SQLite
    stored_comps = {r["company"] for r in rows(c, "SELECT DISTINCT company FROM observations")}
    assert len(stored_comps) == 10, f"All 10 companies must be present in observations: {stored_comps}"

    # Multi-period coverage check: exactly 9 of the 10 companies exhibit multi-year observations in fixture data
    multi_period_comps = rows(c, "SELECT company, COUNT(DISTINCT fiscal_year) as fy_count FROM observations WHERE fiscal_year IS NOT NULL GROUP BY company HAVING fy_count >= 2")
    expected_multi_year = {"AAPL", "AMZN", "GOOGL", "JNJ", "META", "MSFT", "NVDA", "TSLA", "XOM"}
    actual_multi_year = {r["company"] for r in multi_period_comps}
    assert actual_multi_year == expected_multi_year, f"Expected multi-year companies {expected_multi_year}, got {actual_multi_year}"
    assert len(multi_period_comps) == 9, f"Exactly 9 companies must exhibit multi-year observations, got {len(multi_period_comps)}"


def test_fiscal_matching_and_incomparable_period_handling():
    """Verify strict fiscal comparison matching, exact values, and suppression of incomparable periods."""
    from financial_radar.store import load_observations_for_companies
    c = connect(":memory:")
    client = MultiCompanyMockSECClient()

    # 1. Test 5 companies with verified, unconditional quarterly YoY comparison pairs
    yoy_cases = [
        {"ticker": "AMZN", "cik": "0001018724", "sector": "Consumer Discretionary", "quarter": "Q2", "fy_curr": 2026, "fy_prior": 2025, "val_curr": 200606000000.0, "val_prior": 147977000000.0},
        {"ticker": "META", "cik": "0001326801", "sector": "Communication Services", "quarter": "Q2", "fy_curr": 2026, "fy_prior": 2025, "val_curr": 60801000000.0, "val_prior": 39071000000.0},
        {"ticker": "TSLA", "cik": "0001318605", "sector": "Consumer Discretionary", "quarter": "Q2", "fy_curr": 2026, "fy_prior": 2025, "val_curr": 28236000000.0, "val_prior": 25500000000.0},
        {"ticker": "JNJ",  "cik": "0000200406", "sector": "Health Care",             "quarter": "Q2", "fy_curr": 2026, "fy_prior": 2025, "val_curr": 25310000000.0, "val_prior": 22447000000.0},
        {"ticker": "XOM",  "cik": "0000034088", "sector": "Energy",                  "quarter": "Q1", "fy_curr": 2026, "fy_prior": 2025, "val_curr": 85138000000.0, "val_prior": 83083000000.0},
    ]

    for case in yoy_cases:
        ingest_company(client, c, {"ticker": case["ticker"], "cik": case["cik"], "sector": case["sector"]})
        obs = load_observations_for_companies(c, [case["ticker"]])
        curr, prior = get_comparison_pair(obs, "revenue", "QUARTER", mode="yoy")

        # Unconditional existence and alignment assertion
        assert curr is not None, f"Expected valid current observation for {case['ticker']}"
        assert prior is not None, f"Expected valid prior observation for {case['ticker']}"
        assert curr.fiscal_year == prior.fiscal_year + 1 == case["fy_curr"], f"Fiscal year mismatch for {case['ticker']}"
        assert curr.fiscal_period == prior.fiscal_period == case["quarter"], f"Fiscal quarter mismatch for {case['ticker']}"
        assert curr.period_type == prior.period_type == "QUARTER", f"Period type mismatch for {case['ticker']}"
        assert curr.value == case["val_curr"], f"Expected current revenue {case['val_curr']} for {case['ticker']}, got {curr.value}"
        assert prior.value == case["val_prior"], f"Expected prior revenue {case['val_prior']} for {case['ticker']}, got {prior.value}"

    # 2. Test incomplete/incomparable periods: MSFT lacks a matching quarterly prior frame, so prior must be None
    ingest_company(client, c, {"ticker": "MSFT", "cik": "0000789019", "sector": "Information Technology"})
    msft_obs = load_observations_for_companies(c, ["MSFT"])
    m_curr, m_prior = get_comparison_pair(msft_obs, "revenue", "QUARTER", mode="yoy")
    assert m_curr is not None, "MSFT has current quarter observation"
    assert m_prior is None, "MSFT must withhold comparison when prior fiscal frame does not match"

    # 3. Incomparable periods: attempt matching with empty set returns (None, None)
    c_none, p_none = get_comparison_pair([], "revenue", "QUARTER", mode="yoy")
    assert c_none is None and p_none is None, "Empty observations must return None without raising"


def test_provenance_and_derivation_lineage_preservation():
    """Verify source accession, filing dates, and derivation lineage survive to persisted state."""
    c = connect(":memory:")
    client = MultiCompanyMockSECClient()
    ingest_company(client, c, {"ticker": "AAPL", "cik": "0000320193", "sector": "Information Technology"})

    # Check canonical reported observations
    reported = rows(c, "SELECT provenance FROM observations WHERE company='AAPL' AND quality='REPORTED' AND provenance != '[]' LIMIT 5")
    assert len(reported) > 0
    for r in reported:
        prov = json.loads(r["provenance"])
        assert len(prov) > 0
        assert "accession" in prov[0]
        assert "source_url" in prov[0]
        assert "https://www.sec.gov" in prov[0]["source_url"]

    # Check derived observations have derived_from lineage populated
    derived = rows(c, "SELECT derived_from FROM observations WHERE company='AAPL' AND quality='DERIVED' AND derived_from IS NOT NULL LIMIT 5")
    assert len(derived) > 0
    for d in derived:
        der = json.loads(d["derived_from"])
        assert len(der) >= 1, "Derived metric must record derivation lineage"


def test_sector_policy_suppression_financials():
    """Verify that corporate metrics are properly suppressed for Financials (JPM) unconditionally."""
    from datetime import date
    from financial_radar.models import Observation, DataQuality
    from financial_radar.pipeline import evaluate

    c = connect(":memory:")
    client = MultiCompanyMockSECClient()
    ingest_company(client, c, {"ticker": "JPM", "cik": "0000019617", "sector": "Financials"})

    # Synthetic observations for corporate metrics evaluated under sector='Financials'
    synth_obs = [
        Observation("JPM", "gross_margin", 0.40, "pure", date(2025, 1, 1), "QUARTER", DataQuality.REPORTED, tuple(), comparable=True, fiscal_year=2025, fiscal_period="Q1"),
        Observation("JPM", "gross_margin", 0.50, "pure", date(2024, 1, 1), "QUARTER", DataQuality.REPORTED, tuple(), comparable=True, fiscal_year=2024, fiscal_period="Q1"),
    ]
    sigs = evaluate("JPM", synth_obs, sector="Financials")
    gm_sig = next((s for s in sigs if s.signal_id == "GROSS_MARGIN_COMPRESSION"), None)
    assert gm_sig is not None, "Expected GROSS_MARGIN_COMPRESSION to be evaluated"
    assert gm_sig.severity == "UNKNOWN", "Suppressed corporate signal must have UNKNOWN severity"
    assert gm_sig.suppressed_reason == "Sector Context (Financials)", "Suppressed signal must document explicit rationale"

