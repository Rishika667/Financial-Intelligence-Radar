"""
Unit tests for deeper fundamental analysis engine (Workstream C).
Tests: CAGR with span guards, margin basis point shifts, operating leverage divergence,
FCF margin, Capex intensity, reinvestment rates, cumulative cash flows, margin volatility,
and growth consistency scoring.
"""

import pytest
from fundamentals_lens.models import FinancialFact, DerivedMetrics
from fundamentals_lens.metrics import (
    calculate_revenue_growth,
    calculate_operating_margin,
    calculate_margin_change_bps,
    calculate_fcf_margin,
    calculate_capex_intensity,
    calculate_reinvestment_rate,
    calculate_operating_leverage,
    calculate_cagr,
    calculate_margin_volatility,
    evaluate_growth_consistency,
    calculate_cumulative_cash_flows,
    compute_derived_metrics_for_company,
)


def test_calculate_margin_change_bps():
    # 17.5% from 15.2% is +2.3% = +230.0 bps
    assert calculate_margin_change_bps(17.5, 15.2) == 230.0
    # Compression: 10.0% from 12.5% is -2.5% = -250.0 bps
    assert calculate_margin_change_bps(10.0, 12.5) == -250.0
    # None handling
    assert calculate_margin_change_bps(None, 15.0) is None
    assert calculate_margin_change_bps(15.0, None) is None


def test_calculate_fcf_margin():
    assert calculate_fcf_margin(2000.0, 10000.0) == 20.0
    assert calculate_fcf_margin(-500.0, 5000.0) == -10.0
    # Zero or negative revenue guards
    assert calculate_fcf_margin(100.0, 0.0) is None
    assert calculate_fcf_margin(100.0, -50.0) is None
    assert calculate_fcf_margin(None, 1000.0) is None


def test_calculate_capex_intensity():
    assert calculate_capex_intensity(500.0, 10000.0) == 5.0
    assert calculate_capex_intensity(0.0, 10000.0) == 0.0
    # Revenue guards
    assert calculate_capex_intensity(100.0, 0.0) is None
    assert calculate_capex_intensity(100.0, -100.0) is None
    assert calculate_capex_intensity(None, 1000.0) is None


def test_calculate_reinvestment_rate():
    rate, reason = calculate_reinvestment_rate(300.0, 1000.0)
    assert rate == 30.0
    assert reason is None

    # OCF non-positive guard
    rate, reason = calculate_reinvestment_rate(300.0, -500.0)
    assert rate is None
    assert "non-positive" in reason

    rate, reason = calculate_reinvestment_rate(300.0, 0.0)
    assert rate is None
    assert "non-positive" in reason

    # Missing inputs
    rate, reason = calculate_reinvestment_rate(None, 1000.0)
    assert rate is None
    assert "Missing" in reason


def test_calculate_operating_leverage():
    # Operating Income grew 25%, Revenue grew 15% -> spread is +10.0%
    assert calculate_operating_leverage(25.0, 15.0) == 10.0
    # Operating Income grew 5%, Revenue grew 12% -> spread is -7.0%
    assert calculate_operating_leverage(5.0, 12.0) == -7.0
    assert calculate_operating_leverage(None, 10.0) is None


def test_calculate_cagr():
    # 100.0 to 200.0 over 4 intervals = (2.0)^0.25 - 1 = 18.92%
    cagr, reason = calculate_cagr(100.0, 200.0, 4)
    assert cagr == 18.92
    assert reason is None

    # 100.0 to 100.0 = 0.0%
    cagr, reason = calculate_cagr(100.0, 100.0, 4)
    assert cagr == 0.0

    # Non-positive start guard
    cagr, reason = calculate_cagr(-50.0, 100.0, 4)
    assert cagr is None
    assert "Base period value is non-positive" in reason

    cagr, reason = calculate_cagr(0.0, 100.0, 4)
    assert cagr is None
    assert "Base period value is non-positive" in reason

    # Non-positive end guard
    cagr, reason = calculate_cagr(100.0, -10.0, 4)
    assert cagr is None
    assert "End period value is non-positive" in reason

    # Zero intervals guard
    cagr, reason = calculate_cagr(100.0, 200.0, 0)
    assert cagr is None
    assert "at least 1 interval" in reason


def test_calculate_margin_volatility():
    # Margins: 10%, 12%, 14% -> mean 12, var ((4+0+4)/2)=4, std 2.0
    assert calculate_margin_volatility([10.0, 12.0, 14.0]) == 2.0
    # Fewer than 2 periods -> None
    assert calculate_margin_volatility([10.0]) is None
    assert calculate_margin_volatility([]) is None


def test_evaluate_growth_consistency():
    res = evaluate_growth_consistency([10.0, 12.0, 8.0, 15.0])
    assert res["label"] == "CONSISTENT_EXPANSION"
    assert res["positive_years"] == 4
    assert res["total_years"] == 4

    res = evaluate_growth_consistency([10.0, -2.0, 8.0, 15.0])
    assert res["label"] == "MOSTLY_POSITIVE"
    assert res["positive_years"] == 3

    res = evaluate_growth_consistency([-5.0, -2.0, -8.0, -1.0])
    assert res["label"] == "CONSISTENT_CONTRACTION"

    res = evaluate_growth_consistency([10.0, -5.0, -2.0, 8.0])
    assert res["label"] == "CYCLICAL_MIXED"


def test_calculate_cumulative_cash_flows():
    facts = [
        FinancialFact(
            ticker="TEST", company_name="Test Corp", peer_group_id="test",
            country="US", currency="USD", unit="$ Millions", scale_multiplier=1000000,
            fiscal_year=2022, fiscal_year_label="FY2022", period_start="2021-01-01", period_end="2021-12-31",
            statement_basis="CONSOLIDATED", revenue=1000.0, operating_income=200.0, net_income=150.0,
            operating_cash_flow=250.0, capital_expenditure=50.0, source_id="s1", source_title="t1",
            source_url="http", filing_date="2022-02-01", statement_location="loc", accession_id="acc1",
            reported_status="AUDITED", verification_status="VERIFIED"
        ),
        FinancialFact(
            ticker="TEST", company_name="Test Corp", peer_group_id="test",
            country="US", currency="USD", unit="$ Millions", scale_multiplier=1000000,
            fiscal_year=2023, fiscal_year_label="FY2023", period_start="2022-01-01", period_end="2022-12-31",
            statement_basis="CONSOLIDATED", revenue=1200.0, operating_income=240.0, net_income=180.0,
            operating_cash_flow=300.0, capital_expenditure=60.0, source_id="s2", source_title="t2",
            source_url="http", filing_date="2023-02-01", statement_location="loc", accession_id="acc2",
            reported_status="AUDITED", verification_status="VERIFIED"
        ),
    ]

    res = calculate_cumulative_cash_flows(facts)
    assert res["cumulative_ocf"] == 550.0
    assert res["cumulative_capex"] == 110.0
    assert res["cumulative_fcf"] == 440.0
    assert res["cumulative_reinvestment_pct"] == 20.0  # 110 / 550 * 100
    assert res["periods_included"] == 2


def test_compute_derived_metrics_includes_deeper_fields():
    facts = [
        FinancialFact(
            ticker="DEMO", company_name="Demo Corp", peer_group_id="demo",
            country="US", currency="USD", unit="$ Millions", scale_multiplier=1000000,
            fiscal_year=2021, fiscal_year_label="FY2021", period_start="2020-01-01", period_end="2020-12-31",
            statement_basis="CONSOLIDATED", revenue=1000.0, operating_income=100.0, net_income=80.0,
            operating_cash_flow=150.0, capital_expenditure=30.0, source_id="s1", source_title="t1",
            source_url="http", filing_date="2021-02-01", statement_location="loc", accession_id="acc1",
            reported_status="AUDITED", verification_status="VERIFIED"
        ),
        FinancialFact(
            ticker="DEMO", company_name="Demo Corp", peer_group_id="demo",
            country="US", currency="USD", unit="$ Millions", scale_multiplier=1000000,
            fiscal_year=2022, fiscal_year_label="FY2022", period_start="2021-01-01", period_end="2021-12-31",
            statement_basis="CONSOLIDATED", revenue=1200.0, operating_income=150.0, net_income=120.0,
            operating_cash_flow=200.0, capital_expenditure=40.0, source_id="s2", source_title="t2",
            source_url="http", filing_date="2022-02-01", statement_location="loc", accession_id="acc2",
            reported_status="AUDITED", verification_status="VERIFIED"
        ),
    ]

    derived = compute_derived_metrics_for_company(facts)
    assert len(derived) == 2

    # Period 1 (FY2021): baseline period
    assert derived[0].revenue_growth_yoy is None
    assert derived[0].operating_margin == 10.0
    assert derived[0].operating_margin_change_bps is None
    assert derived[0].fcf_margin == 12.0  # (150-30)/1000 = 12%
    assert derived[0].capex_intensity == 3.0  # 30/1000 = 3%
    assert derived[0].reinvestment_rate == 20.0  # 30/150 = 20%

    # Period 2 (FY2022): YoY growth
    assert derived[1].revenue_growth_yoy == 20.0  # (1200-1000)/1000
    assert derived[1].operating_margin == 12.5  # 150/1200 = 12.5%
    # Margin shifted from 10.0% to 12.5% = +250.0 bps
    assert derived[1].operating_margin_change_bps == 250.0
    # Operating income grew from 100 to 150 = +50.0%, Revenue grew +20.0% -> leverage spread = +30.0%
    assert derived[1].operating_leverage == 30.0
    assert derived[1].fcf_margin == 13.33  # (200-40)/1200 = 160/1200 = 13.33%
    assert derived[1].capex_intensity == 3.33  # 40/1200 = 3.33%
    assert derived[1].reinvestment_rate == 20.0  # 40/200 = 20%
