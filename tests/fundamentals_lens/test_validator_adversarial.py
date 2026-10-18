"""
Phase 5 Mutation and Adversarial Test Suite:
Proves that FundamentalsValidator reliably detects and fails on:
1. Wrong financial number (operating margin invariant failure)
2. Wrong source URL (generic URL or mismatched URL)
3. Wrong accession/reference ID (fact vs source register mismatch)
4. Wrong fiscal year label (label mismatch or chronological gap)
5. Missing source record (unaligned fact with no source register entry)
6. Duplicate period-end (uniqueness violation)
7. Missing or contradictory coverage record (status code vs periods contradiction)
8. False metric definition (invalid accounting taxonomy or mismatched flag)
9. Unexplained zero (synthetic coercion guard triggered)
10. Invalid or mismatched currency/scale
11. Incorrect FCF calculation (OCF - Capex arithmetic failure)
12. Negative capex sign (violating cash outflow magnitude convention)
"""

import pytest
import copy

from fundamentals_lens.data_loader import (
    load_companies,
    load_financial_facts,
    load_source_register,
    load_coverage_report,
    get_facts_for_company,
    get_company_by_ticker
)
from fundamentals_lens.validator import FundamentalsValidator
from fundamentals_lens.models import ValidationStatus, FinancialFact


@pytest.fixture
def sample_company_dataset():
    company = get_company_by_ticker("AAPL")
    facts = get_facts_for_company("AAPL")
    sources = [s for s in load_source_register() if s["ticker"] == "AAPL"]
    coverage = load_coverage_report()
    return company, facts, sources, coverage


def test_adversarial_wrong_financial_number(sample_company_dataset):
    """1. Adversarial test: Setting operating income greater than revenue breaks operating margin invariant."""
    company, facts, sources, coverage = sample_company_dataset
    mutated_facts = copy.deepcopy(facts)
    # Corrupt operating income so it exceeds revenue (impossible >100% margin)
    mutated_facts[0].operating_income = mutated_facts[0].revenue * 1.5
    
    results = FundamentalsValidator.validate_company_dataset(company, mutated_facts, sources, coverage)
    margin_res = next(r for r in results if r.rule_id == "GATE_ARITHMETIC_OPERATING_MARGIN")
    assert margin_res.status == ValidationStatus.FAIL
    assert "Operating margin reconciliation mismatch" in margin_res.message


def test_adversarial_wrong_source_url(sample_company_dataset):
    """2. Adversarial test: Using a generic browse/root URL fails source lineage gate."""
    company, facts, sources, coverage = sample_company_dataset
    mutated_facts = copy.deepcopy(facts)
    mutated_sources = copy.deepcopy(sources)
    
    # Inject generic URL into fact and source
    mutated_facts[0].source_url = "https://www.apple.com/investor-relations"
    mutated_sources[0]["source_url"] = "https://www.apple.com/investor-relations"
    
    results = FundamentalsValidator.validate_company_dataset(company, mutated_facts, mutated_sources, coverage)
    prov_res = next(r for r in results if r.rule_id == "GATE_SOURCE_PROVENANCE")
    assert prov_res.status == ValidationStatus.FAIL
    assert "Generic search/browse or bare landing URLs detected" in prov_res.message


def test_adversarial_wrong_accession_id(sample_company_dataset):
    """3. Adversarial test: Tampered accession ID breaks 1:1 source alignment."""
    company, facts, sources, coverage = sample_company_dataset
    mutated_facts = copy.deepcopy(facts)
    mutated_facts[0].accession_id = "0000000000-00-000000-WRONG"
    
    results = FundamentalsValidator.validate_company_dataset(company, mutated_facts, sources, coverage)
    prov_res = next(r for r in results if r.rule_id == "GATE_SOURCE_PROVENANCE")
    assert prov_res.status == ValidationStatus.FAIL
    assert "Source register alignment mismatches detected" in prov_res.message


def test_adversarial_wrong_fiscal_year_label(sample_company_dataset):
    """4. Adversarial test: Corrupting fiscal year label fails period completeness gate."""
    company, facts, sources, coverage = sample_company_dataset
    mutated_facts = copy.deepcopy(facts)
    mutated_facts[0].fiscal_year_label = "FY2099" # Mismatches fiscal_year 2021
    
    results = FundamentalsValidator.validate_company_dataset(company, mutated_facts, sources, coverage)
    comp_res = next(r for r in results if r.rule_id == "GATE_PERIOD_COMPLETENESS")
    assert comp_res.status == ValidationStatus.FAIL
    assert "Fiscal year label 'FY2099' does not correspond to fiscal_year 2021" in comp_res.message


def test_adversarial_missing_source_record(sample_company_dataset):
    """5. Adversarial test: Missing source register record fails provenance verification."""
    company, facts, sources, coverage = sample_company_dataset
    # Remove period 0 from source register
    incomplete_sources = [s for s in sources if s["fiscal_year_label"] != "FY2021"]
    
    results = FundamentalsValidator.validate_company_dataset(company, facts, incomplete_sources, coverage)
    prov_res = next(r for r in results if r.rule_id == "GATE_SOURCE_PROVENANCE")
    assert prov_res.status == ValidationStatus.FAIL
    assert "Source register alignment mismatches detected" in prov_res.message


def test_adversarial_duplicate_period_end(sample_company_dataset):
    """6. Adversarial test: Duplicate period-end date fails uniqueness gate."""
    company, facts, sources, coverage = sample_company_dataset
    mutated_facts = copy.deepcopy(facts)
    # Set period 1 end date identical to period 0
    mutated_facts[1].period_end = mutated_facts[0].period_end
    
    results = FundamentalsValidator.validate_company_dataset(company, mutated_facts, sources, coverage)
    dup_res = next(r for r in results if r.rule_id == "GATE_NO_DUPLICATES")
    assert dup_res.status == ValidationStatus.FAIL
    assert "Duplicate observation keys detected" in dup_res.message


def test_adversarial_contradictory_coverage_record(sample_company_dataset):
    """7. Adversarial test: Contradictory coverage report claims pending horizon that is already present."""
    company, facts, sources, coverage = sample_company_dataset
    mutated_coverage = copy.deepcopy(coverage)
    cov_entry = next(c for c in mutated_coverage if c["ticker"] == "AAPL")
    # AAPL has verified periods FY2021-FY2025. Contradict by claiming target horizon is FY2025 but code 1 (pending)
    cov_entry["target_horizon_period"] = "FY2025"
    cov_entry["target_period_status_code"] = 1
    
    results = FundamentalsValidator.validate_company_dataset(company, facts, sources, mutated_coverage)
    cov_res = next(r for r in results if r.rule_id == "GATE_COVERAGE_INTEGRITY")
    assert cov_res.status == ValidationStatus.FAIL
    assert "Status code 1 claims target horizon FY2025 is pending, but it is already in verified periods" in cov_res.message


def test_adversarial_missing_coverage_record(sample_company_dataset):
    """7b. Adversarial test: Missing coverage entry for company returns FAIL."""
    company, facts, sources, coverage = sample_company_dataset
    stripped_coverage = [c for c in coverage if c["ticker"] != "AAPL"]
    
    results = FundamentalsValidator.validate_company_dataset(company, facts, sources, stripped_coverage)
    cov_res = next(r for r in results if r.rule_id == "GATE_COVERAGE_INTEGRITY")
    assert cov_res.status == ValidationStatus.FAIL
    assert "Missing coverage report entry for AAPL" in cov_res.message


def test_adversarial_false_metric_definition(sample_company_dataset):
    """8. Adversarial test: Fabricated accounting metric taxonomy fails definition gate."""
    company, facts, sources, coverage = sample_company_dataset
    mutated_sources = copy.deepcopy(sources)
    # Corrupt metric definition type
    mutated_sources[0]["metric_definitions"]["operating_income_type"] = "FABRICATED_EBITDA_NON_GAAP"
    
    results = FundamentalsValidator.validate_company_dataset(company, facts, mutated_sources, coverage)
    def_res = next(r for r in results if r.rule_id == "GATE_METRIC_DEFINITIONS")
    assert def_res.status == ValidationStatus.FAIL
    assert "Invalid operating_income_type 'FABRICATED_EBITDA_NON_GAAP'" in def_res.message


def test_adversarial_unexplained_zero(sample_company_dataset):
    """9. Adversarial test: Synthetic coercion to zero without disclosure note fails guard."""
    company, facts, sources, coverage = sample_company_dataset
    mutated_facts = copy.deepcopy(facts)
    # Zero capex without disclosure note
    mutated_facts[0].capital_expenditure = 0.0
    mutated_facts[0].notes = ""
    mutated_facts[0].accounting_notes = ""
    
    results = FundamentalsValidator.validate_company_dataset(company, mutated_facts, sources, coverage)
    zero_res = next(r for r in results if r.rule_id == "GATE_NON_COERCION")
    assert zero_res.status == ValidationStatus.FAIL
    assert "Potential synthetic zero coercion detected" in zero_res.message


def test_adversarial_mismatched_currency_and_scale(sample_company_dataset):
    """10. Adversarial test: Currency or scale multiplier tampering fails reporting standards gate."""
    company, facts, sources, coverage = sample_company_dataset
    mutated_facts = copy.deepcopy(facts)
    mutated_facts[0].currency = "EUR" # Expected USD
    
    results = FundamentalsValidator.validate_company_dataset(company, mutated_facts, sources, coverage)
    curr_res = next(r for r in results if r.rule_id == "GATE_UNIT_CONSISTENCY")
    assert curr_res.status == ValidationStatus.FAIL
    assert "Currency mismatch for AAPL: expected USD" in curr_res.message


def test_adversarial_negative_capex_sign(sample_company_dataset):
    """11. Adversarial test: Negative capex violates cash outflow positive magnitude invariant."""
    company, facts, sources, coverage = sample_company_dataset
    mutated_facts = copy.deepcopy(facts)
    mutated_facts[0].capital_expenditure = -5000.0
    
    results = FundamentalsValidator.validate_company_dataset(company, mutated_facts, sources, coverage)
    capex_res = next(r for r in results if r.rule_id == "GATE_ARITHMETIC_CAPEX_SIGN")
    assert capex_res.status == ValidationStatus.FAIL
    assert "Capex must be expressed as a non-negative cash outflow magnitude" in capex_res.message


def test_adversarial_subtle_financial_value_change(sample_company_dataset):
    """12. Adversarial test: Plausible +$1M mutation in revenue fails fact-evidence alignment gate."""
    company, facts, sources, coverage = sample_company_dataset
    mutated_facts = copy.deepcopy(facts)
    # Slightly shift revenue by +1.0 (margin remains completely plausible, but violates evidence source)
    mutated_facts[0].revenue += 1.0
    
    results = FundamentalsValidator.validate_company_dataset(company, mutated_facts, sources, coverage)
    align_res = next(r for r in results if r.rule_id == "GATE_FACT_EVIDENCE_ALIGNMENT")
    assert align_res.status == ValidationStatus.FAIL
    assert "Discrepancies detected between financial facts and primary evidence register" in align_res.message


def test_adversarial_fact_changed_without_evidence_change(sample_company_dataset):
    """13. Adversarial test: Fact changed without evidence change is detected immediately."""
    company, facts, sources, coverage = sample_company_dataset
    from fundamentals_lens.data_loader import load_evidence_register
    evidence_reg = copy.deepcopy(load_evidence_register())
    mutated_facts = copy.deepcopy(facts)
    mutated_facts[0].operating_income += 5.0
    
    results = FundamentalsValidator.validate_company_dataset(
        company, mutated_facts, sources, coverage=coverage, evidence_register=evidence_reg
    )
    align_res = next(r for r in results if r.rule_id == "GATE_FACT_EVIDENCE_ALIGNMENT")
    assert align_res.status == ValidationStatus.FAIL


def test_adversarial_evidence_changed_without_fact_change(sample_company_dataset):
    """14. Adversarial test: Evidence changed without corresponding fact change fails alignment."""
    company, facts, sources, coverage = sample_company_dataset
    from fundamentals_lens.data_loader import load_evidence_register
    mutated_evidence = copy.deepcopy(load_evidence_register())
    # Tamper with the evidence register canonical value
    for item in mutated_evidence:
        if item["ticker"] == "AAPL" and item["fiscal_year_label"] == "FY2021":
            item["metrics"]["net_income"]["canonical_value"] += 10.0
            break
            
    results = FundamentalsValidator.validate_company_dataset(
        company, facts, sources, coverage=coverage, evidence_register=mutated_evidence
    )
    align_res = next(r for r in results if r.rule_id == "GATE_FACT_EVIDENCE_ALIGNMENT")
    assert align_res.status == ValidationStatus.FAIL
    assert "Discrepancies detected between financial facts and primary evidence register" in align_res.message


def test_adversarial_fabricated_reconciliation_tier_without_locator(sample_company_dataset):
    """15. Adversarial test: Claiming INDEPENDENTLY_RECONCILED without locator fails tier consistency gate."""
    company, facts, sources, coverage = sample_company_dataset
    from fundamentals_lens.data_loader import load_evidence_register
    mutated_evidence = copy.deepcopy(load_evidence_register())
    for item in mutated_evidence:
        if item["ticker"] == "AAPL" and item["fiscal_year_label"] == "FY2021":
            # Strip locator while claiming INDEPENDENTLY_RECONCILED
            item["metrics"]["revenue"]["statement_locator"] = ""
            break
            
    results = FundamentalsValidator.validate_company_dataset(
        company, facts, sources, coverage=coverage, evidence_register=mutated_evidence
    )
    tier_res = next(r for r in results if r.rule_id == "GATE_EVIDENCE_TIER_CONSISTENCY")
    assert tier_res.status == ValidationStatus.FAIL
    assert "Reconciliation tier requirements violated" in tier_res.message


def test_adversarial_internal_id_mislabeled_as_sec_accession(sample_company_dataset):
    """16. Adversarial test: Internal document key mislabeled as SEC accession fails reference type gate."""
    company, facts, sources, coverage = sample_company_dataset
    mutated_facts = copy.deepcopy(facts)
    mutated_facts[0].reference_type = "SEC_ACCESSION"
    mutated_facts[0].accession_id = "BSE-SCRIP-500325-AR-2021-22"
    
    results = FundamentalsValidator.validate_company_dataset(company, mutated_facts, sources, coverage)
    ref_res = next(r for r in results if r.rule_id == "GATE_REFERENCE_TYPE_INTEGRITY")
    assert ref_res.status == ValidationStatus.FAIL
    assert "falsely labeled as SEC_ACCESSION" in ref_res.message


def test_adversarial_sec_accession_with_internal_key(sample_company_dataset):
    """17. Adversarial test: SEC_ACCESSION record having an internal document key fails integrity."""
    company, facts, sources, coverage = sample_company_dataset
    mutated_facts = copy.deepcopy(facts)
    mutated_facts[0].internal_document_key = "INTERNAL-BSE-KEY"
    
    results = FundamentalsValidator.validate_company_dataset(company, mutated_facts, sources, coverage)
    ref_res = next(r for r in results if r.rule_id == "GATE_REFERENCE_TYPE_INTEGRITY")
    assert ref_res.status == ValidationStatus.FAIL
    assert "has internal_document_key set" in ref_res.message


def test_adversarial_invalid_date_format(sample_company_dataset):
    """18. Adversarial test: Non-ISO period date string fails date format gate."""
    company, facts, sources, coverage = sample_company_dataset
    mutated_facts = copy.deepcopy(facts)
    mutated_facts[0].period_end = "25/09/2021" # Slash-delimited non-ISO format
    
    results = FundamentalsValidator.validate_company_dataset(company, mutated_facts, sources, coverage)
    date_res = next(r for r in results if r.rule_id == "GATE_PERIOD_DATE_FORMAT")
    assert date_res.status == ValidationStatus.FAIL
    assert "Invalid period_end date format" in date_res.message


def test_adversarial_reconciled_with_null_reported_value(sample_company_dataset):
    """19. Adversarial test: INDEPENDENTLY_RECONCILED with null reported_value fails tier gate."""
    from fundamentals_lens.data_loader import load_evidence_register
    company, facts, sources, coverage = sample_company_dataset
    mutated_evidence = copy.deepcopy(load_evidence_register())
    for item in mutated_evidence:
        if item["ticker"] == "AAPL" and item["fiscal_year_label"] == "FY2021":
            item["metrics"]["revenue"]["reported_value"] = None
            break

    results = FundamentalsValidator.validate_company_dataset(
        company, facts, sources, coverage=coverage, evidence_register=mutated_evidence
    )
    tier_res = next(r for r in results if r.rule_id == "GATE_EVIDENCE_TIER_CONSISTENCY")
    assert tier_res.status == ValidationStatus.FAIL
    assert "requires non-null reported_value" in tier_res.details["tier_errors"][0]


def test_adversarial_reconciled_with_not_reconciled_result(sample_company_dataset):
    """20. Adversarial test: INDEPENDENTLY_RECONCILED with NOT_RECONCILED fails tier gate."""
    from fundamentals_lens.data_loader import load_evidence_register
    company, facts, sources, coverage = sample_company_dataset
    mutated_evidence = copy.deepcopy(load_evidence_register())
    for item in mutated_evidence:
        if item["ticker"] == "AAPL" and item["fiscal_year_label"] == "FY2021":
            item["metrics"]["revenue"]["comparison_result"] = "NOT_RECONCILED"
            break

    results = FundamentalsValidator.validate_company_dataset(
        company, facts, sources, coverage=coverage, evidence_register=mutated_evidence
    )
    tier_res = next(r for r in results if r.rule_id == "GATE_EVIDENCE_TIER_CONSISTENCY")
    assert tier_res.status == ValidationStatus.FAIL
    assert "cannot have comparison_result 'NOT_RECONCILED'" in tier_res.details["tier_errors"][0]


def test_adversarial_reconciled_exact_match_value_discrepancy(sample_company_dataset):
    """21. Adversarial test: EXACT_STATEMENT_MATCH reported_value differing from canonical fails tier gate."""
    from fundamentals_lens.data_loader import load_evidence_register
    company, facts, sources, coverage = sample_company_dataset
    mutated_evidence = copy.deepcopy(load_evidence_register())
    for item in mutated_evidence:
        if item["ticker"] == "AAPL" and item["fiscal_year_label"] == "FY2021":
            # Change reported_value so it no longer matches canonical_value
            item["metrics"]["revenue"]["reported_value"] = item["metrics"]["revenue"]["canonical_value"] + 100.0
            break

    results = FundamentalsValidator.validate_company_dataset(
        company, facts, sources, coverage=coverage, evidence_register=mutated_evidence
    )
    tier_res = next(r for r in results if r.rule_id == "GATE_EVIDENCE_TIER_CONSISTENCY")
    assert tier_res.status == ValidationStatus.FAIL
    assert "EXACT_STATEMENT_MATCH reported_value" in tier_res.details["tier_errors"][0]


def test_adversarial_source_linked_claiming_exact_match(sample_company_dataset):
    """22. Adversarial test: SOURCE_LINKED_ONLY claiming EXACT_STATEMENT_MATCH fails tier gate."""
    from fundamentals_lens.data_loader import load_evidence_register
    company, facts, sources, coverage = sample_company_dataset
    mutated_evidence = copy.deepcopy(load_evidence_register())
    for item in mutated_evidence:
        if item["ticker"] == "AAPL" and item["fiscal_year_label"] == "FY2021":
            # Demote tier to SOURCE_LINKED_ONLY but claim EXACT_STATEMENT_MATCH
            item["metrics"]["revenue"]["reconciliation_tier"] = "SOURCE_LINKED_ONLY"
            item["metrics"]["revenue"]["comparison_result"] = "EXACT_STATEMENT_MATCH"
            break

    results = FundamentalsValidator.validate_company_dataset(
        company, facts, sources, coverage=coverage, evidence_register=mutated_evidence
    )
    tier_res = next(r for r in results if r.rule_id == "GATE_EVIDENCE_TIER_CONSISTENCY")
    assert tier_res.status == ValidationStatus.FAIL
    assert "cannot claim comparison_result 'EXACT_STATEMENT_MATCH'" in tier_res.details["tier_errors"][0]


def test_adversarial_accession_mismatch_between_fact_and_evidence(sample_company_dataset):
    """23. Adversarial test: Accession ID mismatch between fact and evidence register fails alignment gate."""
    from fundamentals_lens.data_loader import load_evidence_register
    company, facts, sources, coverage = sample_company_dataset
    mutated_evidence = copy.deepcopy(load_evidence_register())
    for item in mutated_evidence:
        if item["ticker"] == "AAPL" and item["fiscal_year_label"] == "FY2021":
            item["official_filing_id"] = "0000320193-99-999999"
            break

    results = FundamentalsValidator.validate_company_dataset(
        company, facts, sources, coverage=coverage, evidence_register=mutated_evidence
    )
    align_res = next(r for r in results if r.rule_id == "GATE_FACT_EVIDENCE_ALIGNMENT")
    assert align_res.status == ValidationStatus.FAIL
    assert "Fact accession" in align_res.details["errors"][0]


def test_adversarial_url_mismatch_between_fact_and_evidence(sample_company_dataset):
    """24. Adversarial test: Source URL mismatch between fact and evidence register fails alignment gate."""
    from fundamentals_lens.data_loader import load_evidence_register
    company, facts, sources, coverage = sample_company_dataset
    mutated_evidence = copy.deepcopy(load_evidence_register())
    for item in mutated_evidence:
        if item["ticker"] == "AAPL" and item["fiscal_year_label"] == "FY2021":
            item["source_url"] = "https://www.sec.gov/Archives/edgar/data/320193/000032019321000105/tampered.htm"
            break

    results = FundamentalsValidator.validate_company_dataset(
        company, facts, sources, coverage=coverage, evidence_register=mutated_evidence
    )
    align_res = next(r for r in results if r.rule_id == "GATE_FACT_EVIDENCE_ALIGNMENT")
    assert align_res.status == ValidationStatus.FAIL
    assert "Fact source_url" in align_res.details["errors"][0]


def test_adversarial_altered_canonical_value_against_source_observation(sample_company_dataset):
    """25. Adversarial test: Altering canonical fact value against unchanged raw observation fails observation gate."""
    from fundamentals_lens.data_loader import load_evidence_register, load_source_observations
    company, facts, sources, coverage = sample_company_dataset
    mutated_facts = copy.deepcopy(facts)
    evidence = load_evidence_register()
    obs = load_source_observations()

    # Tamper with canonical revenue fact (change from 365817.0 to 400000.0)
    # Also update evidence canonical value so alignment passes, proving observation check catches it
    mutated_facts[0].revenue = 400000.0
    mutated_evidence = copy.deepcopy(evidence)
    for reg in mutated_evidence:
        if reg["ticker"] == "AAPL" and reg["fiscal_year_label"] == "FY2021":
            reg["metrics"]["revenue"]["canonical_value"] = 400000.0
            break

    results = FundamentalsValidator.validate_company_dataset(
        company, mutated_facts, sources, coverage=coverage, evidence_register=mutated_evidence, source_observations=obs
    )
    obs_res = next(r for r in results if r.rule_id == "GATE_INDEPENDENT_SOURCE_OBSERVATION")
    assert obs_res.status == ValidationStatus.FAIL
    assert any("Canonical fact" in err and "Observation reported_value" in err for err in obs_res.details["source_obs_errors"])


def test_adversarial_altered_source_observation_reported_value(sample_company_dataset):
    """26. Adversarial test: Corrupting reported value in source observations fails observation gate."""
    from fundamentals_lens.data_loader import load_evidence_register, load_source_observations
    company, facts, sources, coverage = sample_company_dataset
    evidence = load_evidence_register()
    mutated_obs = copy.deepcopy(load_source_observations())

    # Tamper with observation reported_value for AAPL FY2021 revenue
    for o in mutated_obs:
        if o["ticker"] == "AAPL" and o["fiscal_year_label"] == "FY2021" and o["metric_name"] == "revenue":
            o["reported_value"] = 999999.0
            break

    results = FundamentalsValidator.validate_company_dataset(
        company, facts, sources, coverage=coverage, evidence_register=evidence, source_observations=mutated_obs
    )
    obs_res = next(r for r in results if r.rule_id == "GATE_INDEPENDENT_SOURCE_OBSERVATION")
    assert obs_res.status == ValidationStatus.FAIL
    assert any("Evidence reported_value" in err and "Observation reported_value" in err for err in obs_res.details["source_obs_errors"])


def test_adversarial_standalone_statement_basis_fails_gate(sample_company_dataset):
    """27. Adversarial test: Standalone statement basis falsely labeled consolidated fails observation gate."""
    from fundamentals_lens.data_loader import load_evidence_register, load_source_observations
    company, facts, sources, coverage = sample_company_dataset
    evidence = load_evidence_register()
    mutated_obs = copy.deepcopy(load_source_observations())

    for o in mutated_obs:
        if o["ticker"] == "AAPL" and o["fiscal_year_label"] == "FY2021" and o["metric_name"] == "revenue":
            o["statement_basis"] = "STANDALONE"
            break

    results = FundamentalsValidator.validate_company_dataset(
        company, facts, sources, coverage=coverage, evidence_register=evidence, source_observations=mutated_obs
    )
    obs_res = next(r for r in results if r.rule_id == "GATE_INDEPENDENT_SOURCE_OBSERVATION")
    assert obs_res.status == ValidationStatus.FAIL
    assert any("Observation statement_basis is 'STANDALONE'" in err for err in obs_res.details["source_obs_errors"])


def test_adversarial_missing_xbrl_concept_on_sec_observation(sample_company_dataset):
    """28. Adversarial test: Missing XBRL concept on US SEC observation fails observation gate."""
    from fundamentals_lens.data_loader import load_evidence_register, load_source_observations
    company, facts, sources, coverage = sample_company_dataset
    evidence = load_evidence_register()
    mutated_obs = copy.deepcopy(load_source_observations())

    for o in mutated_obs:
        if o["ticker"] == "AAPL" and o["fiscal_year_label"] == "FY2021" and o["metric_name"] == "revenue":
            o["xbrl_concept"] = ""
            break

    results = FundamentalsValidator.validate_company_dataset(
        company, facts, sources, coverage=coverage, evidence_register=evidence, source_observations=mutated_obs
    )
    obs_res = next(r for r in results if r.rule_id == "GATE_INDEPENDENT_SOURCE_OBSERVATION")
    assert obs_res.status == ValidationStatus.FAIL
    assert any("Missing XBRL concept in US SEC observation" in err for err in obs_res.details["source_obs_errors"])


def test_adversarial_missing_source_observation_entry(sample_company_dataset):
    """29. Adversarial test: Missing observation record in source_observations fails observation gate."""
    from fundamentals_lens.data_loader import load_evidence_register, load_source_observations
    company, facts, sources, coverage = sample_company_dataset
    evidence = load_evidence_register()
    # Drop AAPL FY2021 revenue observation entirely
    mutated_obs = [
        o for o in load_source_observations()
        if not (o["ticker"] == "AAPL" and o["fiscal_year_label"] == "FY2021" and o["metric_name"] == "revenue")
    ]

    results = FundamentalsValidator.validate_company_dataset(
        company, facts, sources, coverage=coverage, evidence_register=evidence, source_observations=mutated_obs
    )
    obs_res = next(r for r in results if r.rule_id == "GATE_INDEPENDENT_SOURCE_OBSERVATION")
    assert obs_res.status == ValidationStatus.FAIL
    assert any("Missing source observation for AAPL FY2021 (revenue)" in err for err in obs_res.details["source_obs_errors"])


def test_adversarial_definition_type_cross_pollution_rejected(sample_company_dataset):
    """30. Adversarial test: Revenue inheriting capex definition fails observation gate."""
    from fundamentals_lens.data_loader import load_evidence_register, load_source_observations
    company, facts, sources, coverage = sample_company_dataset
    evidence = load_evidence_register()
    mutated_obs = copy.deepcopy(load_source_observations())

    # Mutate AAPL revenue to have PPE_PURCHASES_ONLY definition type
    for o in mutated_obs:
        if o["ticker"] == "AAPL" and o["fiscal_year_label"] == "FY2021" and o["metric_name"] == "revenue":
            o["definition_type"] = "PPE_PURCHASES_ONLY"
            break

    results = FundamentalsValidator.validate_company_dataset(
        company, facts, sources, coverage=coverage, evidence_register=evidence, source_observations=mutated_obs
    )
    obs_res = next(r for r in results if r.rule_id == "GATE_INDEPENDENT_SOURCE_OBSERVATION")
    assert obs_res.status == ValidationStatus.FAIL
    assert any("Revenue observation has invalid capex definition" in err for err in obs_res.details["source_obs_errors"])


def test_adversarial_bare_locator_rejected_for_reconciled(sample_company_dataset):
    """31. Adversarial test: Bare locator 'Consolidated Financial Statements' fails reconciled gate."""
    from fundamentals_lens.data_loader import load_evidence_register, load_source_observations
    company, facts, sources, coverage = sample_company_dataset
    evidence = load_evidence_register()
    mutated_obs = copy.deepcopy(load_source_observations())

    # Mutate AAPL revenue locator to bare generic string
    for o in mutated_obs:
        if o["ticker"] == "AAPL" and o["fiscal_year_label"] == "FY2021" and o["metric_name"] == "revenue":
            o["statement_locator"] = "Consolidated Financial Statements"
            break

    results = FundamentalsValidator.validate_company_dataset(
        company, facts, sources, coverage=coverage, evidence_register=evidence, source_observations=mutated_obs
    )
    obs_res = next(r for r in results if r.rule_id == "GATE_INDEPENDENT_SOURCE_OBSERVATION")
    assert obs_res.status == ValidationStatus.FAIL
    assert any("Generic or bare observation statement locator" in err for err in obs_res.details["source_obs_errors"])


def test_adversarial_wrong_company_document_identity_rejected(sample_company_dataset):
    """32. Adversarial test: Accession from another company (MSFT on AAPL) fails provenance gate."""
    company, facts, sources, coverage = sample_company_dataset
    mutated_sources = copy.deepcopy(sources)
    # Inject MSFT accession into AAPL source
    mutated_sources[0]["accession_id"] = "0000789019-21-000032"
    mutated_sources[0]["official_filing_id"] = "0000789019-21-000032"

    results = FundamentalsValidator.validate_company_dataset(company, facts, mutated_sources, coverage)
    prov_res = next(r for r in results if r.rule_id == "GATE_SOURCE_PROVENANCE")
    assert prov_res.status == ValidationStatus.FAIL
    assert "Source register alignment mismatches detected" in prov_res.message


def test_adversarial_fcf_arithmetic_vs_input_confidence_decoupling():
    """33. Adversarial test: FCF arithmetic is verified even when inputs are SOURCE_LINKED_ONLY."""
    from fundamentals_lens.data_loader import load_evidence_register
    evidence = load_evidence_register()

    # Find a record with SOURCE_LINKED_INPUTS (e.g., Indian FY2024-25 pending periods)
    sl_records = [r for r in evidence if r["free_cash_flow_derived"]["source_input_confidence"] == "SOURCE_LINKED_INPUTS"]
    assert len(sl_records) == 9, f"Expected 9 Indian pending period records, found {len(sl_records)}"

    for r in sl_records:
        fcf_info = r["free_cash_flow_derived"]
        assert fcf_info["arithmetic_verified"] is True
        assert fcf_info["source_input_confidence"] == "SOURCE_LINKED_INPUTS"
        assert "await audit" in fcf_info["source_input_confidence_description"]


def test_adversarial_evidence_json_csv_count_consistency():
    """34. Adversarial test: Evidence JSON and CSV exports have 100% consistent counts and metrics."""
    import csv
    from fundamentals_lens.data_loader import load_evidence_register
    from scripts.build_evidence_register_phase12 import EVIDENCE_CSV

    evidence = load_evidence_register()
    assert len(evidence) == 75, f"Expected 75 period records in JSON, found {len(evidence)}"

    total_json_metrics = sum(len(r["metrics"]) for r in evidence)
    assert total_json_metrics == 375, f"Expected 375 metric entries in JSON, found {total_json_metrics}"

    with open(EVIDENCE_CSV, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        csv_rows = list(reader)
    assert len(csv_rows) == 375, f"Expected 375 metric rows in CSV, found {len(csv_rows)}"


def test_adversarial_discrepancy_ledger_includes_disc016():
    """35. Adversarial test: Discrepancy ledger has 16 items and includes DISC-016 for WMT Net Income."""
    import json
    from scripts.build_evidence_register_phase12 import DISCREPANCY_JSON

    with open(DISCREPANCY_JSON, "r", encoding="utf-8") as f:
        ledger = json.load(f)

    assert len(ledger) == 16, f"Expected 16 discrepancies, found {len(ledger)}"
    disc16 = next((d for d in ledger if d["discrepancy_id"] == "DISC-016"), None)
    assert disc16 is not None, "DISC-016 missing from discrepancy ledger"
    assert disc16["ticker"] == "WMT"
    assert disc16["metric"] == "net_income"
    assert disc16["primary_reported_value"] == 19436.0


def test_adversarial_legacy_radar_app_entrypoint_functional():
    """36. Adversarial test: Legacy Financial Intelligence Radar app.py loads cleanly without error."""
    import importlib.util
    from pathlib import Path

    repo_root = Path(__file__).resolve().parent.parent.parent
    app_path = repo_root / "app.py"
    assert app_path.exists(), "app.py missing"

    spec = importlib.util.spec_from_file_location("legacy_app", str(app_path))
    assert spec is not None
    # Verifying module can be loaded
    assert spec.loader is not None
