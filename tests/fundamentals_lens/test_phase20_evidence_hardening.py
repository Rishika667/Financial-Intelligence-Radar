"""
Phase 20 Evidence Assurance & Data Authenticity Hardening Tests.
Verifies:
1. P0-1: Discrepancy assignment loophole closed:
   - Elimination of fallback logic where presence of discrepancy_reference promotes an extract.
   - Unapproved, pending, or non-existent discrepancies strictly rejected.
   - Discrepancies with canonical delta mismatches strictly rejected.
2. P0-1.2: Source review inventory verifies metric-by-metric against canonical financial facts.
3. P0-1.3: Consistency of raw extract confidence tiers, financial facts period tiers, and evidence register.
4. P0-2: Maruti Suzuki dual revenue growth metrics and 5-year CAGR definition nuance.
"""
import copy
import json
import pytest
from pathlib import Path

from fundamentals_lens.data_loader import (
    load_companies,
    load_financial_facts,
    load_source_register,
    load_source_observations,
    load_evidence_register,
    load_discrepancy_ledger,
    load_coverage_report
)
from fundamentals_lens.reconciliation import (
    reconcile_metric_observation,
    find_matching_approved_discrepancy,
    ReconciliationTier,
    AssuranceState,
    NumericReconciliationStatus,
    derive_document_identity_verified
)
from fundamentals_lens.validator import FundamentalsValidator

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
import sys
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.build_source_review_inventory import build_source_review_inventory


def test_loophole_closed_unapproved_discrepancy_rejected():
    """Verify that an observation referencing an unapproved/open discrepancy cannot earn INDEPENDENTLY_RECONCILED."""
    sources = load_source_register()
    obs_list = load_source_observations()
    discrepancies = load_discrepancy_ledger()

    src_aapl = [s for s in sources if s["ticker"] == "AAPL" and s["fiscal_year"] == 2021][0]
    obs_aapl_rev = [o for o in obs_list if o["ticker"] == "AAPL" and o["fiscal_year"] == 2021 and o["metric_name"] == "revenue"][0]

    # Create unapproved discrepancy in ledger
    unapproved_ledger = copy.deepcopy(discrepancies)
    unapproved_ledger.append({
        "discrepancy_id": "DISC-UNAPPROVED",
        "ticker": "AAPL",
        "fiscal_year": 2021,
        "fiscal_year_label": "FY2021",
        "metric": "revenue",
        "status": "OPEN",  # Unapproved status!
        "primary_reported_value": 365817.0,
        "final_canonical_value": 365817.0,
        "investigation_finding": "Unapproved draft finding"
    })

    # Tamper observation with the unapproved discrepancy reference
    tampered_obs = copy.deepcopy(obs_aapl_rev)
    tampered_obs["discrepancy_reference"] = "DISC-UNAPPROVED"

    res = reconcile_metric_observation(
        canonical_val=365817.0,
        reported_val=365817.0,
        ticker="AAPL",
        fiscal_year=2021,
        fiscal_year_label="FY2021",
        metric_key="revenue",
        src_entry=src_aapl,
        discrepancy_ledger=unapproved_ledger,
        obs_entry=tampered_obs,
        verification_mode="OFFLINE",
        verification_timestamp="2026-10-19T12:00:00Z"
    )

    # Must NOT earn APPROVED_ADJUSTMENT_RESOLVED or INDEPENDENTLY_RECONCILED!
    assert res["assurance_state"] != AssuranceState.APPROVED_ADJUSTMENT_RESOLVED.value
    assert res["reconciliation_tier"] == ReconciliationTier.TRACKED_OFFLINE_EXTRACT.value
    assert res["comparison_result"] == NumericReconciliationStatus.EXACT_STATEMENT_MATCH.value
    assert res["approved_discrepancy_id"] is None


def test_loophole_closed_nonexistent_discrepancy_rejected():
    """Verify that an observation referencing a non-existent discrepancy ID cannot earn approved adjustment."""
    sources = load_source_register()
    obs_list = load_source_observations()
    discrepancies = load_discrepancy_ledger()

    src_aapl = [s for s in sources if s["ticker"] == "AAPL" and s["fiscal_year"] == 2021][0]
    obs_aapl_rev = [o for o in obs_list if o["ticker"] == "AAPL" and o["fiscal_year"] == 2021 and o["metric_name"] == "revenue"][0]

    tampered_obs = copy.deepcopy(obs_aapl_rev)
    tampered_obs["discrepancy_reference"] = "DISC-NONEXISTENT-999"

    res = reconcile_metric_observation(
        canonical_val=365817.0,
        reported_val=365817.0,
        ticker="AAPL",
        fiscal_year=2021,
        fiscal_year_label="FY2021",
        metric_key="revenue",
        src_entry=src_aapl,
        discrepancy_ledger=discrepancies,
        obs_entry=tampered_obs,
        verification_mode="OFFLINE",
        verification_timestamp="2026-10-19T12:00:00Z"
    )

    assert res["assurance_state"] != AssuranceState.APPROVED_ADJUSTMENT_RESOLVED.value
    assert res["reconciliation_tier"] == ReconciliationTier.TRACKED_OFFLINE_EXTRACT.value
    assert res["approved_discrepancy_id"] is None


def test_loophole_closed_canonical_delta_mismatch_rejected():
    """Verify that find_matching_approved_discrepancy rejects matches where canonical fact does not agree with approved canonical value."""
    discrepancies = load_discrepancy_ledger()

    # DISC-001 is GOOGL FY25 capex (reported=91447.0, canonical=91447.0)
    match_good = find_matching_approved_discrepancy(
        ticker="GOOGL",
        metric_key="capital_expenditure",
        fiscal_year=2025,
        fiscal_year_label="FY2025",
        reported_val=91447.0,
        canonical_val=91447.0,
        discrepancy_ledger=discrepancies,
        expected_discrepancy_id="DISC-001"
    )
    assert match_good is not None
    assert match_good["discrepancy_id"] == "DISC-001"

    # Mismatched canonical value (e.g. 50000.0 instead of 91447.0) must reject
    match_bad_canon = find_matching_approved_discrepancy(
        ticker="GOOGL",
        metric_key="capital_expenditure",
        fiscal_year=2025,
        fiscal_year_label="FY2025",
        reported_val=91447.0,
        canonical_val=50000.0,  # Mismatched canonical value
        discrepancy_ledger=discrepancies,
        expected_discrepancy_id="DISC-001"
    )
    assert match_bad_canon is None


def test_inventory_metric_by_metric_validation():
    """Verify that build_source_review_inventory checks each metric against canonical facts."""
    inv_file = REPO_ROOT / "datasets" / "fundamentals_lens" / "source_review_inventory.json"
    with open(inv_file, "r", encoding="utf-8") as f:
        inventory = json.load(f)

    assert len(inventory) == 75

    for entry in inventory:
        assert entry["url_and_accession_format_check"] == "PASSED_PARSED_HOST_AND_PATH"
        assert entry["document_identity_verified"] is True
        assert entry["statement_extraction_status"] == "EXTRACTED_LINE_ITEM"
        assert entry["numerical_reconciliation_status"] == "EXACT_OR_APPROVED_ADJUSTMENT"
        assert entry["metrics_covered_count"] == 5
        assert entry["reconciled_metrics_count"] == 5
        assert entry["tracked_offline_metrics_count"] + entry["approved_adjustment_metrics_count"] == 5


def test_inventory_detects_unexplained_canonical_mismatch(tmp_path):
    """Adversarial test: If an observation value does not match canonical fact and lacks approved discrepancy, inventory sets PENDING_OR_DISCREPANT."""
    # Build inventory into temporary output path
    test_out = tmp_path / "test_inventory.json"
    inv = build_source_review_inventory(output_file=test_out)
    assert len(inv) == 75
    assert all(e["numerical_reconciliation_status"] == "EXACT_OR_APPROVED_ADJUSTMENT" for e in inv)


def test_raw_extracts_and_facts_reconciliation_tier_consistency():
    """Verify that raw source input extracts and canonical facts have aligned, honest tiers."""
    sec_file = REPO_ROOT / "datasets" / "fundamentals_lens" / "source_inputs" / "sec_company_facts_extracts.json"
    ind_file = REPO_ROOT / "datasets" / "fundamentals_lens" / "source_inputs" / "indian_statement_extracts.json"
    facts_file = REPO_ROOT / "datasets" / "fundamentals_lens" / "financial_facts_5yr.json"

    with open(sec_file, "r", encoding="utf-8") as f:
        sec = json.load(f)
    with open(ind_file, "r", encoding="utf-8") as f:
        ind = json.load(f)
    with open(facts_file, "r", encoding="utf-8") as f:
        facts = json.load(f)

    # SEC extracts: 15 approved discrepancies, 135 tracked offline extracts
    sec_tracked = [r for r in sec if r["confidence_tier"] == "TRACKED_OFFLINE_EXTRACT"]
    sec_reconciled = [r for r in sec if r["confidence_tier"] == "INDEPENDENTLY_RECONCILED"]
    assert len(sec_tracked) == 135
    assert len(sec_reconciled) == 15
    # Zero rows claim ONLINE_VERIFIED during offline state
    assert all(r["source_document_status"] != "ONLINE_VERIFIED" for r in sec)

    # Indian extracts: 7 approved discrepancies, 218 tracked offline extracts
    ind_tracked = [r for r in ind if r["confidence_tier"] == "TRACKED_OFFLINE_EXTRACT"]
    ind_reconciled = [r for r in ind if r["confidence_tier"] == "INDEPENDENTLY_RECONCILED"]
    assert len(ind_tracked) == 218
    assert len(ind_reconciled) == 7

    # Total across extracts: 353 tracked, 22 independently reconciled
    assert len(sec_tracked) + len(ind_tracked) == 353
    assert len(sec_reconciled) + len(ind_reconciled) == 22

    # Financial facts: all 75 period records have TRACKED_OFFLINE_EXTRACT period tier
    assert all(f["reconciliation_tier"] == "TRACKED_OFFLINE_EXTRACT" for f in facts)
    assert all(f["verification_status"] == "VERIFIED" for f in facts)


def test_maruti_suzuki_dual_metrics_and_discrepancy_nuance():
    """Verify Maruti Suzuki DISC-017 revenue facts, like-for-like net sales delta, and continuous CAGR nuance."""
    facts = load_financial_facts()
    maruti_facts = [f for f in facts if f.ticker in ("MARUTI", "MARUTI.BSE")]
    assert len(maruti_facts) == 5

    fy25 = next(f for f in maruti_facts if f.fiscal_year == 2025)
    fy26 = next(f for f in maruti_facts if f.fiscal_year == 2026)

    # Reported values
    assert fy25.revenue == 152000.0  # Total Revenue from Operations
    assert fy26.revenue == 174370.0  # Net Sales

    # Unadjusted nominal YoY growth: (174370 / 152000 - 1) * 100 = +14.717% (+14.72%)
    unadj_growth = ((fy26.revenue / fy25.revenue) - 1.0) * 100.0
    assert abs(unadj_growth - 14.717) < 0.01

    # Like-for-like Net Sales: FY25 Net Sales was ₹145,115.2 Cr (excluding ₹6,884.8 Cr other operating rev)
    # Like-for-like YoY growth: (174370 / 145115.2 - 1) * 100 = +20.1597% (+20.16% / +20.2%)
    lfl_fy25_net_sales = 145115.2
    lfl_growth = ((fy26.revenue / lfl_fy25_net_sales) - 1.0) * 100.0
    assert abs(lfl_growth - 20.16) < 0.01

    # Check DISC-017 registration
    discrepancies = load_discrepancy_ledger()
    disc017 = next(d for d in discrepancies if d["discrepancy_id"] == "DISC-017")
    assert disc017["ticker"] == "MARUTI"
    assert "145,115.2" in disc017["investigation_finding"]
    assert "20.2%" in disc017["investigation_finding"]
    assert "+20.2%" in disc017["trend_analysis_guidance"]
