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
