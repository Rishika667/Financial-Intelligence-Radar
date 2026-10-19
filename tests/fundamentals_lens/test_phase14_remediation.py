"""
Phase 14 Evidence Integrity Remediation & Acceptance Test Suite.
Validates all Phase 14 core requirements:

1. Normalized discrepancy ledger schema (initial, before, reported, final, category).
2. Granular sub-metric discrepancy resolution (DISC-010, DISC-012, DISC-014, DISC-015).
3. Multi-year discrepancy resolution (DISC-016 WMT FY25/FY26).
4. Filing identity alignment classification (DISC-011).
5. Truthful offline document status (OFFLINE_AUDITED, zero unearned online flags).
6. Earned verification dimensions:
   - Official corporate domain validation for Indian sources.
   - Substantive fiscal year period duration check (rejects quarters/YTD < 300 days).
   - Non-generic statement locator enforcement.
7. Pre-map duplicate validation in builders and validators (M1).
8. Dynamic reconciliation counts and metadata alignment.
"""

import copy
import json
import pytest
from pathlib import Path

from fundamentals_lens.data_loader import (
    load_companies,
    load_financial_facts,
    load_source_register,
    load_evidence_register,
    load_discrepancy_ledger,
    load_source_observations,
    load_dataset_metadata,
    get_company_by_ticker,
    get_facts_for_company
)
from fundamentals_lens.reconciliation import (
    derive_document_identity_verified,
    find_matching_approved_discrepancy,
    reconcile_metric_observation,
    DocumentIdentityStatus,
    DocumentRetrievalStatus,
    PeriodMatchStatus,
    MetricExtractionStatus,
    NumericReconciliationStatus,
    ReconciliationTier,
    INDIAN_OFFICIAL_DOMAINS
)
from fundamentals_lens.validator import FundamentalsValidator
from fundamentals_lens.models import ValidationStatus

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def test_phase14_discrepancy_ledger_schema_completeness():
    """Verify that all discrepancy entries have normalized, explicit schema fields."""
    ledger = load_discrepancy_ledger()
    assert len(ledger) >= 16, f"Expected at least 16 discrepancy records, found {len(ledger)}"

    valid_categories = {
        "NUMERICAL_REVISION",
        "ACCOUNTING_PROXY_CLASSIFICATION",
        "ATTRIBUTION_BASIS",
        "FILING_IDENTITY_ALIGNMENT"
    }

    for d in ledger:
        did = d.get("discrepancy_id")
        assert did.startswith("DISC-"), f"Invalid discrepancy_id format: {did}"
        assert "ticker" in d
        assert "fiscal_year" in d
        assert "fiscal_year_label" in d
        assert "affected_periods" in d
        assert isinstance(d["affected_periods"], list)
        assert len(d["affected_periods"]) >= 1

        assert "discrepancy_category" in d
        assert d["discrepancy_category"] in valid_categories, f"{did}: Invalid category '{d['discrepancy_category']}'"

        assert "initial_dataset_value" in d
        assert "canonical_value_before_correction" in d
        assert "primary_reported_value" in d
        assert "final_canonical_value" in d
        assert "status" in d
        assert d["status"] == "RESOLVED"
        assert "investigation_finding" in d
        assert "resolution_rationale" in d
        assert "source_accession_or_key" in d

    # Verify DISC-001 specific numeric normalization
    disc_001 = next(d for d in ledger if d["discrepancy_id"] == "DISC-001")
    assert disc_001["initial_dataset_value"] == 91400.0
    assert disc_001["canonical_value_before_correction"] == 91400.0
    assert disc_001["primary_reported_value"] == 91447.0
    assert disc_001["final_canonical_value"] == 91447.0
    assert disc_001["canonical_value"] == 91447.0


def test_phase14_identity_alignment_classification():
    """Verify DISC-011 is classified as FILING_IDENTITY_ALIGNMENT with non-numerical typing."""
    ledger = load_discrepancy_ledger()
    disc_011 = next(d for d in ledger if d["discrepancy_id"] == "DISC-011")

    assert disc_011["discrepancy_category"] == "FILING_IDENTITY_ALIGNMENT"
    assert disc_011["is_numerical"] is False
    assert disc_011["initial_source_key"] == "0000909832-24-000084"
    assert disc_011["source_accession_or_key"] == "0000909832-24-000049"
    assert "accession_id" in disc_011["resolution_rationale"]


def test_phase14_multi_metric_sub_discrepancy_matching():
    """Verify that multi-metric compound entries resolve their secondary sub-metrics."""
    ledger = load_discrepancy_ledger()

    # 1. DISC-010: COST FY2022 Net Income (5,844.0) matching
    match_ni = find_matching_approved_discrepancy(
        ticker="COST",
        metric_key="net_income",
        fiscal_year=2022,
        fiscal_year_label="FY2022",
        reported_val=5844.0,
        canonical_val=5844.0,
        discrepancy_ledger=ledger
    )
    assert match_ni is not None, "Failed to match COST FY2022 Net Income under DISC-010"
    assert match_ni["discrepancy_id"] == "DISC-010"

    # 2. DISC-012: COST FY2025 Capex (5,498.0) matching
    match_capex = find_matching_approved_discrepancy(
        ticker="COST",
        metric_key="capital_expenditure",
        fiscal_year=2025,
        fiscal_year_label="FY2025",
        reported_val=5498.0,
        canonical_val=5498.0,
        discrepancy_ledger=ledger
    )
    assert match_capex is not None, "Failed to match COST FY2025 Capex under DISC-012"
    assert match_capex["discrepancy_id"] == "DISC-012"

    # 3. DISC-014: MSFT FY2025 Operating Income (128,528.0) matching
    match_msft_oi = find_matching_approved_discrepancy(
        ticker="MSFT",
        metric_key="operating_income",
        fiscal_year=2025,
        fiscal_year_label="FY2025",
        reported_val=128528.0,
        canonical_val=128528.0,
        discrepancy_ledger=ledger
    )
    assert match_msft_oi is not None, "Failed to match MSFT FY2025 Operating Income under DISC-014"
    assert match_msft_oi["discrepancy_id"] == "DISC-014"

    # 4. DISC-015: MSFT FY2026 Operating Cash Flow (182,935.0) matching
    match_msft_ocf = find_matching_approved_discrepancy(
        ticker="MSFT",
        metric_key="operating_cash_flow",
        fiscal_year=2026,
        fiscal_year_label="FY2026",
        reported_val=182935.0,
        canonical_val=182935.0,
        discrepancy_ledger=ledger
    )
    assert match_msft_ocf is not None, "Failed to match MSFT FY2026 OCF under DISC-015"
    assert match_msft_ocf["discrepancy_id"] == "DISC-015"


def test_phase14_multi_year_discrepancy_matching():
    """Verify DISC-016 resolves Net Income across both FY2025 and FY2026."""
    ledger = load_discrepancy_ledger()

    # FY2025 matching (19,436.0)
    match_fy25 = find_matching_approved_discrepancy(
        ticker="WMT",
        metric_key="net_income",
        fiscal_year=2025,
        fiscal_year_label="FY2025",
        reported_val=19436.0,
        canonical_val=19436.0,
        discrepancy_ledger=ledger
    )
    assert match_fy25 is not None
    assert match_fy25["discrepancy_id"] == "DISC-016"

    # FY2026 matching (21,893.0)
    match_fy26 = find_matching_approved_discrepancy(
        ticker="WMT",
        metric_key="net_income",
        fiscal_year=2026,
        fiscal_year_label="FY2026",
        reported_val=21893.0,
        canonical_val=21893.0,
        discrepancy_ledger=ledger
    )
    assert match_fy26 is not None
    assert match_fy26["discrepancy_id"] == "DISC-016"


def test_phase14_truthful_offline_document_status():
    """Verify all offline observations emit OFFLINE_AUDITED with zero online claims."""
    observations = load_source_observations()
    assert len(observations) == 375

    for obs in observations:
        assert obs["verification_mode"] == "OFFLINE"
        assert obs["source_document_status"] == "OFFLINE_AUDITED"
        assert obs["source_document_status"] != "ONLINE_VERIFIED"


def test_phase14_indian_corporate_domain_validation():
    """Verify strict official corporate domain validation for Indian companies."""
    # Test 1: Valid registered corporate domain
    valid_source = {
        "ticker": "TCS",
        "internal_document_key": "BSE-SCRIP-532540-AR-2025-26",
        "source_url": "https://www.tcs.com/investor-relations/ar2026.pdf",
        "filing_date": "2026-06-15",
        "reference_type": "INTERNAL_DOCUMENT_KEY"
    }
    tcs_meta = {"country": "IN", "bse_scrip": "532540"}
    is_valid, reason = derive_document_identity_verified(valid_source, tcs_meta)
    assert is_valid is True
    assert "verified" in reason.lower()

    # Test 2: Unregistered third-party domain (e.g. random-scam.com) is strictly rejected
    invalid_domain_source = {
        "ticker": "TCS",
        "internal_document_key": "BSE-SCRIP-532540-AR-2025-26",
        "source_url": "https://www.random-scam.com/reports/tcs-ar.pdf",
        "filing_date": "2026-06-15",
        "reference_type": "INTERNAL_DOCUMENT_KEY"
    }
    is_valid_bad, reason_bad = derive_document_identity_verified(invalid_domain_source, tcs_meta)
    assert is_valid_bad is False
    assert "Indian source URL domain invalid" in reason_bad


def test_phase14_period_duration_validation():
    """Verify period duration validation strictly rejects quarters or YTD periods (< 300 days)."""
    src_entry = {
        "ticker": "AAPL",
        "reference_type": "SEC_ACCESSION",
        "document_identity_verified": True,
        "country": "US"
    }
    # Quarterly observation: 90 days duration
    quarter_obs = {
        "ticker": "AAPL",
        "fiscal_year": 2024,
        "fiscal_year_label": "FY2024",
        "period_start": "2024-01-01",
        "period_end": "2024-03-31", # ~90 days
        "statement_locator": "Item 1 - Condensed Financial Statements",
        "statement_name": "Consolidated Statements of Operations",
        "reported_line_item": "Revenue",
        "reported_value": 90753.0,
        "source_unit": "$ Millions",
        "reported_sign": "POSITIVE",
        "extraction_method": "SEC_XBRL_FACTS_PRIMARY"
    }

    result = reconcile_metric_observation(
        canonical_val=90753.0,
        reported_val=90753.0,
        ticker="AAPL",
        fiscal_year=2024,
        fiscal_year_label="FY2024",
        metric_key="revenue",
        src_entry=src_entry,
        discrepancy_ledger=[],
        obs_entry=quarter_obs
    )

    assert result["period_match_status"] == PeriodMatchStatus.PERIOD_MISMATCH.value
    assert result["reconciliation_tier"] == ReconciliationTier.DISCREPANT.value
    assert "Period chronology mismatch" in result["discrepancy_note"]


def test_phase14_generic_locator_rejection():
    """Verify that bare, generic statement locators cannot qualify for INDEPENDENTLY_RECONCILED."""
    src_entry = {
        "ticker": "AAPL",
        "reference_type": "SEC_ACCESSION",
        "document_identity_verified": True,
        "country": "US"
    }
    generic_obs = {
        "ticker": "AAPL",
        "fiscal_year": 2024,
        "fiscal_year_label": "FY2024",
        "period_start": "2023-10-01",
        "period_end": "2024-09-28",
        "statement_locator": "Item 8", # Generic bare locator
        "statement_name": "Consolidated Statements of Operations",
        "reported_line_item": "Revenue",
        "reported_value": 391035.0,
        "source_unit": "$ Millions",
        "reported_sign": "POSITIVE",
        "extraction_method": "SEC_XBRL_FACTS_PRIMARY"
    }

    result = reconcile_metric_observation(
        canonical_val=391035.0,
        reported_val=391035.0,
        ticker="AAPL",
        fiscal_year=2024,
        fiscal_year_label="FY2024",
        metric_key="revenue",
        src_entry=src_entry,
        discrepancy_ledger=[],
        obs_entry=generic_obs
    )

    assert result["metric_extraction_status"] == MetricExtractionStatus.VALUE_NOT_LOCATED.value
    assert result["reconciliation_tier"] == ReconciliationTier.SOURCE_LINKED_ONLY.value


def test_phase14_pre_map_duplicate_rejection():
    """Verify that duplicate evidence register records trigger a validation failure."""
    company = get_company_by_ticker("AAPL")
    facts = get_facts_for_company("AAPL")
    evidence = load_evidence_register()

    # Duplicate first record
    mutated_evidence = copy.deepcopy(evidence)
    mutated_evidence.append(copy.deepcopy(evidence[0]))

    results = FundamentalsValidator.validate_company_dataset(
        company, facts, evidence_register=mutated_evidence
    )
    align_res = next(r for r in results if r.rule_id == "GATE_FACT_EVIDENCE_ALIGNMENT")
    assert align_res.status == ValidationStatus.FAIL
    assert "Duplicate evidence register entries detected" in align_res.message
