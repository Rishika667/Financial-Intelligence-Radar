import json
import sqlite3
from datetime import date
import pytest

from financial_radar.intelligence import generate_intelligence, resolve_evidence_pair
from financial_radar.signals import divergence, gross_margin_compression, operating_margin_deterioration, cash_conversion
from financial_radar.models import Observation, DataQuality
from financial_radar.synthesis import synthesize_company
from financial_radar.store import DDL, save_observations


def test_divergence_metric_names_and_percentage_points():
    """
    Divergence explanations must state the specific metric (Receivables/revenue ratio or
    Inventory/sales ratio) and describe changes in percentage points, not generic labels.
    """
    # 1. Receivables / revenue divergence in generate_intelligence
    ev_rec = json.dumps([
        {"metric": "receivables_revenue_ratio", "value": 0.35, "unit": "pure", "period_end": "2023-12-31"},
        {"metric": "receivables_revenue_ratio", "value": 0.15, "unit": "pure", "period_end": "2022-12-31"},
    ])
    res_rec = generate_intelligence("RECEIVABLES_REVENUE_DIVERGENCE", "ACME", "Tech", ev_rec)
    what_rec = res_rec.get("what_changed", "")
    assert "Receivables/revenue ratio increased by 20.0 percentage points from 15.0% to 35.0%" in what_rec
    assert "Target ratio" not in what_rec
    assert "Target metric" not in what_rec

    # 2. Inventory / sales divergence in generate_intelligence
    ev_inv = json.dumps([
        {"metric": "inventory_sales_ratio", "value": 0.30, "unit": "pure", "period_end": "2023-12-31"},
        {"metric": "inventory_sales_ratio", "value": 0.10, "unit": "pure", "period_end": "2022-12-31"},
    ])
    res_inv = generate_intelligence("INVENTORY_SALES_DIVERGENCE", "ACME", "Tech", ev_inv)
    what_inv = res_inv.get("what_changed", "")
    assert "Inventory/sales ratio increased by 20.0 percentage points from 10.0% to 30.0%" in what_inv
    assert "Target ratio" not in what_inv
    assert "receivables" not in what_inv.lower()
    assert "receivables" not in res_inv.get("why_it_matters", "").lower()
    assert "receivables" not in res_inv.get("title", "").lower()

    # 3. Direct signals.divergence() explanation accuracy
    curr_rec_obs = Observation("ACME", "receivables_revenue_ratio", 0.40, "pure", date(2023, 12, 31), "QUARTER", DataQuality.REPORTED)
    prior_rec_obs = Observation("ACME", "receivables_revenue_ratio", 0.20, "pure", date(2022, 12, 31), "QUARTER", DataQuality.REPORTED)
    sig_rec = divergence("RECEIVABLES_REVENUE_DIVERGENCE", curr_rec_obs, prior_rec_obs)
    assert sig_rec is not None
    assert "Receivables/revenue ratio increased by 20.0 percentage points from 20.0% to 40.0%." in sig_rec.explanation

    curr_inv_obs = Observation("ACME", "inventory_sales_ratio", 0.45, "pure", date(2023, 12, 31), "QUARTER", DataQuality.REPORTED)
    prior_inv_obs = Observation("ACME", "inventory_sales_ratio", 0.25, "pure", date(2022, 12, 31), "QUARTER", DataQuality.REPORTED)
    sig_inv = divergence("INVENTORY_SALES_DIVERGENCE", curr_inv_obs, prior_inv_obs)
    assert sig_inv is not None
    assert "Inventory/sales ratio increased by 20.0 percentage points from 25.0% to 45.0%." in sig_inv.explanation
    assert "receivables" not in sig_inv.explanation.lower()


def test_cash_conversion_multiple_formatting():
    """
    Cash conversion must be formatted as multiples (e.g. 1.20x), not percentages (e.g. 120.0%).
    """
    # 1. generate_intelligence formatting
    ev_conv = json.dumps([
        {"metric": "cash_conversion", "value": 0.50, "unit": "multiple", "period_end": "2023-12-31"},
        {"metric": "cash_conversion", "value": 1.20, "unit": "multiple", "period_end": "2022-12-31"},
    ])
    res_conv = generate_intelligence("EARNINGS_CASH_CONVERSION_DETERIORATION", "ACME", "Tech", ev_conv)
    what = res_conv.get("what_changed", "")
    assert "Cash conversion declined from 1.20x to 0.50x" in what
    assert "120.0%" not in what
    assert "50.0%" not in what
    assert "operating cash flow divided by net income" in res_conv.get("why_it_matters", "")

    # 2. signals.cash_conversion formatting
    curr_conv_obs = Observation("ACME", "cash_conversion", 0.50, "multiple", date(2023, 12, 31), "QUARTER", DataQuality.REPORTED)
    prior_conv_obs = Observation("ACME", "cash_conversion", 1.20, "multiple", date(2022, 12, 31), "QUARTER", DataQuality.REPORTED)
    sig_conv = cash_conversion(curr_conv_obs, prior_conv_obs)
    assert sig_conv is not None
    assert "Cash conversion fell from 1.20x to 0.50x." in sig_conv.explanation
    assert "%" not in sig_conv.explanation


def test_evidence_temporal_ordering_independence():
    """
    Evidence ordering must be independent of list order.
    [current, prior] and [prior, current] must produce identical narratives and orderings.
    """
    curr = {"metric": "gross_margin", "value": 0.35, "unit": "pure", "period_end": "2023-12-31", "fiscal_year": 2023}
    prior = {"metric": "gross_margin", "value": 0.40, "unit": "pure", "period_end": "2022-12-31", "fiscal_year": 2022}

    # Direct resolution check
    c1, p1 = resolve_evidence_pair([curr, prior])
    c2, p2 = resolve_evidence_pair([prior, curr])
    assert c1["value"] == 0.35 and c1["period_end"] == "2023-12-31"
    assert p1["value"] == 0.40 and p1["period_end"] == "2022-12-31"
    assert c2["value"] == 0.35 and c2["period_end"] == "2023-12-31"
    assert p2["value"] == 0.40 and p2["period_end"] == "2022-12-31"

    # Narrative output check
    intel_forward = generate_intelligence("GROSS_MARGIN_COMPRESSION", "ACME", "Tech", json.dumps([curr, prior]))
    intel_reverse = generate_intelligence("GROSS_MARGIN_COMPRESSION", "ACME", "Tech", json.dumps([prior, curr]))

    assert intel_forward == intel_reverse
    assert "Gross margin declined from 40.0% to 35.0%, a 5.0 percentage-point decline." in intel_forward["what_changed"]


def test_non_deteriorating_expansion_no_false_deterioration_language():
    """
    When numbers indicate expansion or improvement, narratives must not claim deterioration or decline.
    """
    # 1. Gross margin expansion
    curr_gm = {"metric": "gross_margin", "value": 0.45, "unit": "pure", "period_end": "2023-12-31"}
    prior_gm = {"metric": "gross_margin", "value": 0.40, "unit": "pure", "period_end": "2022-12-31"}
    res_gm = generate_intelligence("GROSS_MARGIN_COMPRESSION", "ACME", "Tech", [curr_gm, prior_gm])
    assert "Gross margin increased from 40.0% to 45.0%, a 5.0 percentage-point expansion." in res_gm["what_changed"]
    assert "declined" not in res_gm["what_changed"]

    # 2. Cash conversion improvement
    curr_cc = {"metric": "cash_conversion", "value": 1.40, "unit": "multiple", "period_end": "2023-12-31"}
    prior_cc = {"metric": "cash_conversion", "value": 1.10, "unit": "multiple", "period_end": "2022-12-31"}
    res_cc = generate_intelligence("EARNINGS_CASH_CONVERSION_DETERIORATION", "ACME", "Tech", [curr_cc, prior_cc])
    assert "Cash conversion increased from 1.10x to 1.40x" in res_cc["what_changed"]
    assert "declined" not in res_cc["what_changed"]

    # 3. Liquidity ratio improvement
    curr_liq = {"metric": "liquidity_ratio", "value": 2.10, "unit": "multiple", "period_end": "2023-12-31"}
    prior_liq = {"metric": "liquidity_ratio", "value": 1.80, "unit": "multiple", "period_end": "2022-12-31"}
    res_liq = generate_intelligence("LIQUIDITY_COMPRESSION", "ACME", "Tech", [curr_liq, prior_liq])
    assert "Liquidity ratio rose from 1.80x to 2.10x" in res_liq["what_changed"]
    assert "fell" not in res_liq["what_changed"]


def test_synthesis_margin_uses_percentage_points():
    """
    synthesize_company must describe margin changes with 'percentage points', not generic 'points'.
    """
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.executescript(DDL)

    obs = [
        Observation("ACME", "gross_margin", 0.40, "pure", date(2023, 12, 31), "QUARTER", DataQuality.REPORTED, tuple(), tuple(), True, None, None, 2023, "Q4"),
        Observation("ACME", "gross_margin", 0.45, "pure", date(2022, 12, 31), "QUARTER", DataQuality.REPORTED, tuple(), tuple(), True, None, None, 2022, "Q4"),
        Observation("ACME", "operating_margin", 0.15, "pure", date(2023, 12, 31), "QUARTER", DataQuality.REPORTED, tuple(), tuple(), True, None, None, 2023, "Q4"),
        Observation("ACME", "operating_margin", 0.20, "pure", date(2022, 12, 31), "QUARTER", DataQuality.REPORTED, tuple(), tuple(), True, None, None, 2022, "Q4"),
    ]
    save_observations(c, obs)

    synth = synthesize_company("ACME", c)
    observed_text = " ".join(synth.get("observed", []))
    assert "Gross margin decreased 5.0 percentage points YoY" in observed_text
    assert "Operating margin decreased 5.0 percentage points YoY" in observed_text
    assert "points YoY" not in observed_text.replace("percentage points YoY", "")


def test_generate_intelligence_public_contract_and_structure():
    """
    generate_intelligence must fulfill the analytical contract:
    - Return dict with title, what_changed, why_it_matters, investigate
    - investigate must be a non-empty list of actionable checklist steps
    - why_it_matters must express screening hypotheses rather than definitive causation
    """
    signals = [
        "RECEIVABLES_REVENUE_DIVERGENCE",
        "INVENTORY_SALES_DIVERGENCE",
        "GROSS_MARGIN_COMPRESSION",
        "OPERATING_MARGIN_DETERIORATION",
        "EARNINGS_CASH_CONVERSION_DETERIORATION",
        "FREE_CASH_FLOW_DETERIORATION",
        "DEBT_OPERATING_INCOME_DETERIORATION",
        "LIQUIDITY_COMPRESSION",
        "SHARE_COUNT_DILUTION",
        "MULTI_FACTOR_DETERIORATION_CLUSTER",
    ]
    for s_id in signals:
        res = generate_intelligence(s_id, "TEST", "Industrial", "[]")
        assert isinstance(res, dict)
        for key in ("title", "what_changed", "why_it_matters", "investigate"):
            assert key in res, f"Key {key} missing from {s_id}"
        assert isinstance(res["investigate"], list)
        assert len(res["investigate"]) > 0
        # Hypotheses framing checks
        wim = res["why_it_matters"].lower()
        assert any(w in wim for w in ("screening", "review", "warrants", "starting point", "suggest")), (
            f"Signal {s_id} why_it_matters should be framed as screening/investigation: {res['why_it_matters']}"
        )
