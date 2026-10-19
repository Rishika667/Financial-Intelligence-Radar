"""
Phase 19 Evidence Assurance & Adversarial Integrity Test Suite.

Tests multi-tier verification semantics, the 8-state AssuranceState model,
and adversarial tampering across canonical facts, observations, sources,
hashes, timestamps, statement bases, and discrepancy records.
"""

import copy
import json
import pytest

from fundamentals_lens.models import (
    AssuranceState,
    FinancialFact,
    VerificationTier,
    normalize_verification_tier,
)
from fundamentals_lens.reconciliation import (
    reconcile_metric_observation,
    derive_source_reconciliation_status,
    validate_reconciliation_telemetry,
    DocumentRetrievalStatus,
    DocumentIdentityStatus,
    PeriodMatchStatus,
    MetricExtractionStatus,
    ReconciliationTier,
)
from fundamentals_lens.validator import DataIntegrityValidator, ValidationStatus
from fundamentals_lens.data_loader import (
    load_companies,
    load_financial_facts,
    load_evidence_register,
    load_discrepancy_ledger,
    load_source_register,
    load_source_observations,
    load_dataset_metadata,
)


def test_assurance_state_enum_distinct_and_exhaustive():
    """Verify all 8 distinct assurance states exist and have non-empty values."""
    expected_states = [
        "SOURCE_REFERENCE_RECORDED",
        "SOURCE_IDENTITY_CHECKED",
        "OFFLINE_EXTRACT_RECORDED",
        "DOCUMENT_SNAPSHOT_HASHED",
        "PRIMARY_STATEMENT_LINE_ITEM_AUDITED",
        "LIVE_RETRIEVAL_SUCCEEDED",
        "APPROVED_ADJUSTMENT_RESOLVED",
        "PENDING_OR_DISCREPANT",
    ]
    actual_states = [s.value for s in AssuranceState]
    assert len(actual_states) == 8
    for state in expected_states:
        assert state in actual_states


def test_reconciliation_assigns_tracked_offline_vs_independently_reconciled():
    """Verify that offline facts matching observations receive TRACKED_OFFLINE_EXTRACT,
    while approved discrepancy adjustments or live retrievals receive INDEPENDENTLY_RECONCILED."""
    sources = load_source_register()
    obs_list = load_source_observations()
    discrepancies = load_discrepancy_ledger()

    # Find AAPL FY2021 source and revenue observation
    src_aapl = [s for s in sources if s.get("ticker") == "AAPL" and s.get("fiscal_year") == 2021][0]
    obs_aapl_rev = [o for o in obs_list if o.get("ticker") == "AAPL" and o.get("fiscal_year") == 2021 and o.get("metric_name") == "revenue"][0]

    # 1. Standard offline match -> TRACKED_OFFLINE_EXTRACT / OFFLINE_EXTRACT_RECORDED
    res_offline = reconcile_metric_observation(
        canonical_val=365817.0,
        reported_val=365817.0,
        ticker="AAPL",
        fiscal_year=2021,
        fiscal_year_label="FY2021",
        metric_key="revenue",
        src_entry=src_aapl,
        discrepancy_ledger=discrepancies,
        obs_entry=obs_aapl_rev,
        verification_mode="OFFLINE",
        verification_timestamp="2026-10-19T12:00:00Z",
    )
    assert res_offline["reconciliation_tier"] == VerificationTier.TRACKED_OFFLINE_EXTRACT.value
    assert res_offline["assurance_state"] == AssuranceState.OFFLINE_EXTRACT_RECORDED.value
    assert res_offline["comparison_result"] == "EXACT_STATEMENT_MATCH"

    # 2. Approved discrepancy resolution -> INDEPENDENTLY_RECONCILED / APPROVED_ADJUSTMENT_RESOLVED
    # Find an approved discrepancy: GOOGL FY2025 capital_expenditure (DISC-001)
    src_googl = [s for s in sources if s.get("ticker") == "GOOGL" and s.get("fiscal_year") == 2025][0]
    obs_googl_capex = [o for o in obs_list if o.get("ticker") == "GOOGL" and o.get("fiscal_year") == 2025 and o.get("metric_name") == "capital_expenditure"][0]
    res_adj = reconcile_metric_observation(
        canonical_val=91447.0,
        reported_val=91447.0,
        ticker="GOOGL",
        fiscal_year=2025,
        fiscal_year_label="FY2025",
        metric_key="capital_expenditure",
        src_entry=src_googl,
        discrepancy_ledger=discrepancies,
        obs_entry=obs_googl_capex,
        verification_mode="OFFLINE",
        verification_timestamp="2026-10-19T12:00:00Z",
    )
    assert res_adj["reconciliation_tier"] == VerificationTier.INDEPENDENTLY_RECONCILED.value
    assert res_adj["assurance_state"] == AssuranceState.APPROVED_ADJUSTMENT_RESOLVED.value
    assert res_adj["comparison_result"] in ("RECONCILED_WITH_APPROVED_ADJUSTMENT", "RECONCILED_WITH_DOCUMENTED_ADJUSTMENT")

    # 3. Live retrieval -> INDEPENDENTLY_RECONCILED / LIVE_RETRIEVAL_SUCCEEDED
    retrieval_success = {"outcome": "SUCCESS", "http_status": 200}
    res_live = reconcile_metric_observation(
        canonical_val=365817.0,
        reported_val=365817.0,
        ticker="AAPL",
        fiscal_year=2021,
        fiscal_year_label="FY2021",
        metric_key="revenue",
        src_entry=src_aapl,
        discrepancy_ledger=discrepancies,
        obs_entry=obs_aapl_rev,
        verification_mode="ONLINE",
        verification_timestamp="2026-10-19T12:00:00Z",
        retrieval_outcome=retrieval_success,
    )
    assert res_live["reconciliation_tier"] == VerificationTier.INDEPENDENTLY_RECONCILED.value
    assert res_live["assurance_state"] == AssuranceState.LIVE_RETRIEVAL_SUCCEEDED.value


def test_adversarial_tamper_fact_vs_observation_value():
    """Adversarial test: Tampering reported value without approved discrepancy causes unexplained discrepancy."""
    sources = load_source_register()
    obs_list = load_source_observations()
    discrepancies = load_discrepancy_ledger()

    src_msft = [s for s in sources if s.get("ticker") == "MSFT" and s.get("fiscal_year") == 2024][0]
    obs_msft_rev = copy.deepcopy([o for o in obs_list if o.get("ticker") == "MSFT" and o.get("fiscal_year") == 2024 and o.get("metric_name") == "revenue"][0])

    res = reconcile_metric_observation(
        canonical_val=245120.0,
        reported_val=999999.0,  # Fabricated mismatch
        ticker="MSFT",
        fiscal_year=2024,
        fiscal_year_label="FY2024",
        metric_key="revenue",
        src_entry=src_msft,
        discrepancy_ledger=discrepancies,
        obs_entry=obs_msft_rev,
        verification_mode="OFFLINE",
        verification_timestamp="2026-10-19T12:00:00Z",
    )
    assert res["reconciliation_tier"] == VerificationTier.UNVERIFIED.value or res["numeric_reconciliation_status"] == "UNEXPLAINED_DISCREPANCY"
    assert res["assurance_state"] == AssuranceState.PENDING_OR_DISCREPANT.value
    assert res["comparison_result"] == "UNEXPLAINED_DISCREPANCY"


def test_adversarial_tamper_evidence_tier_inflation_fails_telemetry():
    """Adversarial test: Telemetry rejects OFFLINE INDEPENDENTLY_RECONCILED without approved discrepancy or hash."""
    tampered_record = {
        "verification_mode": "OFFLINE",
        "document_retrieval_status": "OFFLINE_AUDITED",
        "document_identity_status": "VALIDATED",
        "period_match_status": "EXACT_PERIOD_MATCH",
        "metric_extraction_status": "EXTRACTED_LINE_ITEM",
        "reconciliation_tier": "INDEPENDENTLY_RECONCILED",
        "verification_timestamp": "2026-10-19T12:00:00Z",
        # Intentionally missing approved_discrepancy_id and document_snapshot_hash
    }
    is_valid, errors = validate_reconciliation_telemetry(tampered_record)
    assert not is_valid
    assert any("without approved_discrepancy_id or document_snapshot_hash" in e for e in errors)


def test_adversarial_tamper_empty_timestamp_fails_telemetry():
    """Adversarial test: Reconciled tier without verification_timestamp fails telemetry validation."""
    record = {
        "verification_mode": "OFFLINE",
        "document_retrieval_status": "OFFLINE_AUDITED",
        "document_identity_status": "VALIDATED",
        "period_match_status": "EXACT_PERIOD_MATCH",
        "metric_extraction_status": "EXTRACTED_LINE_ITEM",
        "reconciliation_tier": "TRACKED_OFFLINE_EXTRACT",
        "verification_timestamp": "",  # Empty timestamp
    }
    is_valid, errors = validate_reconciliation_telemetry(record)
    assert not is_valid
    assert any("verification_timestamp is empty" in e for e in errors)


def test_adversarial_tamper_unlocated_metric_cannot_claim_reconciled():
    """Adversarial test: VALUE_NOT_LOCATED metric extraction cannot claim TRACKED_OFFLINE_EXTRACT or INDEPENDENTLY_RECONCILED."""
    record = {
        "verification_mode": "OFFLINE",
        "document_retrieval_status": "OFFLINE_AUDITED",
        "document_identity_status": "VALIDATED",
        "period_match_status": "EXACT_PERIOD_MATCH",
        "metric_extraction_status": "VALUE_NOT_LOCATED",
        "reconciliation_tier": "TRACKED_OFFLINE_EXTRACT",
        "verification_timestamp": "2026-10-19T12:00:00Z",
    }
    is_valid, errors = validate_reconciliation_telemetry(record)
    assert not is_valid
    assert any("metric_extraction_status is VALUE_NOT_LOCATED" in e for e in errors)


def test_adversarial_tamper_period_mismatch_cannot_claim_reconciled():
    """Adversarial test: PERIOD_MISMATCH cannot claim TRACKED_OFFLINE_EXTRACT."""
    record = {
        "verification_mode": "OFFLINE",
        "document_retrieval_status": "OFFLINE_AUDITED",
        "document_identity_status": "VALIDATED",
        "period_match_status": "PERIOD_MISMATCH",
        "metric_extraction_status": "EXTRACTED_LINE_ITEM",
        "reconciliation_tier": "TRACKED_OFFLINE_EXTRACT",
        "verification_timestamp": "2026-10-19T12:00:00Z",
    }
    is_valid, errors = validate_reconciliation_telemetry(record)
    assert not is_valid
    assert any("period_match_status is PERIOD_MISMATCH" in e for e in errors)


def test_adversarial_tamper_statement_basis_fails_validator():
    """Adversarial test: DataIntegrityValidator rejects standalone observation for consolidated fact."""
    facts = load_financial_facts()
    aapl_facts = [f for f in facts if f.ticker == "AAPL"]
    evidence = load_evidence_register()
    sources = load_source_register()
    obs = load_source_observations()

    # Tamper one observation's statement_basis to STANDALONE
    tampered_obs = copy.deepcopy(obs)
    for o in tampered_obs:
        if o.get("ticker") == "AAPL" and o.get("fiscal_year") == 2024 and o.get("metric_name") == "revenue":
            o["statement_basis"] = "STANDALONE"
            break

    results = DataIntegrityValidator._check_evidence_alignment_and_tiers(
        facts=aapl_facts,
        evidence_register=evidence,
        source_observations=tampered_obs,
        sources=sources,
    )
    obs_gate = [r for r in results if r.rule_id == "GATE_INDEPENDENT_SOURCE_OBSERVATION"]
    assert len(obs_gate) == 1
    assert obs_gate[0].status == ValidationStatus.FAIL
    assert "statement_basis is 'STANDALONE'" in obs_gate[0].message or any("STANDALONE" in e for e in obs_gate[0].details.get("errors", []))


def test_adversarial_tamper_reported_value_mismatch_fails_validator():
    """Adversarial test: DataIntegrityValidator rejects canonical value mismatch in EXACT_STATEMENT_MATCH."""
    facts = load_financial_facts()
    aapl_facts = [f for f in facts if f.ticker == "AAPL"]
    evidence = load_evidence_register()
    sources = load_source_register()
    obs = load_source_observations()

    tampered_obs = copy.deepcopy(obs)
    for o in tampered_obs:
        if o.get("ticker") == "AAPL" and o.get("fiscal_year") == 2024 and o.get("metric_name") == "revenue":
            o["reported_value"] = 123456.0
            break

    results = DataIntegrityValidator._check_evidence_alignment_and_tiers(
        facts=aapl_facts,
        evidence_register=evidence,
        source_observations=tampered_obs,
        sources=sources,
    )
    obs_gate = [r for r in results if r.rule_id == "GATE_INDEPENDENT_SOURCE_OBSERVATION"]
    assert len(obs_gate) == 1
    assert obs_gate[0].status == ValidationStatus.FAIL


def test_adversarial_tamper_negative_capex_fails_validator():
    """Adversarial test: Negative capital expenditure violates non-negative cash outflow convention."""
    facts = load_financial_facts()
    aapl_facts = copy.deepcopy([f for f in facts if f.ticker == "AAPL"])
    aapl_facts[0].capital_expenditure = -9435.0  # Tampered negative capex

    results = DataIntegrityValidator._check_arithmetic_invariants(aapl_facts)
    capex_gate = [r for r in results if r.rule_id == "GATE_ARITHMETIC_CAPEX_SIGN"]
    assert len(capex_gate) == 1
    assert capex_gate[0].status == ValidationStatus.FAIL
    assert "non-negative cash outflow magnitude" in capex_gate[0].message


def test_adversarial_tamper_sec_accession_format_fails_validator():
    """Adversarial test: Invalid SEC accession format fails reference type integrity gate."""
    facts = load_financial_facts()
    aapl_facts = copy.deepcopy([f for f in facts if f.ticker == "AAPL"])
    aapl_facts[0].accession_id = "INVALID_ACCESSION_STRING"

    res = DataIntegrityValidator._check_filing_reference_types(aapl_facts)
    assert res.status == ValidationStatus.FAIL
    assert "does not match standard 20-digit pattern" in res.message or "integrity violations" in res.message


def test_maruti_suzuki_analytical_guidance_present_in_insights_and_discrepancy():
    """Verify that Maruti Suzuki like-for-like Net Sales (+20.2%) guidance is registered
    in discrepancy ledger DISC-017 and highlighted in insights engine."""
    from fundamentals_lens.insights import InsightsEngine

    discrepancies = load_discrepancy_ledger()
    maruti_disc = [d for d in discrepancies if d.get("discrepancy_id") == "DISC-017"]
    assert len(maruti_disc) == 1
    disc = maruti_disc[0]
    assert disc.get("disposition") == "TREND_ANALYSIS_QUALIFIED"
    assert "20.2%" in disc.get("trend_analysis_guidance", "") or "Net Sales" in disc.get("trend_analysis_guidance", "")

    # Run insights engine for MARUTI
    facts = load_financial_facts()
    maruti_facts = [f for f in facts if f.ticker in ("MARUTI", "MARUTI.BSE")]
    insights = InsightsEngine.generate_company_insights(maruti_facts)
    growth_insight = [i for i in insights if i.category == "TOP_LINE_GROWTH"]
    assert len(growth_insight) >= 1
    assert "20.2%" in growth_insight[0].what_changed or "Net Sales" in growth_insight[0].what_changed
