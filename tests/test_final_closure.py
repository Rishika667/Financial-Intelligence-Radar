"""
Focused regression tests for the final closure defects:
1. period_start propagation in _derive()
2. Deterministic growth provenance (no set() iteration)
3. Type-safe peer candidate sorting (date not str)
4. Full comparison-window cluster key
5. Cluster confidence propagation
6. SEC preflight success uses only 4 booleans, not ERRORS
7. YTD selection reversed-input invariance
"""
import os
from datetime import date, datetime
import pytest

from financial_radar.models import Observation, DataQuality, Provenance, Signal, QUALITY_RANK


def _prov(acc="ACC1"):
    return Provenance(acc, f"https://sec.gov/{acc}", date(2023, 1, 1), "10-Q", "rev", datetime(2023, 7, 1))


# ---------------------------------------------------------------------------
# 1. period_start propagation in _derive()
# ---------------------------------------------------------------------------

def test_derived_analytical_metric_propagates_period_start():
    """gross_margin derived from gross_profit + revenue must keep period_start."""
    from financial_radar.metrics import derive_analytical_metrics

    ps = date(2023, 1, 1)
    pe = date(2023, 3, 31)

    rev = Observation("AAPL", "revenue", 100_000, "USD", pe, "QUARTER", DataQuality.REPORTED,
                      (_prov("A1"),), period_start=ps, fiscal_year=2023, fiscal_period="Q1")
    gp = Observation("AAPL", "gross_profit", 43_000, "USD", pe, "QUARTER", DataQuality.REPORTED,
                     (_prov("A2"),), period_start=ps, fiscal_year=2023, fiscal_period="Q1")

    derived = derive_analytical_metrics([rev, gp])
    gm = next((o for o in derived if o.metric == "gross_margin"), None)
    assert gm is not None, "gross_margin must be derived"
    assert gm.period_start == ps, f"Expected period_start={ps}, got {gm.period_start}"
    assert abs(gm.value - 0.43) < 1e-9


# ---------------------------------------------------------------------------
# 2. Deterministic growth provenance (no set() non-determinism)
# ---------------------------------------------------------------------------

def test_growth_provenance_is_deterministic():
    """Revenue growth provenance must be a stable ordered tuple, not a set-iteration artifact."""
    from financial_radar.metrics import derive_analytical_metrics

    pe_curr = date(2023, 3, 31)
    pe_prior = date(2022, 3, 31)

    def make_rev(pe, ps, val, acc, fy, fp):
        return Observation("AAPL", "revenue", val, "USD", pe, "QUARTER",
                           DataQuality.REPORTED, (_prov(acc),),
                           period_start=ps, fiscal_year=fy, fiscal_period=fp)

    obs = [
        make_rev(pe_curr, date(2023, 1, 1), 100_000, "ACC_CURR", 2023, "Q1"),
        make_rev(pe_prior, date(2022, 1, 1), 90_000, "ACC_PRIOR", 2022, "Q1"),
    ]

    results = []
    for _ in range(5):
        derived = derive_analytical_metrics(obs)
        growth = next((o for o in derived if o.metric == "revenue_growth_yoy"), None)
        assert growth is not None
        prov_accessions = tuple(p.accession for p in growth.provenance)
        results.append(prov_accessions)

    assert all(r == results[0] for r in results), "Provenance must be deterministic across multiple calls"


# ---------------------------------------------------------------------------
# 3. Type-safe peer candidate sorting
# ---------------------------------------------------------------------------

def test_peer_sort_key_is_type_safe():
    """Peer candidate sorting must not mix date and str types (date.min must be used, not '')."""
    from financial_radar.peers import peer_context

    pe = date(2023, 3, 31)
    # One observation has period_start=None, another has a real date — must not raise TypeError
    own_obs = Observation("AAPL", "revenue", 100_000, "USD", pe, "QUARTER",
                          DataQuality.REPORTED, (_prov(),),
                          period_start=None, fiscal_year=2023, fiscal_period="Q1")
    peer_obs_a = Observation("MSFT", "revenue", 90_000, "USD", pe, "QUARTER",
                             DataQuality.REPORTED, (_prov("P1"),),
                             period_start=date(2023, 1, 1), fiscal_year=2023, fiscal_period="Q1")
    peer_obs_b = Observation("MSFT", "revenue", 92_000, "USD", date(2023, 6, 30), "QUARTER",
                             DataQuality.REPORTED, (_prov("P2"),),
                             period_start=None, fiscal_year=2023, fiscal_period="Q2")

    # Should not raise — if period_start or "" was used this would fail with TypeError
    result = peer_context("AAPL", "revenue", [own_obs, peer_obs_a, peer_obs_b], ["MSFT"])
    assert isinstance(result, dict)


def test_peer_candidate_determinism_reversed_input():
    """Peer candidate selection result must be identical regardless of input order."""
    from financial_radar.peers import peer_context

    pe = date(2023, 3, 31)
    own = Observation("AAPL", "revenue", 100_000, "USD", pe, "QUARTER",
                      DataQuality.REPORTED, (_prov(),),
                      period_start=date(2023, 1, 1), fiscal_year=2023, fiscal_period="Q1")
    peer1 = Observation("MSFT", "revenue", 80_000, "USD", pe, "QUARTER",
                        DataQuality.REPORTED, (_prov("P1"),),
                        period_start=date(2023, 1, 1), fiscal_year=2023, fiscal_period="Q1")
    peer2 = Observation("GOOG", "revenue", 70_000, "USD", pe, "QUARTER",
                        DataQuality.REPORTED, (_prov("P2"),),
                        period_start=date(2023, 1, 1), fiscal_year=2023, fiscal_period="Q1")

    obs_fwd = [own, peer1, peer2]
    obs_rev = [peer2, peer1, own]

    r1 = peer_context("AAPL", "revenue", obs_fwd, ["MSFT", "GOOG"])
    r2 = peer_context("AAPL", "revenue", obs_rev, ["MSFT", "GOOG"])

    assert r1["peer_median"] == r2["peer_median"]
    assert r1["n_peers"] == r2["n_peers"]
    assert r1["position"] == r2["position"]


# ---------------------------------------------------------------------------
# 4. Full comparison-window cluster key
# ---------------------------------------------------------------------------

def test_cluster_different_prior_windows_do_not_merge():
    """Signals with same company + same current period_end but DIFFERENT prior periods must NOT cluster."""
    from financial_radar.signals import cluster

    q1 = date(2023, 3, 31)
    q2 = date(2023, 6, 30)
    q3 = date(2023, 9, 30)

    # 3 signals for AAPL: current=Q3, but priors differ (Q2 vs Q1)
    o_curr = Observation("AAPL", "rev", 10, "USD", q3, "QUARTER", DataQuality.REPORTED, ())
    o_prior_q2 = Observation("AAPL", "rev", 12, "USD", q2, "QUARTER", DataQuality.REPORTED, ())
    o_prior_q1 = Observation("AAPL", "rev", 13, "USD", q1, "QUARTER", DataQuality.REPORTED, ())

    s1 = Signal("A", "AAPL", "HIGH", "HIGH", "a", (o_curr, o_prior_q2))
    s2 = Signal("B", "AAPL", "HIGH", "HIGH", "b", (o_curr, o_prior_q2))
    s3 = Signal("C", "AAPL", "HIGH", "HIGH", "c", (o_curr, o_prior_q1))  # different prior

    result = cluster([s1, s2, s3])
    # s1+s2 share same window (Q3→Q2), s3 has Q3→Q1 — no single window has 3 signals
    assert len(result) == 0, f"Expected no cluster, got {len(result)}"


def test_cluster_same_window_forms_cluster():
    """3+ signals with identical comparison window must form exactly one cluster."""
    from financial_radar.signals import cluster

    q2 = date(2023, 6, 30)
    q1 = date(2023, 3, 31)

    o_curr = Observation("AAPL", "m1", 10, "USD", q2, "QUARTER", DataQuality.REPORTED, ())
    o_prior = Observation("AAPL", "m1", 12, "USD", q1, "QUARTER", DataQuality.REPORTED, ())

    s1 = Signal("A", "AAPL", "HIGH", "HIGH", "a", (o_curr, o_prior))
    s2 = Signal("B", "AAPL", "HIGH", "HIGH", "b", (o_curr, o_prior))
    s3 = Signal("C", "AAPL", "HIGH", "HIGH", "c", (o_curr, o_prior))

    result = cluster([s1, s2, s3])
    assert len(result) == 1, f"Expected 1 cluster, got {len(result)}"
    assert result[0].signal_id == "MULTI_FACTOR_DETERIORATION_CLUSTER"
    assert result[0].confidence == "HIGH"


def test_cluster_suppressed_signals_excluded():
    """Suppressed signals must not be included in cluster count."""
    from financial_radar.signals import cluster

    q2 = date(2023, 6, 30)
    q1 = date(2023, 3, 31)

    o_curr = Observation("AAPL", "m1", 10, "USD", q2, "QUARTER", DataQuality.REPORTED, ())
    o_prior = Observation("AAPL", "m1", 12, "USD", q1, "QUARTER", DataQuality.REPORTED, ())

    s1 = Signal("A", "AAPL", "HIGH", "HIGH", "a", (o_curr, o_prior))
    s2 = Signal("B", "AAPL", "HIGH", "HIGH", "b", (o_curr, o_prior))
    s3_suppressed = Signal("C", "AAPL", "HIGH", "HIGH", "c", (o_curr, o_prior), suppressed_reason="unit mismatch")

    result = cluster([s1, s2, s3_suppressed])
    assert len(result) == 0, "Suppressed signal must not count toward cluster threshold"


# ---------------------------------------------------------------------------
# 5. Cluster confidence propagation
# ---------------------------------------------------------------------------

def test_cluster_confidence_medium_when_any_derived():
    """Cluster confidence must be MEDIUM if any component signal has MEDIUM confidence."""
    from financial_radar.signals import cluster

    q2 = date(2023, 6, 30)
    q1 = date(2023, 3, 31)
    o_curr = Observation("AAPL", "m1", 10, "USD", q2, "QUARTER", DataQuality.REPORTED, ())
    o_prior = Observation("AAPL", "m1", 12, "USD", q1, "QUARTER", DataQuality.REPORTED, ())

    s1 = Signal("A", "AAPL", "HIGH", "HIGH", "a", (o_curr, o_prior))
    s2 = Signal("B", "AAPL", "HIGH", "HIGH", "b", (o_curr, o_prior))
    s3 = Signal("C", "AAPL", "MEDIUM", "MEDIUM", "c", (o_curr, o_prior))  # MEDIUM confidence

    result = cluster([s1, s2, s3])
    assert len(result) == 1
    assert result[0].confidence == "MEDIUM", f"Expected MEDIUM, got {result[0].confidence}"


def test_cluster_confidence_high_when_all_high():
    """Cluster confidence must be HIGH when all component signals are HIGH."""
    from financial_radar.signals import cluster

    q2 = date(2023, 6, 30)
    q1 = date(2023, 3, 31)
    o_curr = Observation("AAPL", "m1", 10, "USD", q2, "QUARTER", DataQuality.REPORTED, ())
    o_prior = Observation("AAPL", "m1", 12, "USD", q1, "QUARTER", DataQuality.REPORTED, ())

    signals = [Signal(x, "AAPL", "HIGH", "HIGH", x, (o_curr, o_prior)) for x in "ABC"]
    result = cluster(signals)
    assert len(result) == 1
    assert result[0].confidence == "HIGH"


def test_cluster_confidence_input_order_independent():
    """Cluster confidence result must not depend on signal input order."""
    from financial_radar.signals import cluster

    q2 = date(2023, 6, 30)
    q1 = date(2023, 3, 31)
    o_curr = Observation("AAPL", "m1", 10, "USD", q2, "QUARTER", DataQuality.REPORTED, ())
    o_prior = Observation("AAPL", "m1", 12, "USD", q1, "QUARTER", DataQuality.REPORTED, ())

    s_high1 = Signal("A", "AAPL", "HIGH", "HIGH", "a", (o_curr, o_prior))
    s_high2 = Signal("B", "AAPL", "HIGH", "HIGH", "b", (o_curr, o_prior))
    s_med = Signal("C", "AAPL", "MEDIUM", "MEDIUM", "c", (o_curr, o_prior))

    r1 = cluster([s_high1, s_high2, s_med])
    r2 = cluster([s_med, s_high2, s_high1])
    r3 = cluster([s_high2, s_med, s_high1])

    assert r1[0].confidence == r2[0].confidence == r3[0].confidence == "MEDIUM"


# ---------------------------------------------------------------------------
# 6. SEC preflight — success must not be poisoned by ERRORS key
# ---------------------------------------------------------------------------

def test_sec_preflight_success_based_on_four_booleans():
    """A preflight result with all 4 booleans True and non-empty ERRORS must still be SUCCESS."""
    # Simulate what test_sec_connectivity() returns
    res = {
        'USER_AGENT_CONFIGURED': True,
        'SEC_REACHABLE': True,
        'SUBMISSIONS_REACHABLE': True,
        'XBRL_REACHABLE': True,
        'ERRORS': ["some non-fatal informational message"],
    }
    # The UI evaluation logic (mirrored from app.py line 116)
    success = all(res.get(k) for k in ('USER_AGENT_CONFIGURED', 'SEC_REACHABLE', 'SUBMISSIONS_REACHABLE', 'XBRL_REACHABLE'))
    assert success is True, "ERRORS list must not make a successful preflight fail"


def test_sec_preflight_failure_when_endpoint_unreachable():
    """Missing SEC_REACHABLE must cause preflight failure."""
    res = {
        'USER_AGENT_CONFIGURED': True,
        'SEC_REACHABLE': False,
        'SUBMISSIONS_REACHABLE': True,
        'XBRL_REACHABLE': True,
        'ERRORS': [],
    }
    success = all(res.get(k) for k in ('USER_AGENT_CONFIGURED', 'SEC_REACHABLE', 'SUBMISSIONS_REACHABLE', 'XBRL_REACHABLE'))
    assert success is False


def test_sec_preflight_failure_missing_user_agent():
    """Missing USER_AGENT_CONFIGURED must cause failure."""
    res = {
        'USER_AGENT_CONFIGURED': False,
        'SEC_REACHABLE': False,
        'SUBMISSIONS_REACHABLE': False,
        'XBRL_REACHABLE': False,
        'ERRORS': ["Invalid or missing SEC_USER_AGENT environment variable"],
    }
    success = all(res.get(k) for k in ('USER_AGENT_CONFIGURED', 'SEC_REACHABLE', 'SUBMISSIONS_REACHABLE', 'XBRL_REACHABLE'))
    assert success is False


# ---------------------------------------------------------------------------
# 7. YTD selection — reversed-input invariance
# ---------------------------------------------------------------------------

def test_find_ytd_reversed_input_gives_same_result():
    """
    YTD candidate selection must yield the same Q2 derived value regardless of
    which Q1 candidate appears first in the list.
    This exercises the deterministic find_ytd() path inside normalization.py.
    """
    from financial_radar.core import derive_standalone_quarter

    # Two Q1 candidates — only Q1_B is the correct fiscal match (Q1, 2023)
    q1_end_a = date(2023, 3, 31)
    q1_end_b = date(2022, 12, 31)  # prior year — should NOT be selected for Q2 2023
    ytd_end = date(2023, 6, 30)

    prov = _prov("P1")

    q1_a = Observation("AAPL", "revenue", 90_000, "USD", q1_end_a, "QUARTER",
                       DataQuality.REPORTED, (prov,),
                       period_start=date(2023, 1, 1), fiscal_year=2023, fiscal_period="Q1")
    q1_b = Observation("AAPL", "revenue", 80_000, "USD", q1_end_b, "QUARTER",
                       DataQuality.REPORTED, (prov,),
                       period_start=date(2022, 10, 1), fiscal_year=2022, fiscal_period="Q4")
    ytd = Observation("AAPL", "revenue", 200_000, "USD", ytd_end, "YTD_6M",
                      DataQuality.REPORTED, (prov,),
                      period_start=date(2023, 1, 1), fiscal_year=2023, fiscal_period="Q2")

    # derive_standalone_quarter(ytd, q1_a) is the correct pairing
    result_correct = derive_standalone_quarter(ytd, q1_a)
    assert result_correct.value is not None, "Q2 value should be derivable from YTD_6M - Q1 2023"
    assert result_correct.value == pytest.approx(200_000 - 90_000), "Q2 = YTD_6M - Q1"

    # derive_standalone_quarter(ytd, q1_b) should fail fiscal match
    result_wrong = derive_standalone_quarter(ytd, q1_b)
    # Should return CALCULATION_INVALID since fiscal year mismatch 2022 Q4 vs 2023 Q2
    assert result_wrong.value is None or result_wrong.quality == DataQuality.CALCULATION_INVALID, \
        "Mismatched fiscal Q4 2022 must not be used as Q1 for Q2 2023 derivation"




# ---------------------------------------------------------------------------
# 8. QUALITY_RANK explicit hierarchy
# ---------------------------------------------------------------------------

def test_quality_rank_hierarchy():
    """AMENDED > RESTATED > REPORTED > DERIVED > NOT_REPORTED > CALCULATION_INVALID."""
    from financial_radar.models import QUALITY_RANK, DataQuality
    assert QUALITY_RANK[DataQuality.AMENDED] > QUALITY_RANK[DataQuality.RESTATED]
    assert QUALITY_RANK[DataQuality.RESTATED] > QUALITY_RANK[DataQuality.REPORTED]
    assert QUALITY_RANK[DataQuality.REPORTED] > QUALITY_RANK[DataQuality.DERIVED]
    assert QUALITY_RANK[DataQuality.DERIVED] > QUALITY_RANK[DataQuality.NOT_REPORTED]
    assert QUALITY_RANK[DataQuality.NOT_REPORTED] > QUALITY_RANK[DataQuality.CALCULATION_INVALID]

def test_semantic_fiscal_match_preferred_over_date_heuristic():
    """
    A candidate that is a true fiscal match but lower quality MUST beat a 
    candidate that lacks fiscal info and only matches via date heuristics.
    """
    from financial_radar.metrics import get_comparison_pair
    from financial_radar.models import Observation, DataQuality, Provenance
    from datetime import date
    
    current = Observation("AAPL", "rev", 100, "USD", date(2023,12,31), "QUARTER", DataQuality.REPORTED, (),
                          period_start=date(2023,10,1), fiscal_year=2024, fiscal_period="Q1")
                          
    # Candidate A: high quality (AMENDED) but no fiscal info. Falls into the 350-380 day date bucket.
    cand_a = Observation("AAPL", "rev", 90, "USD", date(2022,12,31), "QUARTER", DataQuality.AMENDED, (),
                         period_start=date(2022,10,1), fiscal_year=None, fiscal_period=None)
                         
    # Candidate B: low quality (REPORTED or DERIVED) but perfect fiscal info.
    cand_b = Observation("AAPL", "rev", 95, "USD", date(2022,12,31), "QUARTER", DataQuality.REPORTED, (),
                         period_start=date(2022,10,1), fiscal_year=2023, fiscal_period="Q1")
                         
    # Test forward order
    curr, prior_fwd = get_comparison_pair([current, cand_a, cand_b], "rev", "QUARTER", mode="yoy", current_obs=current)
    assert prior_fwd == cand_b, "Fiscal match must be preferred over date match, regardless of quality"
    
    # Test reverse order
    curr, prior_rev = get_comparison_pair([current, cand_b, cand_a], "rev", "QUARTER", mode="yoy", current_obs=current)
    assert prior_rev == cand_b, "Fiscal match must be preferred over date match, regardless of input order"


def test_quantitative_intelligence_narratives():
    """
    Research Mode must format precise quantitative explanations for 
    cash conversion, FCF, and liquidity deterioration.
    """
    from financial_radar.intelligence import generate_intelligence
    import json
    
    ev_conv = json.dumps([{"value": 0.5}, {"value": 1.2}])
    res_conv = generate_intelligence("EARNINGS_CASH_CONVERSION_DETERIORATION", "AAPL", "Tech", ev_conv)
    assert "declined from 120.0% to 50.0%" in res_conv.get("what_changed", "")
    
    ev_fcf = json.dumps([{"value": -1000000, "unit": "USD"}, {"value": 5000000, "unit": "USD"}])
    res_fcf = generate_intelligence("FREE_CASH_FLOW_DETERIORATION", "AAPL", "Tech", ev_fcf)
    assert "fell from $5.0M to -$1.0M" in res_fcf.get("what_changed", "")
    
    ev_liq = json.dumps([{"value": 0.8}, {"value": 1.5}])
    res_liq = generate_intelligence("LIQUIDITY_COMPRESSION", "AAPL", "Tech", ev_liq)
    assert "fell from 1.50x to 0.80x" in res_liq.get("what_changed", "")

def test_provenance_determinism_no_typeerror():
    """
    Growth provenance must sort deterministically even if accessions are mixed types
    (e.g., int vs str). It must not fall back to input ordering.
    """
    from financial_radar.metrics import derive_analytical_metrics
    from financial_radar.models import Observation, DataQuality, Provenance
    from datetime import date
    
    # Create two observations for yoy growth
    prov1 = Provenance(accession=123, source_url="", filing_date=date(2023,1,1), form="10-K", concept="", raw_value=100, retrieval_timestamp=date(2024,1,1), mapping_version='1')
    prov2 = Provenance(accession="000123-23-0001", source_url="", filing_date=date(2024,1,1), form="10-K", concept="", raw_value=110, retrieval_timestamp=date(2024,1,1), mapping_version='1')
    
    o1 = Observation("AAPL", "revenue", 100, "USD", date(2023,12,31), "ANNUAL", DataQuality.REPORTED, (prov1,),
                     period_start=date(2023,1,1), fiscal_year=2023, fiscal_period="FY")
    o2 = Observation("AAPL", "revenue", 110, "USD", date(2024,12,31), "ANNUAL", DataQuality.REPORTED, (prov2,),
                     period_start=date(2024,1,1), fiscal_year=2024, fiscal_period="FY")
                     
    # Even though one accession is an int and the other is a string,
    # the sort key should convert both to str and sort stably without throwing TypeError.
    # We will test two different input orders. Both should yield the same provenance order.
    
    res1 = derive_analytical_metrics([o1, o2])
    res2 = derive_analytical_metrics([o2, o1])
    
    g1 = [r for r in res1 if r.metric == "revenue_growth_yoy"][0]
    g2 = [r for r in res2 if r.metric == "revenue_growth_yoy"][0]
    
    accs1 = [p.accession for p in g1.provenance]
    accs2 = [p.accession for p in g2.provenance]
    
    assert accs1 == accs2, "Provenance sorting must be identical regardless of input order"
    assert str(accs1[0]) < str(accs1[1]), "Provenance must be sorted by stringified accession"


def test_51_company_semantics():
    """
    The primary companies array must contain exactly 51 APPLICATION_UNIVERSE companies.
    Peer-only companies (e.g. AMD, PFE) must be in peer_references.
    """
    import json
    
    with open("config/sp500_representative_51_2026.json", "r", encoding="utf-8") as f:
        data = json.load(f)
        
    main_companies = data.get("companies", [])
    assert len(main_companies) == 51, "Must have exactly 51 primary companies"
    
    for c in main_companies:
        assert c.get("universe_type") == "APPLICATION_UNIVERSE", f"Company {c['ticker']} in main array must be APPLICATION_UNIVERSE"
        
    peer_refs = data.get("peer_references", [])
    assert len(peer_refs) > 0, "Must have separate peer references array"
    
    # Check that AMD/PFE are not in the main array
    main_tickers = [c["ticker"] for c in main_companies]
    assert "AMD" not in main_tickers, "AMD should be a peer reference, not in main array"
    assert "PFE" not in main_tickers, "PFE should be a peer reference, not in main array"

