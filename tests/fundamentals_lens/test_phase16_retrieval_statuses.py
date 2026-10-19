"""
Phase 16 Priority P0-A Acceptance Test Suite:
Factually Accurate Retrieval & Multi-Dimensional Verification Statuses.

Tests:
1. Online retrieval success: receives RETRIEVED_ONLINE_EDGAR or RETRIEVED_ONLINE_BSE.
2. Online retrieval failure (e.g. HTTP 404/500/network error): receives FAILED status and demotes tier.
3. Online retrieval timeout: receives INCONCLUSIVE status and demotes tier.
4. Online retrieval never attempted: receives NOT_CHECKED status and demotes tier.
5. Offline rebuild: receives RETRIEVED_OFFLINE_EXTRACT / OFFLINE_AUDITED; never falsely claims online.
6. Malformed accession identifiers: rejected during document identity validation.
7. Host-spoofing attacks (attacker.com): strictly rejected.
8. Wrong-company document: mismatch between source and company rejected.
9. Wrong-period records: duration mismatch (<300 days) and fiscal calendar mismatch.
10. Contradictory telemetry combinations: rejected by validate_reconciliation_telemetry.
"""

import pytest
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


@pytest.fixture
def base_us_source():
    return {
        "ticker": "AAPL",
        "fiscal_year": 2021,
        "official_filing_id": "0000320193-21-000105",
        "source_url": "https://www.sec.gov/Archives/edgar/data/320193/000032019321000105/aapl-20210925.htm",
        "filing_date": "2021-10-29",
        "reference_type": "SEC_ACCESSION",
        "form": "10-K",
        "source_title": "Apple Inc. Form 10-K (FY 2021)",
        "document_identity_verified": True
    }


@pytest.fixture
def base_us_company():
    return {
        "ticker": "AAPL",
        "name": "Apple Inc.",
        "country": "US",
        "cik": "0000320193",
        "fiscal_year_end_month": "September"
    }


@pytest.fixture
def base_indian_source():
    return {
        "ticker": "TCS",
        "fiscal_year": 2024,
        "internal_document_key": "BSE-SCRIP-532540-AR-2023-24",
        "source_url": "https://www.tcs.com/investor-relations/financial-statements/annual-report-2024",
        "filing_date": "2024-06-10",
        "reference_type": "INTERNAL_DOCUMENT_KEY",
        "document_identity_verified": True
    }


@pytest.fixture
def base_indian_company():
    return {
        "ticker": "TCS",
        "name": "Tata Consultancy Services Limited",
        "country": "IN",
        "bse_scrip": "532540",
        "fiscal_year_end_month": "March"
    }


@pytest.fixture
def base_obs_entry():
    return {
        "ticker": "AAPL",
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


# ------------------------------------------------------------------------------
# 1. Online Retrieval Outcome Tests
# ------------------------------------------------------------------------------

def test_online_retrieval_success_receives_online_status(base_us_source, base_obs_entry, base_us_company):
    """Test that explicit successful online retrieval earns RETRIEVED_ONLINE_EDGAR and INDEPENDENTLY_RECONCILED."""
    res = reconcile_metric_observation(
        canonical_val=365817.0,
        reported_val=365817.0,
        ticker="AAPL",
        fiscal_year=2021,
        fiscal_year_label="FY2021",
        metric_key="revenue",
        src_entry=base_us_source,
        discrepancy_ledger=[],
        obs_entry=base_obs_entry,
        verification_mode="ONLINE",
        verification_timestamp="2026-10-19T10:00:00Z",
        company_meta=base_us_company,
        retrieval_outcome={"outcome": "SUCCESS", "http_status": 200, "retrieved_at": "2026-10-19T10:00:00Z"}
    )
    assert res["document_retrieval_status"] == DocumentRetrievalStatus.RETRIEVED_ONLINE_EDGAR.value
    assert res["reconciliation_tier"] == ReconciliationTier.INDEPENDENTLY_RECONCILED.value
    assert res["is_reconciled"] is True


def test_online_retrieval_failure_demotes_tier(base_us_source, base_obs_entry, base_us_company):
    """Test that a failed online retrieval receives FAILED and cannot earn INDEPENDENTLY_RECONCILED."""
    res = reconcile_metric_observation(
        canonical_val=365817.0,
        reported_val=365817.0,
        ticker="AAPL",
        fiscal_year=2021,
        fiscal_year_label="FY2021",
        metric_key="revenue",
        src_entry=base_us_source,
        discrepancy_ledger=[],
        obs_entry=base_obs_entry,
        verification_mode="ONLINE",
        verification_timestamp="2026-10-19T10:00:00Z",
        company_meta=base_us_company,
        retrieval_outcome={"outcome": "FAILED", "http_status": 404, "error": "Filing not found on EDGAR"}
    )
    assert res["document_retrieval_status"] == DocumentRetrievalStatus.FAILED.value
    assert res["reconciliation_tier"] == ReconciliationTier.SOURCE_LINKED_ONLY.value
    assert res["is_reconciled"] is False
    assert "cannot earn INDEPENDENTLY_RECONCILED" in res["discrepancy_note"]


def test_online_retrieval_timeout_receives_inconclusive(base_us_source, base_obs_entry, base_us_company):
    """Test that an online timeout receives INCONCLUSIVE and demotes tier."""
    res = reconcile_metric_observation(
        canonical_val=365817.0,
        reported_val=365817.0,
        ticker="AAPL",
        fiscal_year=2021,
        fiscal_year_label="FY2021",
        metric_key="revenue",
        src_entry=base_us_source,
        discrepancy_ledger=[],
        obs_entry=base_obs_entry,
        verification_mode="ONLINE",
        verification_timestamp="2026-10-19T10:00:00Z",
        company_meta=base_us_company,
        retrieval_outcome={"outcome": "TIMEOUT", "http_status": None, "error": "Gateway timeout (10s)"}
    )
    assert res["document_retrieval_status"] == DocumentRetrievalStatus.INCONCLUSIVE.value
    assert res["reconciliation_tier"] == ReconciliationTier.SOURCE_LINKED_ONLY.value
    assert res["is_reconciled"] is False


def test_online_mode_without_retrieval_outcome_is_not_checked(base_us_source, base_obs_entry, base_us_company):
    """Test that merely selecting verification_mode=ONLINE without recorded outcome results in NOT_CHECKED."""
    res = reconcile_metric_observation(
        canonical_val=365817.0,
        reported_val=365817.0,
        ticker="AAPL",
        fiscal_year=2021,
        fiscal_year_label="FY2021",
        metric_key="revenue",
        src_entry=base_us_source,
        discrepancy_ledger=[],
        obs_entry=base_obs_entry,
        verification_mode="ONLINE",
        verification_timestamp="2026-10-19T10:00:00Z",
        company_meta=base_us_company,
        retrieval_outcome=None  # Never attempted
    )
    assert res["document_retrieval_status"] == DocumentRetrievalStatus.NOT_CHECKED.value
    assert res["reconciliation_tier"] == ReconciliationTier.SOURCE_LINKED_ONLY.value
    assert res["is_reconciled"] is False


def test_offline_rebuild_emits_offline_status(base_us_source, base_obs_entry, base_us_company):
    """Test that offline rebuild truthfully emits OFFLINE retrieval status without claiming fresh online retrieval."""
    res = reconcile_metric_observation(
        canonical_val=365817.0,
        reported_val=365817.0,
        ticker="AAPL",
        fiscal_year=2021,
        fiscal_year_label="FY2021",
        metric_key="revenue",
        src_entry=base_us_source,
        discrepancy_ledger=[],
        obs_entry=base_obs_entry,
        verification_mode="OFFLINE",
        verification_timestamp="2026-10-18T21:16:44Z",
        company_meta=base_us_company
    )
    assert res["document_retrieval_status"] == DocumentRetrievalStatus.RETRIEVED_OFFLINE_EXTRACT.value
    assert res["verification_mode"] == "OFFLINE"
    assert res["reconciliation_tier"] == ReconciliationTier.TRACKED_OFFLINE_EXTRACT.value


# ------------------------------------------------------------------------------
# 2. Identity & Security Attack Guards
# ------------------------------------------------------------------------------

def test_malformed_accession_rejected(base_us_source, base_us_company):
    """Verify malformed accession format is rejected."""
    bad_source = dict(base_us_source)
    bad_source["official_filing_id"] = "123456789-invalid-acc"
    ok, reason = derive_document_identity_verified(bad_source, base_us_company)
    assert ok is False
    assert "does not match standard 20-digit pattern" in reason


def test_host_spoofing_rejected(base_us_source, base_us_company):
    """Verify host-spoofing URL is rejected."""
    bad_source = dict(base_us_source)
    bad_source["source_url"] = "https://evil.sec.gov.attacker.com/Archives/edgar/data/320193/000032019321000105/aapl.htm"
    ok, reason = derive_document_identity_verified(bad_source, base_us_company)
    assert ok is False
    assert "does not originate from official sec.gov" in reason


def test_wrong_company_document_rejected(base_us_source, base_indian_company):
    """Verify wrong company ticker mismatch is rejected."""
    ok, reason = derive_document_identity_verified(base_us_source, base_indian_company)
    assert ok is False
    assert "Document ticker mismatch" in reason


# ------------------------------------------------------------------------------
# 3. Fiscal Calendar & Period Mismatch Tests
# ------------------------------------------------------------------------------

def test_fiscal_calendar_mismatch_classified_as_period_mismatch(base_indian_source, base_indian_company):
    """Verify that an Indian company (ending in March) with a September period_end is marked PERIOD_MISMATCH."""
    sept_obs = {
        "ticker": "TCS",
        "fiscal_year": 2024,
        "period_start": "2023-10-01",
        "period_end": "2024-09-30", # September end (interim/half-year), duration=365 days
        "statement_name": "Consolidated Statement of Profit and Loss",
        "statement_locator": "Consolidated Statement of Profit and Loss, Page 170, Line: Revenue from operations",
        "reported_line_item": "Revenue from operations",
        "source_unit": "₹ Crores",
        "reported_sign": "POSITIVE",
        "statement_basis": "CONSOLIDATED",
        "extraction_method": "MANUAL_AUDITED_STATEMENT_EXTRACT"
    }

    res = reconcile_metric_observation(
        canonical_val=240893.0,
        reported_val=240893.0,
        ticker="TCS",
        fiscal_year=2024,
        fiscal_year_label="FY2024",
        metric_key="revenue",
        src_entry=base_indian_source,
        discrepancy_ledger=[],
        obs_entry=sept_obs,
        company_meta=base_indian_company
    )
    assert res["period_match_status"] == PeriodMatchStatus.PERIOD_MISMATCH.value
    assert res["reconciliation_tier"] == ReconciliationTier.DISCREPANT.value
    assert "Fiscal calendar mismatch" in res["discrepancy_note"]


# ------------------------------------------------------------------------------
# 4. Contradictory Telemetry Validation Tests
# ------------------------------------------------------------------------------

def test_validate_reconciliation_telemetry_detects_contradictions():
    """Verify validate_reconciliation_telemetry catches contradictory combinations."""
    # Contradiction: Offline mode claiming online retrieval
    bad_record = {
        "verification_mode": "OFFLINE",
        "document_retrieval_status": DocumentRetrievalStatus.RETRIEVED_ONLINE_EDGAR.value,
        "document_identity_status": DocumentIdentityStatus.VALIDATED.value,
        "period_match_status": PeriodMatchStatus.EXACT_PERIOD_MATCH.value,
        "metric_extraction_status": MetricExtractionStatus.EXTRACTED_LINE_ITEM.value,
        "reconciliation_tier": ReconciliationTier.INDEPENDENTLY_RECONCILED.value,
        "verification_timestamp": "2026-10-19T10:00:00Z"
    }
    is_valid, errors = validate_reconciliation_telemetry(bad_record)
    assert is_valid is False
    assert any("verification_mode is OFFLINE but document_retrieval_status" in e for e in errors)

    # Contradiction: Online failed retrieval claiming INDEPENDENTLY_RECONCILED
    bad_online = dict(bad_record)
    bad_online["verification_mode"] = "ONLINE"
    bad_online["document_retrieval_status"] = DocumentRetrievalStatus.FAILED.value
    bad_online["reconciliation_tier"] = ReconciliationTier.INDEPENDENTLY_RECONCILED.value
    is_valid_on, errors_on = validate_reconciliation_telemetry(bad_online)
    assert is_valid_on is False
    assert any("reconciliation_tier is INDEPENDENTLY_RECONCILED in ONLINE mode despite retrieval status 'FAILED'" in e for e in errors_on)
