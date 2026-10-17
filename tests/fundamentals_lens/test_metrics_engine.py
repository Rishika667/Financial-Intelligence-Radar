import pytest
from fundamentals_lens.metrics import (
    calculate_revenue_growth,
    calculate_operating_margin,
    calculate_net_margin,
    calculate_free_cash_flow,
    calculate_cash_conversion,
    compute_derived_metrics_for_company
)
from fundamentals_lens.models import FinancialFact


def test_revenue_growth_calculations():
    # Normal positive growth
    assert calculate_revenue_growth(110.0, 100.0) == 10.0
    # Negative growth (contraction)
    assert calculate_revenue_growth(80.0, 100.0) == -20.0
    # Missing current
    assert calculate_revenue_growth(None, 100.0) is None
    # Missing prior
    assert calculate_revenue_growth(100.0, None) is None
    # Zero prior
    assert calculate_revenue_growth(100.0, 0.0) is None
    # Negative prior
    assert calculate_revenue_growth(100.0, -50.0) is None


def test_margins_calculations():
    # Operating margin
    assert calculate_operating_margin(25.0, 100.0) == 25.0
    assert calculate_operating_margin(-10.0, 100.0) == -10.0
    assert calculate_operating_margin(25.0, 0.0) is None
    assert calculate_operating_margin(25.0, -100.0) is None
    assert calculate_operating_margin(None, 100.0) is None
    assert calculate_operating_margin(25.0, None) is None
    
    # Net margin
    assert calculate_net_margin(15.0, 100.0) == 15.0
    assert calculate_net_margin(-5.0, 100.0) == -5.0
    assert calculate_net_margin(15.0, 0.0) is None


def test_free_cash_flow_calculation():
    # OCF - Capex
    assert calculate_free_cash_flow(100.0, 30.0) == 70.0
    assert calculate_free_cash_flow(50.0, 80.0) == -30.0
    assert calculate_free_cash_flow(None, 30.0) is None
    assert calculate_free_cash_flow(100.0, None) is None


def test_cash_conversion_edge_cases():
    # Normal positive earnings
    conv, reason = calculate_cash_conversion(120.0, 100.0)
    assert conv == 1.2
    assert reason is None
    
    # Negative net income (net loss) must be suppressed
    conv_loss, reason_loss = calculate_cash_conversion(50.0, -20.0)
    assert conv_loss is None
    assert "Net loss" in reason_loss
    
    # Zero net income
    conv_zero, reason_zero = calculate_cash_conversion(50.0, 0.0)
    assert conv_zero is None
    assert "zero" in reason_zero
    
    # Near-zero distortion (< 1.0)
    conv_dist, reason_dist = calculate_cash_conversion(50.0, 0.5)
    assert conv_dist is None
    assert "Near-zero" in reason_dist
    
    # Missing inputs
    conv_miss, reason_miss = calculate_cash_conversion(None, 100.0)
    assert conv_miss is None


def test_compute_derived_metrics_synthetic():
    # 3 periods synthetic fixture
    synthetic_facts = [
        FinancialFact(
            ticker="TEST", company_name="Test Corp", peer_group_id="group_a_tech", country="US", currency="USD", unit="$M", scale_multiplier=1000000,
            fiscal_year=2021, fiscal_year_label="FY2021", period_start="2020-01-01", period_end="2020-12-31", statement_basis="CONSOLIDATED",
            revenue=1000.0, operating_income=200.0, net_income=150.0, operating_cash_flow=180.0, capital_expenditure=50.0,
            source_id="S1", source_title="T1", source_url="https://sec.gov", filing_date="2021-01-01", statement_location="P1", accession_id="A1",
            reported_status="REPORTED", verification_status="VERIFIED"
        ),
        FinancialFact(
            ticker="TEST", company_name="Test Corp", peer_group_id="group_a_tech", country="US", currency="USD", unit="$M", scale_multiplier=1000000,
            fiscal_year=2022, fiscal_year_label="FY2022", period_start="2021-01-01", period_end="2021-12-31", statement_basis="CONSOLIDATED",
            revenue=1200.0, operating_income=300.0, net_income=240.0, operating_cash_flow=250.0, capital_expenditure=70.0,
            source_id="S2", source_title="T2", source_url="https://sec.gov", filing_date="2022-01-01", statement_location="P2", accession_id="A2",
            reported_status="REPORTED", verification_status="VERIFIED"
        ),
        FinancialFact(
            ticker="TEST", company_name="Test Corp", peer_group_id="group_a_tech", country="US", currency="USD", unit="$M", scale_multiplier=1000000,
            fiscal_year=2023, fiscal_year_label="FY2023", period_start="2022-01-01", period_end="2022-12-31", statement_basis="CONSOLIDATED",
            revenue=1500.0, operating_income=400.0, net_income=-50.0, operating_cash_flow=100.0, capital_expenditure=120.0,
            source_id="S3", source_title="T3", source_url="https://sec.gov", filing_date="2023-01-01", statement_location="P3", accession_id="A3",
            reported_status="REPORTED", verification_status="VERIFIED"
        )
    ]
    
    derived = compute_derived_metrics_for_company(synthetic_facts)
    assert len(derived) == 3
    
    # Year 1: No YoY growth
    assert derived[0].revenue_growth_yoy is None
    assert derived[0].operating_margin == 20.0
    assert derived[0].net_margin == 15.0
    assert derived[0].free_cash_flow == 130.0
    assert derived[0].cash_conversion_ratio == 1.2
    
    # Year 2: 20% growth
    assert derived[1].revenue_growth_yoy == 20.0
    assert derived[1].operating_margin == 25.0
    assert derived[1].net_margin == 20.0
    assert derived[1].free_cash_flow == 180.0
    assert derived[1].cash_conversion_ratio == round(250.0 / 240.0, 2)
    
    # Year 3: Loss year
    assert derived[2].revenue_growth_yoy == 25.0
    assert derived[2].net_margin == round((-50.0 / 1500.0) * 100.0, 2)
    assert derived[2].free_cash_flow == -20.0
    assert derived[2].cash_conversion_ratio is None
    assert "Net loss" in derived[2].cash_conversion_qualified_reason
