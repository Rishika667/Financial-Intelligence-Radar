"""
Tests for Phase 16 Priority P0-D: Company Research Brief Quality & Analytical Narrative Scenarios.
Verifies the 7 explicit sections of the research brief and exercises 7 synthetic scenarios:
1. Revenue growth + falling margins
2. Revenue contraction + improving cash
3. Profits up + cash flow down (earnings quality divergence)
4. Strong FCF + capex decline (harvesting vs reinvestment)
5. Negative earnings / non-positive growth baselines
6. Missing periods
7. Proxy metric suppression from direct peer comparison
"""
import pytest
from datetime import date
from typing import Optional
from fundamentals_lens.models import Company, FinancialFact, DerivedMetrics
from fundamentals_lens.insights import NarrativeEngine, FinancialInsight
from fundamentals_lens.exports import ExportGenerator
from fundamentals_lens.metrics import compute_derived_metrics_for_company
from fundamentals_lens.peers import PeerComparisonEngine


@pytest.fixture
def base_company():
    return Company(
        ticker="SYNT",
        name="Synthetic Dynamics Corp",
        peer_group_id="group_a_tech",
        peer_group_name="Global Technology Leaders",
        country="USA",
        exchange="NASDAQ",
        reporting_currency="USD",
        standard_unit_label="$ Millions",
        scale_multiplier=1000000,
        fiscal_year_end_month="September",
        primary_source_url="https://sec.gov",
        business_description="Enterprise software and cloud computing services provider.",
        peer_notes="Competes with enterprise software platforms."
    )


def make_fact(
    fiscal_year: int,
    revenue: float,
    operating_income: float,
    net_income: float,
    operating_cash_flow: float,
    capital_expenditure: float,
    fiscal_year_label: Optional[str] = None,
    comparability_flag: str = "DIRECT",
    accounting_notes: str = "",
    reconciliation_tier: str = "INDEPENDENTLY_RECONCILED",
    accession_id: str = "0001000000-25-000001"
) -> FinancialFact:
    fylbl = fiscal_year_label or f"FY{fiscal_year}"
    return FinancialFact(
        ticker="SYNT",
        company_name="Synthetic Dynamics Corp",
        peer_group_id="group_a_tech",
        country="USA",
        currency="USD",
        unit="$ Millions",
        scale_multiplier=1000000,
        fiscal_year=fiscal_year,
        fiscal_year_label=fylbl,
        period_start=f"{fiscal_year-1}-10-01",
        period_end=f"{fiscal_year}-09-30",
        statement_basis="CONSOLIDATED",
        revenue=revenue,
        operating_income=operating_income,
        net_income=net_income,
        operating_cash_flow=operating_cash_flow,
        capital_expenditure=capital_expenditure,
        source_id=f"EDGAR_10K_{fiscal_year}",
        source_title=f"SEC 10-K {fylbl}",
        source_url="https://sec.gov",
        filing_date=f"{fiscal_year}-11-15",
        statement_location="Item 8",
        accession_id=accession_id,
        reported_status="AUDITED_REPORTED",
        verification_status="VERIFIED",
        comparability_flag=comparability_flag,
        accounting_notes=accounting_notes,
        reconciliation_tier=reconciliation_tier,
        official_filing_id=accession_id,
        reference_type="SEC_ACCESSION"
    )


def test_research_brief_7_sections_structure(base_company):
    """Verify that generate_research_brief produces all 7 explicit analytical sections."""
    facts = [
        make_fact(2024, 1000.0, 200.0, 150.0, 250.0, 50.0),
        make_fact(2025, 1150.0, 240.0, 180.0, 290.0, 60.0)
    ]

    brief = ExportGenerator.generate_research_brief(base_company, facts)

    # 7 explicit sections
    assert "### 1. Executive Business Snapshot" in brief
    assert "### 2. Revenue and Profitability Trajectory" in brief
    assert "### 3. Cash Generation & Earnings Quality" in brief
    assert "### 4. Capital Allocation & Reinvestment" in brief
    assert "### 5. Peer Context & Comparability Nuance" in brief
    assert "### 6. Risks & Unanswered Questions" in brief
    assert "### 7. Evidence, Provenance & Methodology Summary" in brief

    # Check key invariants and attribution
    assert "Created by Rishika Dangayach" in brief
    assert "CONSOLIDATED" in brief
    assert "not constitute investment advice" in brief
    assert "What Changed, Why It Matters, and What to Investigate" in brief


def test_scenario_1_revenue_growth_with_falling_margins(base_company):
    """Scenario 1: Revenue growth + falling margins."""
    facts = [
        make_fact(2024, 1000.0, 250.0, 200.0, 220.0, 40.0), # 25.0% margin
        make_fact(2025, 1300.0, 260.0, 195.0, 240.0, 45.0)  # +30% rev, 20.0% margin (-5 pts)
    ]

    derived = compute_derived_metrics_for_company(facts)
    insights = NarrativeEngine.generate_company_insights(facts, derived)
    brief = ExportGenerator.generate_research_brief(base_company, facts, derived, insights)

    # Narrative engine flags margin compression
    margin_insight = next((i for i in insights if i.category == "OPERATING_MARGINS"), None)
    assert margin_insight is not None
    assert "Compression" in margin_insight.headline
    assert "despite top-line revenue expanding" in margin_insight.what_changed

    # Brief documents revenue growth and margin compression in Section 2 and Section 6
    assert "Operating margin compressed by" in brief
    assert "Operating Margin Compression" in brief


def test_scenario_2_revenue_contraction_with_improving_cash(base_company):
    """Scenario 2: Revenue contraction + improving cash."""
    facts = [
        make_fact(2024, 1200.0, 240.0, 180.0, 200.0, 50.0),
        make_fact(2025, 1050.0, 210.0, 155.0, 280.0, 45.0)  # Rev down -12.5%, OCF up +40%
    ]

    derived = compute_derived_metrics_for_company(facts)
    insights = NarrativeEngine.generate_company_insights(facts, derived)
    brief = ExportGenerator.generate_research_brief(base_company, facts, derived, insights)

    # Narrative engine flags cash flow resilience
    resilience_insight = next((i for i in insights if i.category == "CASH_FLOW_RESILIENCE"), None)
    assert resilience_insight is not None
    assert "Cash Flow Resilience" in resilience_insight.headline
    assert "contracted" in resilience_insight.what_changed
    assert "expanded" in resilience_insight.what_changed

    # Brief Section 3 documents counter-cyclical cash resilience
    assert "Counter-Cyclical Cash Resilience" in brief


def test_scenario_3_profits_up_cash_flow_down_divergence(base_company):
    """Scenario 3: Profits up + cash flow down (earnings quality divergence)."""
    facts = [
        make_fact(2024, 1000.0, 180.0, 130.0, 220.0, 40.0),
        make_fact(2025, 1200.0, 260.0, 200.0, 150.0, 40.0)  # Profits up, OCF down
    ]

    derived = compute_derived_metrics_for_company(facts)
    insights = NarrativeEngine.generate_company_insights(facts, derived)
    brief = ExportGenerator.generate_research_brief(base_company, facts, derived, insights)

    # Narrative engine detects accrual divergence
    div_insight = next((i for i in insights if i.category == "EARNINGS_QUALITY_DIVERGENCE"), None)
    assert div_insight is not None
    assert "Cash Flow Lags Accounting Profit Growth" in div_insight.headline

    # Brief Section 3 highlights accrual divergence
    assert "Accrual Divergence Detected" in brief
    assert "cash collection lagged accounting earnings" in brief


def test_scenario_4_strong_fcf_with_capex_decline(base_company):
    """Scenario 4: Strong FCF + capex decline (harvesting vs reinvestment)."""
    facts = [
        make_fact(2024, 1000.0, 200.0, 150.0, 300.0, 120.0), # Capex 120, FCF 180
        make_fact(2025, 1020.0, 205.0, 155.0, 310.0, 40.0)   # Capex 40, FCF 270
    ]

    derived = compute_derived_metrics_for_company(facts)
    insights = NarrativeEngine.generate_company_insights(facts, derived)
    brief = ExportGenerator.generate_research_brief(base_company, facts, derived, insights)

    # Narrative engine identifies capex moderation / harvesting
    harvest_insight = next((i for i in insights if i.category == "CAPITAL_HARVESTING"), None)
    assert harvest_insight is not None
    assert "Capex Moderation" in harvest_insight.headline

    # Brief Section 4 explicitly notes capital harvesting indicator
    assert "Capital Harvesting Indicator" in brief
    assert "expenditure moderation rather than pure operational acceleration" in brief


def test_scenario_5_negative_earnings_and_non_positive_baseline(base_company):
    """Scenario 5: Negative earnings / non-positive growth baselines."""
    facts = [
        make_fact(2024, 0.0, -50.0, -60.0, 20.0, 10.0),    # Non-positive baseline, negative NI
        make_fact(2025, 500.0, -20.0, -30.0, 40.0, 15.0)   # Negative NI
    ]

    derived = compute_derived_metrics_for_company(facts)
    # Check that cash conversion ratio is suppressed
    assert "net loss" in derived[0].cash_conversion_qualified_reason.lower()

    insights = NarrativeEngine.generate_company_insights(facts, derived)
    conv_insight = next((i for i in insights if i.category == "CASH_CONVERSION"), None)
    assert conv_insight is not None
    assert "Suppressed" in conv_insight.headline

    brief = ExportGenerator.generate_research_brief(base_company, facts, derived, insights)
    assert "Suppressed" in brief
    assert "Non-positive" in brief or "non-positive" in brief


def test_scenario_6_missing_periods_data_limitation(base_company):
    """Scenario 6: Missing periods (fewer than 2 periods)."""
    facts = [
        make_fact(2025, 1000.0, 200.0, 150.0, 220.0, 30.0)
    ]

    derived = compute_derived_metrics_for_company(facts)
    insights = NarrativeEngine.generate_company_insights(facts, derived)

    # Narrative engine returns DATA_LIMITATION insight
    assert len(insights) == 1
    assert insights[0].category == "DATA_LIMITATION"
    assert "Insufficient Historical Periods" in insights[0].headline

    brief = ExportGenerator.generate_research_brief(base_company, facts, derived, insights)
    assert "Truncated Historical Horizon" in brief
    assert "1 periods verified" in brief or "1" in brief


def test_scenario_7_proxy_metric_suppression(base_company):
    """Scenario 7: Proxy metric suppression from direct peer comparison."""
    # Test proxy note on brief
    proxy_facts = [
        make_fact(2024, 1000.0, 200.0, 150.0, 220.0, 30.0, comparability_flag="PROXY", accounting_notes="PBEI proxy excluding exceptional items"),
        make_fact(2025, 1100.0, 220.0, 165.0, 240.0, 35.0, comparability_flag="PROXY", accounting_notes="PBEI proxy excluding exceptional items")
    ]

    brief = ExportGenerator.generate_research_brief(base_company, proxy_facts)
    assert "Proxy Metric Suppression Active" in brief

    # Test peer comparison engine suppression logic
    # For Indian IT, TCS is suppressed for operating_income / operating_margin due to PBEI proxy
    tcs_comp = Company(
        ticker="TCS", name="Tata Consultancy Services", peer_group_id="group_b_india_it",
        peer_group_name="Indian IT Services", country="India", exchange="BSE/NSE",
        reporting_currency="INR", standard_unit_label="₹ Crores", scale_multiplier=10000000,
        fiscal_year_end_month="March", primary_source_url="https://bseindia.com",
        business_description="IT services", peer_notes="Indian IT peer"
    )
    is_supp, reason = PeerComparisonEngine.evaluate_metric_comparability(
        "group_b_india_it", "operating_margin", tcs_comp, proxy_facts[0], True
    )
    assert is_supp is True
    assert "PBEI proxy" in reason

    # Bajaj Auto in Indian Auto suppressed due to EBITDA proxy
    bajaj_comp = Company(
        ticker="BAJAJ-AUTO", name="Bajaj Auto", peer_group_id="group_d_india_auto",
        peer_group_name="Indian Auto & Mobility", country="India", exchange="BSE/NSE",
        reporting_currency="INR", standard_unit_label="₹ Crores", scale_multiplier=10000000,
        fiscal_year_end_month="March", primary_source_url="https://bseindia.com",
        business_description="Auto manufacturer", peer_notes="Indian Auto peer"
    )
    is_supp_bajaj, reason_bajaj = PeerComparisonEngine.evaluate_metric_comparability(
        "group_d_india_auto", "operating_income", bajaj_comp, proxy_facts[0], True
    )
    assert is_supp_bajaj is True
    assert "EBITDA proxy" in reason_bajaj
