import pytest
from fundamentals_lens.data_loader import load_financial_facts, load_companies
from fundamentals_lens.insights import NarrativeEngine, FinancialInsight
from fundamentals_lens.models import FinancialFact


def test_narrative_engine_canonical_companies():
    companies = load_companies()
    facts = load_financial_facts()
    facts_by_ticker = {}
    for f in facts:
        facts_by_ticker.setdefault(f.ticker, []).append(f)

    for c in companies:
        c_facts = facts_by_ticker[c.ticker]
        insights = NarrativeEngine.generate_company_insights(c_facts)
        
        assert len(insights) >= 4, f"Expected at least 4 insights for {c.ticker}"
        categories = {i.category for i in insights}
        assert "TOP_LINE_GROWTH" in categories
        assert "OPERATING_MARGINS" in categories
        assert "CASH_GENERATION" in categories
        assert "CASH_CONVERSION" in categories

        for i in insights:
            assert i.headline
            assert i.what_changed
            assert i.evidence
            assert i.why_it_matters
            assert i.what_to_investigate
            assert i.limitations


def test_narrative_engine_insufficient_data():
    single_fact = [
        FinancialFact(
            ticker="TEST", company_name="Test", peer_group_id="group_a_tech", country="US", currency="USD", unit="$M",
            scale_multiplier=1000000, fiscal_year=2024, fiscal_year_label="FY2024", period_start="2024-01-01",
            period_end="2024-12-31", statement_basis="CONSOLIDATED", revenue=100.0, operating_income=20.0,
            net_income=15.0, operating_cash_flow=18.0, capital_expenditure=5.0, source_id="S1", source_title="T1",
            source_url="http://sec.gov", filing_date="2025-01-01", statement_location="P1", accession_id="A1",
            reported_status="REPORTED", verification_status="VERIFIED"
        )
    ]
    insights = NarrativeEngine.generate_company_insights(single_fact)
    assert len(insights) == 1
    assert insights[0].category == "DATA_LIMITATION"
    assert "Insufficient" in insights[0].headline


def test_narrative_engine_loss_year_cash_conversion():
    facts = [
        FinancialFact(
            ticker="TEST", company_name="Test", peer_group_id="group_a_tech", country="US", currency="USD", unit="$M",
            scale_multiplier=1000000, fiscal_year=2023, fiscal_year_label="FY2023", period_start="2023-01-01",
            period_end="2023-12-31", statement_basis="CONSOLIDATED", revenue=100.0, operating_income=20.0,
            net_income=15.0, operating_cash_flow=18.0, capital_expenditure=5.0, source_id="S1", source_title="T1",
            source_url="http://sec.gov", filing_date="2024-01-01", statement_location="P1", accession_id="A1",
            reported_status="REPORTED", verification_status="VERIFIED"
        ),
        FinancialFact(
            ticker="TEST", company_name="Test", peer_group_id="group_a_tech", country="US", currency="USD", unit="$M",
            scale_multiplier=1000000, fiscal_year=2024, fiscal_year_label="FY2024", period_start="2024-01-01",
            period_end="2024-12-31", statement_basis="CONSOLIDATED", revenue=80.0, operating_income=-5.0,
            net_income=-10.0, operating_cash_flow=5.0, capital_expenditure=15.0, source_id="S2", source_title="T2",
            source_url="http://sec.gov", filing_date="2025-01-01", statement_location="P2", accession_id="A2",
            reported_status="REPORTED", verification_status="VERIFIED"
        )
    ]
    insights = NarrativeEngine.generate_company_insights(facts)
    conv_insight = next(i for i in insights if i.category == "CASH_CONVERSION")
    assert "Suppressed" in conv_insight.headline
    assert "Net loss" in conv_insight.evidence

    cash_insight = next(i for i in insights if i.category == "CASH_GENERATION")
    assert "Negative Free Cash Flow" in cash_insight.headline

    rev_insight = next(i for i in insights if i.category == "TOP_LINE_GROWTH")
    assert "Contraction" in rev_insight.headline
