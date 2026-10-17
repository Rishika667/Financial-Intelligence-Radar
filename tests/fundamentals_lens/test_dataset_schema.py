import subprocess
from pathlib import Path
from fundamentals_lens.data_loader import (
    load_companies,
    load_financial_facts,
    load_source_register,
    load_coverage_report,
    get_dataset_dir
)


def test_dataset_git_tracking():
    """Verify that dataset directory is tracked by git and not ignored."""
    dataset_dir = get_dataset_dir()
    test_file = dataset_dir / "companies.json"
    assert test_file.exists(), f"File {test_file} should exist."
    
    # Run git check-ignore
    result = subprocess.run(
        ["git", "check-ignore", str(test_file)],
        capture_output=True,
        text=True
    )
    # git check-ignore returns exit code 1 if the path is NOT ignored
    assert result.returncode == 1, f"Canonical dataset {test_file} must NOT be ignored by Git!"


def test_companies_schema_and_count():
    companies = load_companies()
    assert len(companies) == 15, f"Expected exactly 15 companies, found {len(companies)}"
    
    peer_groups = {c.peer_group_id for c in companies}
    expected_groups = {
        "group_a_tech", "group_b_india_it", "group_c_india_fmcg",
        "group_d_india_auto", "group_e_us_retail"
    }
    assert peer_groups == expected_groups, f"Expected 5 peer groups, got {peer_groups}"
    
    for c in companies:
        assert c.ticker and isinstance(c.ticker, str)
        assert c.name and isinstance(c.name, str)
        assert c.country in ("US", "IN")
        assert c.reporting_currency in ("USD", "INR")
        assert c.scale_multiplier in (1000000, 10000000)
        assert c.primary_source_url.startswith("http")


def test_financial_facts_record_count_and_types():
    facts = load_financial_facts()
    assert len(facts) == 75, f"Expected 75 records (15 companies * 5 periods), found {len(facts)}"
    
    for f in facts:
        assert f.ticker
        assert f.fiscal_year >= 2019
        assert f.revenue > 0, "Revenue should be positive for our universe"
        assert isinstance(f.operating_income, (int, float))
        assert isinstance(f.net_income, (int, float))
        assert isinstance(f.operating_cash_flow, (int, float))
        assert f.capital_expenditure > 0, "Capex must be stored as positive magnitude"
        assert f.statement_basis == "CONSOLIDATED"
        assert f.verification_status == "VERIFIED"


def test_source_register_count_and_keys():
    sources = load_source_register()
    assert len(sources) == 75, f"Expected 75 source citations, found {len(sources)}"
    
    for s in sources:
        assert s["source_id"].startswith("SRC_")
        assert s["source_url"].startswith("http")
        assert s["statement_location"]
        assert s["accession_id"]
        assert s["verification_status"] == "VERIFIED"


def test_coverage_report_structure():
    coverage = load_coverage_report()
    assert len(coverage) == 15, "Expected coverage report for all 15 companies"
    
    for entry in coverage:
        assert entry["verified_period_count"] == 5
        assert len(entry["verified_periods"]) == 5
        assert entry["target_horizon_period"] in ("FY 2025–26", "FY2026")
        assert entry["target_period_status_code"] in (0, 1, 2)
        assert entry["overall_coverage_status"] in (
            "5_PERIODS_VERIFIED_TARGET_HORIZON_INCLUDED",
            "5_PERIODS_VERIFIED_TARGET_HORIZON_PENDING"
        )
