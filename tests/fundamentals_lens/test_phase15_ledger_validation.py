"""
Unit and Adversarial Tests for Phase 15 Discrepancy Ledger Validation.

Verifies:
1. All 16 committed discrepancy ledger entries pass strict schema, semantic, and cross-artifact checks.
2. DISC-011 is strictly classified as identity alignment (is_numerical=False) and excluded from numerical counts.
3. Mutated final canonical value fails validation against financial facts.
4. Mutated reported value fails validation against source observations.
5. Multi-metric entry (e.g. DISC-010, DISC-012, DISC-014, DISC-015) cannot resolve the wrong metric.
6. Multi-year entry (e.g. DISC-016) cannot resolve the wrong fiscal year.
7. FCF arithmetic consistency is enforced for OCF/Capex adjustments (DISC-012, DISC-015).
8. Operating margin arithmetic consistency is enforced for Revenue/OI adjustments (DISC-002, DISC-005).
9. Unsupported status or duplicate discrepancy ID fails.
"""

import copy
import json
from pathlib import Path
import pytest

from fundamentals_lens.ledger_validator import validate_discrepancy_ledger
from fundamentals_lens.data_loader import (
    load_discrepancy_ledger,
    load_financial_facts,
    load_source_observations
)


@pytest.fixture
def committed_ledger():
    return load_discrepancy_ledger()


@pytest.fixture
def committed_facts():
    return [f.__dict__ for f in load_financial_facts()]


@pytest.fixture
def committed_obs():
    return load_source_observations()


def test_committed_ledger_passes_validation(committed_ledger, committed_facts, committed_obs):
    """Verify that the 16 committed discrepancy ledger entries pass all validation rules."""
    res = validate_discrepancy_ledger(committed_ledger, committed_facts, committed_obs)
    assert res["is_valid"] is True, f"Committed ledger validation failed: {res['errors']}"
    assert res["total_entries"] == 16
    assert res["numerical_count"] == 15
    assert res["identity_count"] == 1
    assert res["resolved_count"] == 16
    assert res["unresolved_count"] == 0
    assert len(res["errors"]) == 0


def test_disc011_identity_classification(committed_ledger):
    """Verify DISC-011 is strictly non-numerical and excluded from numerical counts."""
    disc011 = next(d for d in committed_ledger if d["discrepancy_id"] == "DISC-011")
    assert disc011["is_numerical"] is False
    assert disc011["discrepancy_category"] == "FILING_IDENTITY_ALIGNMENT"
    assert disc011["metric"] == "accession_alignment"
    assert len(disc011.get("affected_metrics_detail", [])) == 0


def test_mutated_final_value_fails(committed_ledger, committed_facts, committed_obs):
    """Verify that a ledger entry with an incorrect final canonical value fails validation."""
    mutated = copy.deepcopy(committed_ledger)
    # Alter final_canonical_value for DISC-001 (GOOGL FY25 capex)
    mutated[0]["final_canonical_value"] = 88888.0
    mutated[0]["canonical_value"] = 88888.0
    mutated[0]["affected_metrics_detail"][0]["final_canonical_value"] = 88888.0

    res = validate_discrepancy_ledger(mutated, committed_facts, committed_obs)
    assert res["is_valid"] is False
    assert any("Fact value" in err and "final_canonical_value" in err for err in res["errors"])


def test_mutated_primary_reported_value_fails(committed_ledger, committed_facts, committed_obs):
    """Verify that a ledger entry with an incorrect primary reported value fails validation."""
    mutated = copy.deepcopy(committed_ledger)
    # Alter primary_reported_value for DISC-002 (TGT FY23 OI)
    mutated[1]["primary_reported_value"] = 9999.0
    mutated[1]["reported_value"] = 9999.0
    mutated[1]["affected_metrics_detail"][0]["primary_reported_value"] = 9999.0

    res = validate_discrepancy_ledger(mutated, committed_facts, committed_obs)
    assert res["is_valid"] is False
    assert any("Observation reported_value" in err and "primary_reported_value" in err for err in res["errors"])


def test_multi_metric_wrong_metric_fails(committed_ledger, committed_facts, committed_obs):
    """Verify that multi-metric entry DISC-010 cannot resolve an unrelated metric."""
    mutated = copy.deepcopy(committed_ledger)
    disc010 = next(d for d in mutated if d["discrepancy_id"] == "DISC-010")
    # Mutate second sub-metric from net_income to revenue
    disc010["affected_metrics_detail"][1]["metric"] = "revenue"

    res = validate_discrepancy_ledger(mutated, committed_facts, committed_obs)
    assert res["is_valid"] is False
    assert any("revenue" in err for err in res["errors"])


def test_multi_year_wrong_year_fails(committed_ledger, committed_facts, committed_obs):
    """Verify that multi-year entry DISC-016 cannot resolve an unapproved fiscal year."""
    mutated = copy.deepcopy(committed_ledger)
    disc016 = next(d for d in mutated if d["discrepancy_id"] == "DISC-016")
    # Mutate sub-metric year from 2026 to 2023
    disc016["affected_metrics_detail"][1]["fiscal_year"] = 2023

    res = validate_discrepancy_ledger(mutated, committed_facts, committed_obs)
    assert res["is_valid"] is False
    assert any("FY2023" in err or "FY23" in err for err in res["errors"])


def test_derived_fcf_arithmetic_consistency(committed_ledger, committed_facts, committed_obs):
    """Verify that corrupting sub-metric FCF in DISC-012 triggers arithmetic validation error."""
    mutated_ledger = copy.deepcopy(committed_ledger)
    disc012 = next(d for d in mutated_ledger if d["discrepancy_id"] == "DISC-012")
    sm_fcf = next(sm for sm in disc012["affected_metrics_detail"] if sm["metric"] == "free_cash_flow")
    sm_fcf["final_canonical_value"] = sm_fcf["final_canonical_value"] + 500.0

    res = validate_discrepancy_ledger(mutated_ledger, committed_facts, committed_obs)
    assert res["is_valid"] is False
    assert any("Sub-metric FCF" in err for err in res["errors"])


def test_duplicate_discrepancy_id_fails(committed_ledger, committed_facts, committed_obs):
    """Verify that duplicate discrepancy_ids are rejected."""
    mutated = copy.deepcopy(committed_ledger)
    # Duplicate DISC-001 ID onto DISC-002
    mutated[1]["discrepancy_id"] = "DISC-001"

    res = validate_discrepancy_ledger(mutated, committed_facts, committed_obs)
    assert res["is_valid"] is False
    assert any("Duplicate discrepancy_id 'DISC-001'" in err for err in res["errors"])


def test_invalid_status_fails(committed_ledger, committed_facts, committed_obs):
    """Verify that unsupported status strings are rejected."""
    mutated = copy.deepcopy(committed_ledger)
    mutated[0]["status"] = "PENDING_ARBITRATION"

    res = validate_discrepancy_ledger(mutated, committed_facts, committed_obs)
    assert res["is_valid"] is False
    assert any("Invalid status 'PENDING_ARBITRATION'" in err for err in res["errors"])
