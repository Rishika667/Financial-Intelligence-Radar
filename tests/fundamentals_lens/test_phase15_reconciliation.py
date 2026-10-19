"""
Unit and Adversarial Tests for Phase 15 Earned Confidence & Multi-Dimensional Verification.

Tests:
1. Parsed host & path validation: rejects host spoofing attacks and loose substring URLs.
2. Form 10-K enforcement on US filings.
3. Substantive duration boundaries (300 <= days <= 400, start < end).
4. Substantive metric extraction guards (rejects generic locators, missing units, non-consolidated basis).
5. Canonical numerical match without valid extraction cannot earn INDEPENDENTLY_RECONCILED.
6. Canonical numerical match without verified document identity cannot earn INDEPENDENTLY_RECONCILED.
7. Unapproved numerical delta is strictly classified as DISCREPANT.
"""

import pytest
from fundamentals_lens.reconciliation import (
    derive_document_identity_verified,
    reconcile_metric_observation,
    DocumentIdentityStatus,
    PeriodMatchStatus,
    MetricExtractionStatus,
    NumericReconciliationStatus,
    ReconciliationTier
)


@pytest.fixture
def valid_us_source():
    return {
        "ticker": "AAPL",
        "fiscal_year": 2021,
        "official_filing_id": "0000320193-21-000105",
        "source_url": "https://www.sec.gov/Archives/edgar/data/320193/000032019321000105/aapl-20210925.htm",
        "filing_date": "2021-10-29",
        "reference_type": "SEC_ACCESSION",
        "form": "10-K",
        "source_title": "Apple Inc. Form 10-K (FY 2021)"
    }


@pytest.fixture
def valid_us_company():
    return {
        "ticker": "AAPL",
        "country": "US",
        "cik": "0000320193"
    }


@pytest.fixture
def valid_indian_source():
    return {
        "ticker": "TCS",
        "fiscal_year": 2024,
        "internal_document_key": "BSE-SCRIP-532540-AR-2023-24",
        "source_url": "https://www.tcs.com/investor-relations/financial-statements/annual-report-2024",
        "filing_date": "2024-06-10",
        "reference_type": "INTERNAL_DOCUMENT_KEY"
    }


@pytest.fixture
def valid_indian_company():
    return {
        "ticker": "TCS",
        "country": "IN",
        "bse_scrip": "532540"
    }


@pytest.fixture
def valid_obs_entry():
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


def test_us_valid_document_identity(valid_us_source, valid_us_company):
    ok, reason = derive_document_identity_verified(valid_us_source, valid_us_company)
    assert ok is True
    assert "US SEC EDGAR" in reason


def test_us_host_spoofing_rejected(valid_us_source, valid_us_company):
    """Verify that attacker.com/sec.gov/Archives URL is rejected by parsed host check."""
    mutated = dict(valid_us_source)
    mutated["source_url"] = "https://attacker.com/www.sec.gov/Archives/edgar/data/320193/000032019321000105/aapl.htm"
    ok, reason = derive_document_identity_verified(mutated, valid_us_company)
    assert ok is False
    assert "host 'attacker.com' does not originate from official sec.gov" in reason


def test_us_wrong_form_rejected(valid_us_source, valid_us_company):
    """Verify that quarterly 10-Q filing is rejected for annual source identity."""
    mutated = dict(valid_us_source)
    mutated["form"] = "10-Q"
    ok, reason = derive_document_identity_verified(mutated, valid_us_company)
    assert ok is False
    assert "US annual filing form must be '10-K'" in reason


def test_indian_host_spoofing_rejected(valid_indian_source, valid_indian_company):
    """Verify that attacker.com?param=tcs.com URL is rejected by parsed host check."""
    mutated = dict(valid_indian_source)
    mutated["source_url"] = "https://attacker.com/download?fake=tcs.com"
    ok, reason = derive_document_identity_verified(mutated, valid_indian_company)
    assert ok is False
    assert "Indian source URL host invalid: 'attacker.com'" in reason


def test_period_duration_bounds(valid_us_source, valid_obs_entry):
    """Verify that period duration outside 300..400 days is classified as PERIOD_MISMATCH."""
    # Duration = 180 days (half year)
    short_obs = dict(valid_obs_entry)
    short_obs["period_start"] = "2021-01-01"
    short_obs["period_end"] = "2021-06-30"

    res = reconcile_metric_observation(
        ticker="AAPL",
        fiscal_year=2021,
        fiscal_year_label="FY2021",
        metric_key="revenue",
        src_entry={**valid_us_source, "document_identity_verified": True},
        discrepancy_ledger=[],
        obs_entry=short_obs,
        canonical_val=365817.0,
        reported_val=365817.0
    )
    assert res["comparison_result"] == NumericReconciliationStatus.UNEXPLAINED_DISCREPANCY.value
    assert res["reconciliation_tier"] == ReconciliationTier.DISCREPANT.value


def test_generic_locator_rejects_reconciled_tier(valid_us_source, valid_obs_entry):
    """Verify that bare generic locators like 'Item 8' demote observation to SOURCE_LINKED_ONLY."""
    bare_obs = dict(valid_obs_entry)
    bare_obs["statement_locator"] = "Item 8"

    res = reconcile_metric_observation(
        ticker="AAPL",
        fiscal_year=2021,
        fiscal_year_label="FY2021",
        metric_key="revenue",
        src_entry={**valid_us_source, "document_identity_verified": True},
        discrepancy_ledger=[],
        obs_entry=bare_obs,
        canonical_val=365817.0,
        reported_val=365817.0
    )
    assert res["comparison_result"] == NumericReconciliationStatus.NOT_RECONCILED.value
    assert res["reconciliation_tier"] == ReconciliationTier.SOURCE_LINKED_ONLY.value


def test_missing_unit_or_sign_demotes_tier(valid_us_source, valid_obs_entry):
    """Verify that missing source unit demotes observation to SOURCE_LINKED_ONLY."""
    no_unit_obs = dict(valid_obs_entry)
    no_unit_obs["source_unit"] = ""

    res = reconcile_metric_observation(
        ticker="AAPL",
        fiscal_year=2021,
        fiscal_year_label="FY2021",
        metric_key="revenue",
        src_entry={**valid_us_source, "document_identity_verified": True},
        discrepancy_ledger=[],
        obs_entry=no_unit_obs,
        canonical_val=365817.0,
        reported_val=365817.0
    )
    assert res["comparison_result"] == NumericReconciliationStatus.NOT_RECONCILED.value
    assert res["reconciliation_tier"] == ReconciliationTier.SOURCE_LINKED_ONLY.value


def test_standalone_basis_rejected(valid_us_source, valid_obs_entry):
    """Verify that STANDALONE basis is rejected for canonical consolidated metrics."""
    standalone_obs = dict(valid_obs_entry)
    standalone_obs["statement_basis"] = "STANDALONE"

    res = reconcile_metric_observation(
        ticker="AAPL",
        fiscal_year=2021,
        fiscal_year_label="FY2021",
        metric_key="revenue",
        src_entry={**valid_us_source, "document_identity_verified": True},
        discrepancy_ledger=[],
        obs_entry=standalone_obs,
        canonical_val=365817.0,
        reported_val=365817.0
    )
    assert res["reconciliation_tier"] == ReconciliationTier.SOURCE_LINKED_ONLY.value


def test_unverified_document_identity_cannot_reconcile(valid_us_source, valid_obs_entry):
    """Verify that unverified document identity strictly yields IDENTITY_UNVERIFIED and UNVERIFIED tier."""
    res = reconcile_metric_observation(
        ticker="AAPL",
        fiscal_year=2021,
        fiscal_year_label="FY2021",
        metric_key="revenue",
        src_entry={**valid_us_source, "document_identity_verified": False},
        discrepancy_ledger=[],
        obs_entry=valid_obs_entry,
        canonical_val=365817.0,
        reported_val=365817.0
    )
    assert res["comparison_result"] == NumericReconciliationStatus.IDENTITY_UNVERIFIED.value
    assert res["reconciliation_tier"] == ReconciliationTier.UNVERIFIED.value


def test_unapproved_numerical_delta_is_discrepant(valid_us_source, valid_obs_entry):
    """Verify that an unapproved numerical delta is strictly classified as DISCREPANT."""
    res = reconcile_metric_observation(
        ticker="AAPL",
        fiscal_year=2021,
        fiscal_year_label="FY2021",
        metric_key="revenue",
        src_entry={**valid_us_source, "document_identity_verified": True},
        discrepancy_ledger=[],
        obs_entry=valid_obs_entry,
        canonical_val=365817.0,
        reported_val=365800.0  # Unapproved 17 unit shift
    )
    assert res["comparison_result"] == NumericReconciliationStatus.UNEXPLAINED_DISCREPANCY.value
    assert res["reconciliation_tier"] == ReconciliationTier.DISCREPANT.value
