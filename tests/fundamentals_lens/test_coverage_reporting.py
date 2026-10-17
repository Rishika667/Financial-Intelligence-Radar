import pytest
from fundamentals_lens.data_loader import load_coverage_report, load_companies


def test_coverage_report_all_companies_represented():
    coverage = load_coverage_report()
    companies = load_companies()
    
    assert len(coverage) == len(companies) == 15
    
    coverage_tickers = {c["ticker"] for c in coverage}
    company_tickers = {c.ticker for c in companies}
    assert coverage_tickers == company_tickers


def test_coverage_report_verified_period_count():
    coverage = load_coverage_report()
    for entry in coverage:
        ticker = entry["ticker"]
        assert entry["verified_period_count"] == 5, f"Ticker {ticker} does not have exactly 5 verified periods"
        if entry["target_period_status_code"] == 0:
            assert entry["overall_coverage_status"] == "5_PERIODS_VERIFIED_TARGET_HORIZON_INCLUDED"
        elif entry["target_period_status_code"] == 1:
            assert entry["overall_coverage_status"] == "5_PERIODS_VERIFIED_TARGET_HORIZON_PENDING"


def test_coverage_report_honest_target_period_reporting():
    coverage = load_coverage_report()
    for entry in coverage:
        ticker = entry["ticker"]
        country = entry["country"]
        
        # Indian companies target FY 2025–26, US companies target FY2026
        if country == "IN":
            assert entry["target_horizon_period"] == "FY 2025–26"
            assert entry["target_period_status_code"] in (0, 1, 2)
        else:
            assert entry["target_horizon_period"] == "FY2026"
            assert entry["target_period_status_code"] in (0, 1, 2)
            
        assert entry["target_period_status_desc"]
        assert len(entry["target_period_status_desc"]) > 20
        # Check that collection cutoff date is recorded
        assert entry["collection_cutoff_date"] in ("2026-10-17", "2026-10-18")
        
        # Check that core metrics and derived metrics lists are populated
        assert len(entry["core_metrics_verified"]) == 5
        assert len(entry["derived_metrics_supported"]) == 5
