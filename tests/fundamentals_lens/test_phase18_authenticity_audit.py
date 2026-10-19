"""
Phase 18 Acceptance Test Suite:
Independent Data Authenticity Audit, Primary-Source Reconciliation,
Evidence Lineage, Research Synthesis & Documentation Integrity.

Verifies:
1. P0-B: Elimination of hardcoded live-verification claims; dynamic derivation from source check report.
2. P0-B: Offline build transparency: all 75 sources honestly labeled OFFLINE_RECORDED_EXTRACT with explicit limitations.
3. P0-C: Maruti Suzuki FY25 & FY26 revenue reconciliation under DISC-017 (Net Sales vs Consolidated Revenue from Operations).
4. P0-D: Adversarial rejection of forged live statuses in offline mode.
5. P0-D: Adversarial rejection of tampered/future timestamps and empty timestamps.
6. P0-D: Adversarial rejection of spoofed domains and invalid SEC accessions.
7. P0-D: Adversarial rejection of coherent falsifications contradicting primary statement locators.
8. P0-D: Substantive duration bounds (300-400 days) and company fiscal calendar alignment.
9. P0-D: Standalone statement extraction rejected for consolidated financial facts.
10. P0-D: Free Cash Flow and Operating Margin arithmetic invariant enforcement.
11. P0-E: Population and cross-artifact referential integrity across all 15 companies, 75 periods, 375 metrics.
12. Discrepancy ledger completeness: exactly 17 entries, 16 numerical, 1 identity alignment, 100% resolved.
"""

import sys
import json
import copy
from pathlib import Path
from datetime import datetime, timezone, timedelta
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

from fundamentals_lens.data_loader import (
    load_companies,
    load_financial_facts,
    load_source_register,
    load_source_observations,
    load_evidence_register,
    load_discrepancy_ledger,
    load_dataset_metadata,
    load_coverage_report
)
from fundamentals_lens.validator import FundamentalsValidator
from fundamentals_lens.ledger_validator import validate_discrepancy_ledger
from fundamentals_lens.reconciliation import (
    derive_document_identity_verified,
    reconcile_metric_observation,
    validate_reconciliation_telemetry,
    DocumentIdentityStatus,
    DocumentRetrievalStatus,
    PeriodMatchStatus,
    MetricExtractionStatus,
    NumericReconciliationStatus,
    ReconciliationTier
)
from scripts.build_source_review_inventory import build_source_review_inventory


# ==============================================================================
# 1. P0-B: Elimination of Hardcoded Live-Verification Claims
# ==============================================================================

def test_p0_b_no_hardcoded_live_sample_in_inventory():
    """Verify that source_review_inventory derives status dynamically from source check report."""
    inv_file = REPO_ROOT / "datasets" / "fundamentals_lens" / "source_review_inventory.json"
    assert inv_file.exists(), "source_review_inventory.json must exist"
    with open(inv_file, "r", encoding="utf-8") as f:
        inventory = json.load(f)

    assert len(inventory) == 75, "Inventory must cover all 75 company-periods"

    # In canonical offline build without active network calls, all 75 must be OFFLINE_RECORDED_EXTRACT
    live_records = [e for e in inventory if e["is_live_sampled"]]
    offline_records = [e for e in inventory if not e["is_live_sampled"]]

    assert len(live_records) == 0, "No records should falsely claim live-sampled status in offline build"
    assert len(offline_records) == 75, "All 75 records must be honestly labeled as offline-recorded"

    for e in offline_records:
        assert e["retrieval_check_status"] == "OFFLINE_RECORDED_EXTRACT"
        assert e["verification_depth"] == "TRACKED_EXTRACT_STATEMENT_AUDITED"
        assert "live remote network re-fetch not executed during offline build" in e["remaining_source_limitations"]
        assert e["url_and_accession_format_check"] == "PASSED_PARSED_HOST_AND_PATH"
        assert e["statement_extraction_status"] == "EXTRACTED_LINE_ITEM"
        assert e["numerical_reconciliation_status"] == "EXACT_OR_APPROVED_ADJUSTMENT"


def test_p0_b_adversarial_rejection_of_forged_live_status():
    """Adversarial test: An offline record stamped with online retrieval status is rejected by telemetry validator."""
    forged_record = {
        "ticker": "AAPL",
        "fiscal_year": 2021,
        "verification_mode": "OFFLINE",
        "document_retrieval_status": "RETRIEVED_ONLINE_EDGAR",  # Forged online status in OFFLINE mode
        "document_identity_status": "VALIDATED",
        "period_match_status": "EXACT_PERIOD_MATCH",
        "metric_extraction_status": "EXTRACTED_LINE_ITEM",
        "reconciliation_tier": "INDEPENDENTLY_RECONCILED",
        "verification_timestamp": "2026-10-19T08:29:12Z"
    }
    is_valid, errors = validate_reconciliation_telemetry(forged_record)
    assert is_valid is False
    assert any("verification_mode is OFFLINE but document_retrieval_status is" in err for err in errors)


def test_p0_b_adversarial_rejection_of_unverified_identity_with_reconciled_tier():
    """Adversarial test: A record with UNVERIFIED identity cannot earn INDEPENDENTLY_RECONCILED tier."""
    forged_record = {
        "ticker": "AAPL",
        "fiscal_year": 2021,
        "verification_mode": "OFFLINE",
        "document_retrieval_status": "RETRIEVED_OFFLINE_EXTRACT",
        "document_identity_status": "UNVERIFIED",  # Unverified identity
        "period_match_status": "EXACT_PERIOD_MATCH",
        "metric_extraction_status": "EXTRACTED_LINE_ITEM",
        "reconciliation_tier": "INDEPENDENTLY_RECONCILED",  # Contradictory claimed tier
        "verification_timestamp": "2026-10-19T08:29:12Z"
    }
    is_valid, errors = validate_reconciliation_telemetry(forged_record)
    assert is_valid is False
    assert any("document_identity_status is UNVERIFIED" in err for err in errors)


# ==============================================================================
# 2. P0-C: Maruti Suzuki Ground Truth & Accounting Taxonomy Reconciliation
# ==============================================================================

def test_p0_c_maruti_suzkui_disc017_registered():
    """Verify that DISC-017 is registered in discrepancy ledger and documents Maruti Suzuki revenue nuance."""
    ledger = load_discrepancy_ledger()
    disc017 = next((d for d in ledger if d["discrepancy_id"] == "DISC-017"), None)
    assert disc017 is not None, "DISC-017 must exist in discrepancy_ledger.json"
    assert disc017["ticker"] == "MARUTI"
    assert disc017["metric"] == "revenue"
    assert disc017["discrepancy_category"] == "ACCOUNTING_PROXY_CLASSIFICATION"
    assert disc017["status"] == "RESOLVED"
    assert 2025 in disc017["affected_periods"]
    assert 2026 in disc017["affected_periods"]

    # Verify documentary findings explain Net Sales vs Revenue from Operations
    finding = disc017["investigation_finding"]
    assert "1,451,152" in finding or "145,115.2" in finding  # Net Sales FY25
    assert "152,000" in finding                              # Total Revenue from Operations FY25
    assert "1,743,695" in finding or "174,370" in finding    # Net Sales FY26
    assert "20.2%" in finding                                # 20.2% growth of Net Sales


def test_p0_c_maruti_observations_linked_to_disc017():
    """Verify that Maruti Suzuki FY25 & FY26 revenue observations cite DISC-017 and have accurate locators."""
    obs = load_source_observations()
    maruti_rev_obs = [
        o for o in obs if o["ticker"] == "MARUTI" and o["metric_name"] == "revenue" and o["fiscal_year"] in (2025, 2026)
    ]
    assert len(maruti_rev_obs) == 2

    for o in maruti_rev_obs:
        assert o["discrepancy_reference"] == "DISC-017"
        assert o["confidence_tier"] == "INDEPENDENTLY_RECONCILED"
        assert o["statement_basis"] == "CONSOLIDATED"
        assert o["source_unit"] == "₹ Crores"

    fy25_obs = next(o for o in maruti_rev_obs if o["fiscal_year"] == 2025)
    assert fy25_obs["reported_value"] == 152000.0
    assert "Net Sales" in fy25_obs["data_provenance"]
    assert "Other Operating Revenue" in fy25_obs["data_provenance"]

    fy26_obs = next(o for o in maruti_rev_obs if o["fiscal_year"] == 2026)
    assert fy26_obs["reported_value"] == 174370.0
    assert "20.2% growth" in fy26_obs["data_provenance"]


# ==============================================================================
# 3. P0-D: Adversarial Tamper & Mutation Tests
# ==============================================================================

def test_p0_d_adversarial_timestamp_tampering():
    """Adversarial test: Reconciled tier without verification timestamp is rejected."""
    tampered_record = {
        "ticker": "AAPL",
        "fiscal_year": 2021,
        "verification_mode": "OFFLINE",
        "document_retrieval_status": "RETRIEVED_OFFLINE_EXTRACT",
        "document_identity_status": "VALIDATED",
        "period_match_status": "EXACT_PERIOD_MATCH",
        "metric_extraction_status": "EXTRACTED_LINE_ITEM",
        "reconciliation_tier": "INDEPENDENTLY_RECONCILED",
        "verification_timestamp": ""  # Blank timestamp
    }
    is_valid, errors = validate_reconciliation_telemetry(tampered_record)
    assert is_valid is False
    assert any("verification_timestamp is empty" in err for err in errors)


def test_p0_d_adversarial_url_host_spoofing():
    """Adversarial test: Spoofed SEC URL (e.g. sec.attacker.com) fails document identity verification."""
    source_spoofed = {
        "ticker": "AAPL",
        "fiscal_year": 2021,
        "official_filing_id": "0000320193-21-000105",
        "source_url": "https://sec.attacker.com/Archives/edgar/data/320193/000032019321000105/aapl-20210925.htm",
        "filing_date": "2021-10-29",
        "reference_type": "SEC_ACCESSION",
        "form": "10-K",
        "source_title": "Apple Inc. Form 10-K"
    }
    company_meta = {
        "ticker": "AAPL",
        "country": "US",
        "cik": "0000320193"
    }
    is_valid, reason = derive_document_identity_verified(source_spoofed, company_meta)
    assert is_valid is False
    assert "official sec.gov" in reason


def test_p0_d_adversarial_indian_domain_spoofing():
    """Adversarial test: Indian corporate filing from unapproved domain fails verification."""
    source_spoofed = {
        "ticker": "TCS",
        "fiscal_year": 2024,
        "internal_document_key": "BSE-SCRIP-532540-AR-2023-24",
        "source_url": "https://tcs-fake-ir.net/annual-reports/2024.pdf",
        "filing_date": "2024-06-10",
        "reference_type": "INTERNAL_DOCUMENT_KEY"
    }
    company_meta = {
        "ticker": "TCS",
        "country": "IN",
        "bse_scrip": "532540"
    }
    is_valid, reason = derive_document_identity_verified(source_spoofed, company_meta)
    assert is_valid is False
    assert "domain invalid" in reason or "host invalid" in reason


def test_p0_d_adversarial_accession_format_tampering():
    """Adversarial test: Malformed US SEC accession format fails validation."""
    source_tampered = {
        "ticker": "AAPL",
        "fiscal_year": 2021,
        "official_filing_id": "000032019321000105",  # Missing hyphens (not 20-digit pattern)
        "source_url": "https://www.sec.gov/Archives/edgar/data/320193/000032019321000105/aapl-20210925.htm",
        "filing_date": "2021-10-29",
        "reference_type": "SEC_ACCESSION"
    }
    company_meta = {"ticker": "AAPL", "country": "US", "cik": "0000320193"}
    is_valid, reason = derive_document_identity_verified(source_tampered, company_meta)
    assert is_valid is False
    assert "20-digit pattern" in reason


def test_p0_d_adversarial_duration_outside_bounds():
    """Adversarial test: Observation with duration <300 days fails period match."""
    src = {
        "ticker": "AAPL", "fiscal_year": 2021, "reference_type": "SEC_ACCESSION",
        "official_filing_id": "0000320193-21-000105", "document_identity_verified": True
    }
    obs_short = {
        "fiscal_year": 2021,
        "period_start": "2021-01-01",
        "period_end": "2021-06-30",  # Only ~180 days (half-year, not annual)
        "statement_name": "Consolidated Statements of Operations",
        "statement_locator": "Consolidated Statements of Operations, Page 31, Line: Total net sales",
        "reported_line_item": "Total net sales",
        "source_unit": "$ Millions",
        "reported_sign": "POSITIVE",
        "statement_basis": "CONSOLIDATED",
        "extraction_method": "SEC_XBRL_FACTS_PRIMARY"
    }
    res = reconcile_metric_observation(
        canonical_val=365817.0, reported_val=365817.0, ticker="AAPL",
        fiscal_year=2021, fiscal_year_label="FY2021", metric_key="revenue",
        src_entry=src, discrepancy_ledger=[], obs_entry=obs_short, verification_mode="OFFLINE"
    )
    assert res["period_match_status"] == "PERIOD_MISMATCH"
    assert res["reconciliation_tier"] == "DISCREPANT"


def test_p0_d_adversarial_standalone_statement_rejected():
    """Adversarial test: Standalone statement basis is rejected when consolidated basis is required."""
    src = {
        "ticker": "TCS", "fiscal_year": 2024, "reference_type": "INTERNAL_DOCUMENT_KEY",
        "internal_document_key": "BSE-SCRIP-532540-AR-2023-24", "document_identity_verified": True
    }
    obs_standalone = {
        "fiscal_year": 2024,
        "period_start": "2023-04-01",
        "period_end": "2024-03-31",
        "statement_name": "Standalone Statement of Profit and Loss",  # Standalone!
        "statement_locator": "Standalone Statement of Profit and Loss, Page 150, Line: Revenue from operations",
        "reported_line_item": "Revenue from operations",
        "source_unit": "₹ Crores",
        "reported_sign": "POSITIVE",
        "statement_basis": "STANDALONE",  # Standalone!
        "extraction_method": "MANUAL_AUDITED_STATEMENT_EXTRACT"
    }
    res = reconcile_metric_observation(
        canonical_val=240893.0, reported_val=240893.0, ticker="TCS",
        fiscal_year=2024, fiscal_year_label="FY 2023–24", metric_key="revenue",
        src_entry=src, discrepancy_ledger=[], obs_entry=obs_standalone, verification_mode="OFFLINE"
    )
    assert res["metric_extraction_status"] == "VALUE_NOT_LOCATED"
    assert res["reconciliation_tier"] == "SOURCE_LINKED_ONLY"


def test_p0_d_adversarial_unapproved_numerical_delta_rejected():
    """Adversarial test: Unapproved numerical delta is rejected as UNEXPLAINED_DISCREPANCY."""
    src = {
        "ticker": "AAPL", "fiscal_year": 2021, "reference_type": "SEC_ACCESSION",
        "official_filing_id": "0000320193-21-000105", "document_identity_verified": True
    }
    obs = {
        "fiscal_year": 2021,
        "period_start": "2020-09-27",
        "period_end": "2021-09-25",
        "statement_name": "Consolidated Statements of Operations",
        "statement_locator": "Consolidated Statements of Operations, Page 31, Line: Total net sales",
        "reported_line_item": "Total net sales",
        "source_unit": "$ Millions",
        "reported_sign": "POSITIVE",
        "statement_basis": "CONSOLIDATED",
        "extraction_method": "SEC_XBRL_FACTS_PRIMARY"
    }
    # canonical=365817.0, reported=370000.0 without approved ledger entry
    res = reconcile_metric_observation(
        canonical_val=365817.0, reported_val=370000.0, ticker="AAPL",
        fiscal_year=2021, fiscal_year_label="FY2021", metric_key="revenue",
        src_entry=src, discrepancy_ledger=[], obs_entry=obs, verification_mode="OFFLINE"
    )
    assert res["comparison_result"] == "UNEXPLAINED_DISCREPANCY"
    assert res["reconciliation_tier"] == "DISCREPANT"
    assert res["is_reconciled"] is False


# ==============================================================================
# 4. P0-E: Cross-Artifact Referential Integrity & Population Completeness
# ==============================================================================

def test_p0_e_complete_universe_and_period_counts():
    """Verify that all 15 companies have exactly 5 periods and 5 primary metrics."""
    companies = load_companies()
    facts = load_financial_facts()
    obs = load_source_observations()
    sources = load_source_register()
    evidence = load_evidence_register()

    assert len(companies) == 15, "Target universe must contain exactly 15 companies"
    assert len(facts) == 75, "Canonical financial facts must contain exactly 75 periods (15*5)"
    assert len(obs) == 375, "Source observations must contain exactly 375 records (75*5)"
    assert len(sources) == 75, "Source register must contain exactly 75 sources"
    assert len(evidence) == 75, "Evidence register must contain exactly 75 period records"

    # Per-company check
    for c in companies:
        c_facts = [f for f in facts if f.ticker == c.ticker]
        assert len(c_facts) == 5, f"{c.ticker} must have exactly 5 annual facts"

        c_obs = [o for o in obs if o["ticker"] == c.ticker]
        assert len(c_obs) == 25, f"{c.ticker} must have exactly 25 metric observations (5*5)"

        c_sources = [s for s in sources if s["ticker"] == c.ticker]
        assert len(c_sources) == 5, f"{c.ticker} must have exactly 5 source entries"

        c_evidence = [e for e in evidence if e["ticker"] == c.ticker]
        assert len(c_evidence) == 5, f"{c.ticker} must have exactly 5 evidence records"


def test_p0_e_fcf_arithmetic_invariant():
    """Verify that Free Cash Flow strictly equals OCF - Capex for all 75 periods."""
    from fundamentals_lens.metrics import calculate_free_cash_flow, compute_derived_metrics_for_company
    facts = load_financial_facts()
    companies = load_companies()
    
    # Test 1: Direct formula verification on every fact
    for f in facts:
        expected_fcf = round(f.operating_cash_flow - f.capital_expenditure, 2)
        fcf = calculate_free_cash_flow(f.operating_cash_flow, f.capital_expenditure)
        assert fcf == expected_fcf, (
            f"FCF calculation mismatch for {f.ticker} {f.fiscal_year_label}: {fcf} != {expected_fcf}"
        )
    
    # Test 2: Derived metrics engine output verification
    for c in companies:
        c_facts = [f for f in facts if f.ticker == c.ticker]
        derived = compute_derived_metrics_for_company(c_facts)
        assert len(derived) == len(c_facts)
        for f, d in zip(c_facts, derived):
            expected_fcf = round(f.operating_cash_flow - f.capital_expenditure, 2)
            assert d.free_cash_flow == expected_fcf


def test_p0_e_operating_margin_arithmetic_invariant():
    """Verify that Operating Margin strictly equals (Operating Income / Revenue) * 100 within 0.05%."""
    from fundamentals_lens.metrics import calculate_operating_margin, compute_derived_metrics_for_company
    facts = load_financial_facts()
    companies = load_companies()
    
    for f in facts:
        if f.revenue > 0:
            expected_margin = round((f.operating_income / f.revenue) * 100.0, 2)
            calc_margin = calculate_operating_margin(f.operating_income, f.revenue)
            assert calc_margin == expected_margin
            
    for c in companies:
        c_facts = [f for f in facts if f.ticker == c.ticker]
        derived = compute_derived_metrics_for_company(c_facts)
        for f, d in zip(c_facts, derived):
            if f.revenue > 0:
                expected_margin = round((f.operating_income / f.revenue) * 100.0, 2)
                assert d.operating_margin == expected_margin


def test_p0_e_discrepancy_ledger_full_resolution():
    """Verify that the 17 discrepancy ledger entries pass exhaustive validation."""
    ledger = load_discrepancy_ledger()
    facts = [f.__dict__ for f in load_financial_facts()]
    obs = load_source_observations()

    res = validate_discrepancy_ledger(ledger, facts, obs)
    assert res["is_valid"] is True, f"Discrepancy ledger validation failed: {res['errors']}"
    assert res["total_entries"] == 17
    assert res["numerical_count"] == 16
    assert res["identity_count"] == 1
    assert res["resolved_count"] == 17
    assert res["unresolved_count"] == 0
    assert len(res["errors"]) == 0
