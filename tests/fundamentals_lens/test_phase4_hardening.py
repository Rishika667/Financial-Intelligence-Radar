"""
Phase 4 Regression Test Suite for Fundamentals Lens:
- Target (TGT) fiscal-period reconciliation and SEC filing accuracy
- Generic URL elimination and source lineage validation
- Operating income and capex accounting metric definitions
- Coverage integrity, semantic status codes, and missing coverage handling
- Missing data non-coercion guards (valid disclosed zero vs unexplained zero)
- Insight engine chronological sorting, baseline protection, and cash conversion suppression
- Peer comparison with differing fiscal calendars and index normalization
- Export consistency (CSV and Markdown brief)
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
from fundamentals_lens.insights import NarrativeEngine
from fundamentals_lens.peers import PeerComparisonEngine, PEER_GROUP_METADATA
from fundamentals_lens.exports import ExportGenerator
from fundamentals_lens.metrics import compute_derived_metrics_for_company


def test_target_reconciliation_integrity():
    """Verify Target (TGT) 5-year chronological periods, values, and accessions."""
    facts = get_facts_for_company("TGT")
    assert len(facts) == 5, f"Expected 5 periods for TGT, found {len(facts)}"
    
    # Chronological fiscal years
    years = [f.fiscal_year for f in facts]
    assert years == [2021, 2022, 2023, 2024, 2025]
    
    # Check labels
    labels = [f.fiscal_year_label for f in facts]
    assert labels == ["FY2021", "FY2022", "FY2023", "FY2024", "FY2025"]
    
    # Unique period end dates
    period_ends = [f.period_end for f in facts]
    assert len(set(period_ends)) == 5
    assert period_ends == ["2022-01-29", "2023-01-28", "2024-02-03", "2025-02-01", "2026-01-31"]
    
    # Unique accession numbers
    accessions = [f.accession_id for f in facts]
    assert len(set(accessions)) == 5
    assert "0000027419-22-000007" in accessions
    assert "0000027419-23-000014" in accessions
    assert "0000027419-24-000032" in accessions
    assert "0000027419-25-000018" in accessions
    assert "0000027419-26-000016" in accessions
    
    # Official 10-K reported figures
    fact_map = {f.fiscal_year: f for f in facts}
    assert fact_map[2021].revenue == 106005.0
    assert fact_map[2021].operating_income == 8946.0
    assert fact_map[2021].net_income == 6946.0
    
    assert fact_map[2022].revenue == 109120.0
    assert fact_map[2022].operating_income == 3848.0
    assert fact_map[2022].net_income == 2780.0
    
    assert fact_map[2023].revenue == 107412.0
    # Reconciled to Form 10-K Consolidated Statements of Operations (DISC-002)
    assert fact_map[2023].operating_income == 5707.0
    assert fact_map[2023].net_income == 4138.0
    
    assert fact_map[2024].revenue == 106566.0
    assert fact_map[2024].operating_income == 5566.0
    assert fact_map[2024].net_income == 4091.0
    
    assert fact_map[2025].revenue == 104780.0
    assert fact_map[2025].operating_income == 5117.0
    assert fact_map[2025].net_income == 3705.0
    
    # Coverage report record for Target
    coverage = load_coverage_report()
    tgt_cov = next((c for c in coverage if c["ticker"] == "TGT"), None)
    assert tgt_cov is not None
    assert tgt_cov["verified_periods"] == ["FY2021", "FY2022", "FY2023", "FY2024", "FY2025"]
    assert tgt_cov["latest_verified_period"] == "FY2025"
    assert tgt_cov["target_horizon_period"] == "FY2026"
    assert tgt_cov["target_period_status_code"] == 1
    assert tgt_cov["overall_coverage_status"] == "5_PERIODS_VERIFIED_TARGET_HORIZON_PENDING"


def test_generic_urls_elimination():
    """Verify generic browse/search URLs are replaced with specific documents."""
    facts = load_financial_facts()
    sources = load_source_register()
    
    forbidden_snippets = ["sec.gov/edgar/browse"]
    for f in facts:
        for s in forbidden_snippets:
            assert s not in f.source_url.lower(), f"Fact {f.ticker} {f.fiscal_year} has generic URL: {f.source_url}"
            
    for src in sources:
        for s in forbidden_snippets:
            assert s not in src["source_url"].lower(), f"Source {src['source_id']} has generic URL: {src['source_url']}"
            
    # Check Indian company specific document links
    tcs_sources = [s for s in sources if s["ticker"] == "TCS"]
    for s in tcs_sources:
        assert ".pdf" in s["source_url"].lower() or "annual-report" in s["source_url"].lower()


def test_metric_definitions_coverage():
    """Verify all 75 sources have documented metric definitions for operating income and capex."""
    sources = load_source_register()
    assert len(sources) == 75
    
    allowed_oi_types = {"US_GAAP_OPERATING_INCOME", "IND_AS_EBIT_OPERATING_PROFIT", "IND_AS_PBEI_PROXY"}
    allowed_capex_types = {"PPE_PURCHASES_ONLY", "PPE_AND_INTANGIBLES", "PPE_AND_CWIP"}
    
    for s in sources:
        assert "metric_definitions" in s, f"Source {s['source_id']} missing metric_definitions"
        md = s["metric_definitions"]
        assert md["operating_income_type"] in allowed_oi_types, f"Invalid operating_income_type in {s['source_id']}"
        assert md["capex_type"] in allowed_capex_types, f"Invalid capex_type in {s['source_id']}"
        assert len(md["operating_income_note"]) > 10
        assert len(md["capex_note"]) > 10


def test_disclosed_zero_vs_unexplained_zero():
    """Verify non-coercion gate passes valid disclosed zero capex and fails unexplained zeroes."""
    facts = get_facts_for_company("AAPL")
    
    # Case 1: Unexplained zero capex fails
    corrupt_capex = copy.deepcopy(facts)
    corrupt_capex[0].capital_expenditure = 0.0
    corrupt_capex[0].notes = ""
    res1 = FundamentalsValidator._check_non_coercion_to_zero(corrupt_capex)
    assert res1.status == ValidationStatus.FAIL
    assert "Potential synthetic zero" in res1.message
    
    # Case 2: Documented disclosed zero capex passes
    disclosed_capex = copy.deepcopy(facts)
    disclosed_capex[0].capital_expenditure = 0.0
    disclosed_capex[0].notes = "Disclosed zero capex for the period in primary financial statements."
    res2 = FundamentalsValidator._check_non_coercion_to_zero(disclosed_capex)
    assert res2.status == ValidationStatus.PASS
    assert "disclosed zeroes verified" in res2.message
    
    # Case 3: Unexplained zero revenue fails
    corrupt_rev = copy.deepcopy(facts)
    corrupt_rev[0].revenue = 0.0
    corrupt_rev[0].notes = ""
    res3 = FundamentalsValidator._check_non_coercion_to_zero(corrupt_rev)
    assert res3.status == ValidationStatus.FAIL


def test_insights_chronological_ordering():
    """Verify NarrativeEngine produces identical, correct output even when input facts are reversed."""
    facts = get_facts_for_company("AAPL")
    reversed_facts = list(reversed(facts))
    
    insights_normal = NarrativeEngine.generate_company_insights(facts)
    insights_reversed = NarrativeEngine.generate_company_insights(reversed_facts)
    
    assert len(insights_normal) == len(insights_reversed)
    for in_norm, in_rev in zip(insights_normal, insights_reversed):
        assert in_norm.headline == in_rev.headline
        assert in_norm.evidence == in_rev.evidence


def test_insights_revenue_baseline_guard():
    """Verify revenue trajectory insight gracefully handles zero/negative baselines."""
    facts = copy.deepcopy(get_facts_for_company("AAPL"))
    facts[0].revenue = 0.0  # Zero base revenue
    
    derived = compute_derived_metrics_for_company(facts)
    insight = NarrativeEngine._analyze_revenue_trajectory(facts, derived)
    assert insight is not None
    assert "Non-positive baseline" in insight.evidence


def test_insights_cash_conversion_suppression():
    """Verify cash conversion is suppressed when net income is negative."""
    facts = copy.deepcopy(get_facts_for_company("AAPL"))
    facts[-1].net_income = -500.0  # Net loss
    
    derived = compute_derived_metrics_for_company(facts)
    insight = NarrativeEngine._analyze_cash_conversion(facts, derived)
    assert insight is not None
    assert "Suppressed" in insight.headline


def test_peer_comparison_differing_fiscal_periods():
    """Verify peer comparison handles retail group with differing calendar windows (WMT/COST vs TGT)."""
    companies = load_companies()
    facts = load_financial_facts()
    facts_by_ticker = {}
    for f in facts:
        facts_by_ticker.setdefault(f.ticker, []).append(f)
        
    matrix = PeerComparisonEngine.build_peer_comparison_matrix(
        companies, facts_by_ticker, "group_e_us_retail", "revenue"
    )
    assert "error" not in matrix
    assert matrix["group_id"] == "group_e_us_retail"
    assert len(matrix["series"]) == 3
    assert matrix.get("metric_note") is None  # Revenue doesn't need OI note
    
    # Check operating income note
    oi_matrix = PeerComparisonEngine.build_peer_comparison_matrix(
        companies, facts_by_ticker, "group_e_us_retail", "operating_income"
    )
    assert oi_matrix.get("metric_note") is not None
    assert "US GAAP Operating Income" in oi_matrix["metric_note"]
    
    # Check indexed peer matrix
    idx_matrix = PeerComparisonEngine.build_indexed_peer_matrix(
        companies, facts_by_ticker, "group_e_us_retail", "revenue"
    )
    assert "error" not in idx_matrix
    assert idx_matrix["base_year"] == 2022  # Common base year across 2022-2026 and 2021-2025


def test_export_generator_integrity():
    """Verify CSV and Markdown brief generation for Target (TGT)."""
    comp = get_company_by_ticker("TGT")
    facts = get_facts_for_company("TGT")
    
    # Test CSV Export
    csv_str = ExportGenerator.generate_company_csv(comp, facts)
    assert "TGT" in csv_str
    assert "FY2021" in csv_str
    assert "FY2025" in csv_str
    assert "0000027419-26-000016" in csv_str
    lines = csv_str.strip().split("\r\n") if "\r\n" in csv_str else csv_str.strip().split("\n")
    assert len(lines) == 6  # 1 header + 5 period rows
    
    # Test Markdown Research Brief
    brief = ExportGenerator.generate_research_brief(comp, facts)
    assert "# FUNDAMENTALS LENS — FINANCIAL RESEARCH BRIEF" in brief
    assert "Target Corporation (TGT)" in brief
    assert "Latest Verified Period:** FY2025" in brief
    assert "FY2021" in brief and "FY2025" in brief
    assert "0000027419-26-000016" in brief
    assert "Disclaimer:" in brief


def test_coverage_report_truthfulness():
    """Verify coverage report records 12 target included and 3 target pending companies."""
    coverage = load_coverage_report()
    code_0 = [c for c in coverage if c["target_period_status_code"] == 0]
    code_1 = [c for c in coverage if c["target_period_status_code"] == 1]
    
    assert len(code_0) == 12
    assert len(code_1) == 3
    
    pending_tickers = {c["ticker"] for c in code_1}
    assert pending_tickers == {"AAPL", "GOOGL", "TGT"}
    
    for c in code_0:
        assert c["overall_coverage_status"] == "5_PERIODS_VERIFIED_TARGET_HORIZON_INCLUDED"
    for c in code_1:
        assert c["overall_coverage_status"] == "5_PERIODS_VERIFIED_TARGET_HORIZON_PENDING"
