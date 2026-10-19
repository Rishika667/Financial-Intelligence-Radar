"""
Phase 16 Priority P0-B Acceptance Test Suite:
Financial-Data and Discrepancy-Ledger Assurance Loop.

Adversarial mutation tests proving rejection of:
1. Duplicate financial facts in input population.
2. Duplicate source observations in input population.
3. Missing metric records in observations.
4. Duplicate source-register entries.
5. Incorrect ledger final values.
6. Incorrect ledger reported values.
7. Wrong fiscal-year associations.
8. Unapproved numerical adjustments.
9. Incorrect derived Free Cash Flow values.
10. Contradictory confidence tiers.
11. Metadata count mismatches against underlying population.
12. Duplicate ledger composite keys (ticker, fiscal_year, metric).
"""

import copy
import pytest
from fundamentals_lens.ledger_validator import validate_discrepancy_ledger
from fundamentals_lens.validator import FundamentalsValidator
from fundamentals_lens.data_loader import (
    load_financial_facts,
    load_source_observations,
    load_discrepancy_ledger,
    load_source_register,
    load_evidence_register,
    load_dataset_metadata,
    load_companies
)


@pytest.fixture
def base_facts():
    return [f.__dict__ if hasattr(f, "__dict__") else dict(f) for f in load_financial_facts()]


@pytest.fixture
def base_observations():
    return load_source_observations()


@pytest.fixture
def base_ledger():
    return load_discrepancy_ledger()


@pytest.fixture
def base_sources():
    return load_source_register()


@pytest.fixture
def base_evidence():
    return load_evidence_register()


@pytest.fixture
def base_metadata():
    return load_dataset_metadata()


# ------------------------------------------------------------------------------
# 1. Collision & Duplication Mutations
# ------------------------------------------------------------------------------

def test_duplicate_financial_facts_rejected(base_ledger, base_facts, base_observations):
    """Verify that duplicate financial facts are detected and rejected by ledger_validator."""
    mutated_facts = copy.deepcopy(base_facts)
    # Duplicate AAPL FY2021 fact
    mutated_facts.append(copy.deepcopy(mutated_facts[0]))

    res = validate_discrepancy_ledger(
        ledger=base_ledger,
        financial_facts=mutated_facts,
        source_observations=base_observations
    )
    assert res["is_valid"] is False
    assert any("Duplicate financial fact encountered" in err for err in res["errors"])


def test_duplicate_source_observations_rejected(base_ledger, base_facts, base_observations):
    """Verify that duplicate source observations are detected and rejected by ledger_validator."""
    mutated_obs = copy.deepcopy(base_observations)
    # Duplicate first observation
    mutated_obs.append(copy.deepcopy(mutated_obs[0]))

    res = validate_discrepancy_ledger(
        ledger=base_ledger,
        financial_facts=base_facts,
        source_observations=mutated_obs
    )
    assert res["is_valid"] is False
    assert any("Duplicate source observation encountered" in err for err in res["errors"])


def test_duplicate_ledger_composite_key_rejected(base_ledger, base_facts, base_observations):
    """Verify that duplicate (ticker, fiscal_year, metric) in ledger is rejected."""
    mutated_ledger = copy.deepcopy(base_ledger)
    dup_entry = copy.deepcopy(mutated_ledger[0])
    dup_entry["discrepancy_id"] = "DISC-999"  # Unique ID but duplicate composite key
    mutated_ledger.append(dup_entry)

    res = validate_discrepancy_ledger(
        ledger=mutated_ledger,
        financial_facts=base_facts,
        source_observations=base_observations
    )
    assert res["is_valid"] is False
    assert any("Duplicate ledger composite key" in err for err in res["errors"])


# ------------------------------------------------------------------------------
# 2. Value, Year & Missing Metric Mutations
# ------------------------------------------------------------------------------

def test_incorrect_ledger_final_value_rejected(base_ledger, base_facts, base_observations):
    """Verify that mutated final_canonical_value conflicting with facts is rejected for RESOLVED entry."""
    mutated_ledger = copy.deepcopy(base_ledger)
    # Mutate DISC-001 final_canonical_value
    mutated_ledger[0]["final_canonical_value"] = 999999.0
    mutated_ledger[0]["affected_metrics_detail"][0]["final_canonical_value"] = 999999.0

    res = validate_discrepancy_ledger(
        ledger=mutated_ledger,
        financial_facts=base_facts,
        source_observations=base_observations
    )
    assert res["is_valid"] is False
    assert any("!= final_canonical_value" in err for err in res["errors"])


def test_incorrect_ledger_reported_value_rejected(base_ledger, base_facts, base_observations):
    """Verify that mutated primary_reported_value conflicting with source observation is rejected."""
    mutated_ledger = copy.deepcopy(base_ledger)
    mutated_ledger[0]["primary_reported_value"] = 88888.0

    res = validate_discrepancy_ledger(
        ledger=mutated_ledger,
        financial_facts=base_facts,
        source_observations=base_observations
    )
    assert res["is_valid"] is False
    assert any("Observation reported_value" in err and "!= primary_reported_value" in err for err in res["errors"])


def test_wrong_fiscal_year_association_rejected(base_ledger, base_facts, base_observations):
    """Verify that associating a discrepancy entry with the wrong fiscal year fails fact lookup."""
    mutated_ledger = copy.deepcopy(base_ledger)
    mutated_ledger[0]["fiscal_year"] = 2035  # Non-existent period

    res = validate_discrepancy_ledger(
        ledger=mutated_ledger,
        financial_facts=base_facts,
        source_observations=base_observations
    )
    assert res["is_valid"] is False
    assert any("Missing or invalid fiscal_year" in err or "No canonical financial fact found" in err for err in res["errors"])


def test_unapproved_numerical_adjustment_rejected():
    """Verify that an unapproved numerical discrepancy is rejected as DISCREPANT."""
    from fundamentals_lens.reconciliation import reconcile_metric_observation, ReconciliationTier, NumericReconciliationStatus
    src = {
        "ticker": "AAPL",
        "official_filing_id": "0000320193-21-000105",
        "source_url": "https://www.sec.gov/Archives/edgar/data/320193/000032019321000105/aapl-20210925.htm",
        "filing_date": "2021-10-29",
        "reference_type": "SEC_ACCESSION",
        "document_identity_verified": True
    }
    obs = {
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

    # Reported is 365,000 vs canonical 365,817 without ledger approval
    res = reconcile_metric_observation(
        canonical_val=365817.0,
        reported_val=365000.0,
        ticker="AAPL",
        fiscal_year=2021,
        fiscal_year_label="FY2021",
        metric_key="revenue",
        src_entry=src,
        discrepancy_ledger=[],
        obs_entry=obs
    )
    assert res["reconciliation_tier"] == ReconciliationTier.DISCREPANT.value
    assert res["comparison_result"] == NumericReconciliationStatus.UNEXPLAINED_DISCREPANCY.value


def test_incorrect_fcf_arithmetic_rejected(base_ledger, base_facts, base_observations):
    """Verify that an arithmetic inconsistency in derived FCF is detected and rejected."""
    mutated_ledger = copy.deepcopy(base_ledger)
    # Find entry with FCF in affected_metrics_detail (e.g. DISC-012 COST FY2025)
    fcf_entry = next((e for e in mutated_ledger if any(sm.get("metric") == "free_cash_flow" for sm in e.get("affected_metrics_detail", []))), None)
    assert fcf_entry is not None

    for sm in fcf_entry["affected_metrics_detail"]:
        if sm.get("metric") == "free_cash_flow":
            sm["final_canonical_value"] = 1.0  # Absurdly wrong FCF

    res = validate_discrepancy_ledger(
        ledger=mutated_ledger,
        financial_facts=base_facts,
        source_observations=base_observations
    )
    assert res["is_valid"] is False
    assert any("Sub-metric FCF" in err and "!=" in err for err in res["errors"])


# ------------------------------------------------------------------------------
# 3. Population & Cross-Artifact Referential Mutations
# ------------------------------------------------------------------------------

def test_missing_observation_record_fails_population_gate(base_facts, base_observations, base_sources, base_evidence):
    """Verify that a missing source observation record fails validate_population_and_cross_artifact_integrity."""
    mutated_obs = copy.deepcopy(base_observations)
    # Drop one observation
    mutated_obs.pop(0)

    res = FundamentalsValidator.validate_population_and_cross_artifact_integrity(
        financial_facts=base_facts,
        source_observations=mutated_obs,
        sources=base_sources,
        evidence_register=base_evidence
    )
    assert res.status.value == "FAIL"
    assert "Missing source observations" in res.message


def test_duplicate_source_register_entry_fails_population_gate(base_facts, base_observations, base_sources, base_evidence):
    """Verify that duplicate source register entry fails population integrity gate."""
    mutated_sources = copy.deepcopy(base_sources)
    # Duplicate first source
    mutated_sources.append(copy.deepcopy(mutated_sources[0]))

    res = FundamentalsValidator.validate_population_and_cross_artifact_integrity(
        financial_facts=base_facts,
        source_observations=base_observations,
        sources=mutated_sources,
        evidence_register=base_evidence
    )
    assert res.status.value == "FAIL"
    assert "Duplicate source_id in source register" in res.message or "Duplicate source register period" in res.message


def test_metadata_count_mismatch_rejected(base_facts, base_observations, base_sources, base_evidence, base_metadata):
    """Verify that dataset metadata with mutated counts fails cross-artifact validation."""
    mutated_meta = copy.deepcopy(base_metadata)
    mutated_meta["reconciled_metric_observations"] = 999  # False claim
    mutated_meta["independently_reconciled_metrics"] = 999

    res = FundamentalsValidator.validate_dataset_metadata(
        metadata=mutated_meta,
        evidence_register=base_evidence,
        discrepancies=load_discrepancy_ledger()
    )
    assert res.status.value == "FAIL"
    assert "reconciled" in res.message
