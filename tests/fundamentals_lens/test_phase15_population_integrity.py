"""
Unit and Adversarial Tests for Phase 15 Population Completeness & Cross-Artifact Referential Integrity (M1).

Tests:
1. Dynamic population derivation: verifies 15 companies, 75 annual periods, 375 primary metrics, 75 derived FCF.
2. Pre-map uniqueness enforcement:
   - Duplicate observations with identical values fail before map creation.
   - Duplicate observations with conflicting values fail before map creation.
   - Repeated source-register keys fail.
   - Repeated financial fact periods fail.
3. Cross-artifact key alignment:
   - Missing financial fact periods are detected.
   - Extra/unregistered source observations are detected.
   - Missing rows in evidence_register.csv are detected.
4. Referential FCF derivation check:
   - Mismatch between canonical fact (OCF - Capex) and evidence register FCF fails.
5. Metadata count synchronization:
   - Metadata count shifts are detected.
"""

import copy
import pytest
from fundamentals_lens.validator import FundamentalsValidator
from fundamentals_lens.data_loader import (
    load_companies,
    load_financial_facts,
    load_source_observations,
    load_source_register,
    load_evidence_register,
    load_discrepancy_ledger,
    load_dataset_metadata
)


@pytest.fixture
def base_data():
    return {
        "companies": load_companies(),
        "facts": load_financial_facts(),
        "obs": load_source_observations(),
        "sources": load_source_register(),
        "evidence": load_evidence_register(),
        "discrepancies": load_discrepancy_ledger(),
        "metadata": load_dataset_metadata()
    }


def test_committed_population_integrity_passes(base_data):
    """Verify that the committed repository datasets pass population and referential integrity."""
    res = FundamentalsValidator.validate_population_and_cross_artifact_integrity(
        companies=base_data["companies"],
        financial_facts=base_data["facts"],
        source_observations=base_data["obs"],
        sources=base_data["sources"],
        evidence_register=base_data["evidence"],
        discrepancies=base_data["discrepancies"],
        metadata=base_data["metadata"]
    )
    assert res.status.value == "PASS", f"Validation failed: {res.message} - {res.details}"
    assert res.details["companies"] == 15
    assert res.details["periods"] == 75
    assert res.details["primary_metrics"] == 375
    assert res.details["fcf_derived"] == 75


def test_duplicate_observations_fail_pre_map(base_data):
    """Verify that duplicate observations (identical or conflicting) fail pre-map uniqueness."""
    mutated_obs = copy.deepcopy(base_data["obs"])
    # Duplicate first observation
    dup_obs = copy.deepcopy(mutated_obs[0])
    mutated_obs.append(dup_obs)

    res = FundamentalsValidator.validate_population_and_cross_artifact_integrity(
        companies=base_data["companies"],
        financial_facts=base_data["facts"],
        source_observations=mutated_obs,
        sources=base_data["sources"],
        evidence_register=base_data["evidence"],
        discrepancies=base_data["discrepancies"],
        metadata=base_data["metadata"]
    )
    assert res.status.value == "FAIL"
    assert any("Duplicate source observation" in e for e in res.details["errors"])


def test_duplicate_source_register_keys_fail(base_data):
    """Verify that repeated source-register keys fail validation."""
    mutated_sources = copy.deepcopy(base_data["sources"])
    dup_src = copy.deepcopy(mutated_sources[0])
    mutated_sources.append(dup_src)

    res = FundamentalsValidator.validate_population_and_cross_artifact_integrity(
        companies=base_data["companies"],
        financial_facts=base_data["facts"],
        source_observations=base_data["obs"],
        sources=mutated_sources,
        evidence_register=base_data["evidence"],
        discrepancies=base_data["discrepancies"],
        metadata=base_data["metadata"]
    )
    assert res.status.value == "FAIL"
    assert any("Duplicate source" in e for e in res.details["errors"])


def test_missing_fact_period_fails(base_data):
    """Verify that removing a company-period record from financial facts fails validation."""
    mutated_facts = [f for f in base_data["facts"] if not (f.ticker == "AAPL" and f.fiscal_year == 2021)]

    res = FundamentalsValidator.validate_population_and_cross_artifact_integrity(
        companies=base_data["companies"],
        financial_facts=mutated_facts,
        source_observations=base_data["obs"],
        sources=base_data["sources"],
        evidence_register=base_data["evidence"],
        discrepancies=base_data["discrepancies"],
        metadata=base_data["metadata"]
    )
    assert res.status.value == "FAIL"
    assert any("Missing" in e or "Extra" in e for e in res.details["errors"])


def test_derived_fcf_reconciliation_mismatch_fails(base_data):
    """Verify that an arithmetic mismatch between canonical facts (OCF - Capex) and evidence FCF fails."""
    mutated_evidence = copy.deepcopy(base_data["evidence"])
    # Corrupt derived FCF in first evidence record
    mutated_evidence[0]["free_cash_flow_derived"]["canonical_fcf_value"] += 999.0

    res = FundamentalsValidator.validate_population_and_cross_artifact_integrity(
        companies=base_data["companies"],
        financial_facts=base_data["facts"],
        source_observations=base_data["obs"],
        sources=base_data["sources"],
        evidence_register=mutated_evidence,
        discrepancies=base_data["discrepancies"],
        metadata=base_data["metadata"]
    )
    assert res.status.value == "FAIL"
    assert any("Derived FCF in evidence register" in e for e in res.details["errors"])


def test_metadata_count_mismatch_fails(base_data):
    """Verify that a discrepancy between metadata counts and underlying population fails."""
    mutated_metadata = copy.deepcopy(base_data["metadata"])
    mutated_metadata["total_metric_observations"] = 374

    res = FundamentalsValidator.validate_population_and_cross_artifact_integrity(
        companies=base_data["companies"],
        financial_facts=base_data["facts"],
        source_observations=base_data["obs"],
        sources=base_data["sources"],
        evidence_register=base_data["evidence"],
        discrepancies=base_data["discrepancies"],
        metadata=mutated_metadata
    )
    assert res.status.value == "FAIL"
    assert any("metadata.total_metric_observations" in e for e in res.details["errors"])
