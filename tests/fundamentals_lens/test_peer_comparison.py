import pytest
from fundamentals_lens.data_loader import load_companies, load_financial_facts
from fundamentals_lens.peers import PeerComparisonEngine, PEER_GROUP_METADATA


def test_peer_group_metadata():
    groups = PeerComparisonEngine.get_all_peer_groups()
    assert len(groups) == 5
    
    auto_group = groups.get("group_d_india_auto")
    assert auto_group is not None
    assert "Passenger car economics differ structurally" in auto_group.comparability_notes
    assert any("Maruti Suzuki produces 4-wheeler passenger cars" in c for c in auto_group.structural_caveats)
    assert auto_group.currency == "INR"

    retail_group = groups.get("group_e_us_retail")
    assert retail_group is not None
    assert any("Costco" in c for c in retail_group.structural_caveats)
    assert retail_group.currency == "USD"


def test_peer_comparison_matrix_generation():
    companies = load_companies()
    facts = load_financial_facts()
    facts_by_ticker = {}
    for f in facts:
        facts_by_ticker.setdefault(f.ticker, []).append(f)

    # Test Tech group revenue growth
    matrix = PeerComparisonEngine.build_peer_comparison_matrix(
        companies, facts_by_ticker, "group_a_tech", "revenue_growth_yoy"
    )
    assert "series" in matrix
    assert len(matrix["series"]) == 3
    assert matrix["unit"] == "%"
    assert matrix["is_single_currency"] is True
    assert matrix["currency_code"] == "USD"

    for s in matrix["series"]:
        assert s["ticker"] in ("AAPL", "MSFT", "GOOGL")
        assert len(s["data"]) == 5

    # Test Indian FMCG operating margin
    matrix_fmcg = PeerComparisonEngine.build_peer_comparison_matrix(
        companies, facts_by_ticker, "group_c_india_fmcg", "operating_margin"
    )
    assert len(matrix_fmcg["series"]) == 3
    assert matrix_fmcg["currency_code"] == "INR"
    assert matrix_fmcg["unit"] == "%"


def test_peer_comparison_invalid_group():
    companies = load_companies()
    facts_by_ticker = {}
    res = PeerComparisonEngine.build_peer_comparison_matrix(companies, facts_by_ticker, "invalid_group", "revenue")
    assert "error" in res


def test_indexed_peer_matrix_revenue():
    companies = load_companies()
    facts = load_financial_facts()
    facts_by_ticker = {}
    for f in facts:
        facts_by_ticker.setdefault(f.ticker, []).append(f)

    # Test Tech group indexed revenue (default earliest base year)
    indexed_res = PeerComparisonEngine.build_indexed_peer_matrix(
        companies, facts_by_ticker, "group_a_tech", "revenue"
    )
    assert "series" in indexed_res
    assert len(indexed_res["series"]) == 3
    assert "Index (Base" in indexed_res["unit"]
    assert any("does NOT compare absolute corporate scale" in c for c in indexed_res["structural_caveats"])

    for s in indexed_res["series"]:
        assert s["is_suppressed"] is False
        assert s["suppress_reason"] is None
        # Base period must be 100.0
        base_pt = next(pt for pt in s["data"] if pt["fiscal_year"] == indexed_res["base_year"])
        assert base_pt["value"] == 100.0
        # Subsequent periods should have calculated relative index
        for pt in s["data"]:
            assert pt["value"] is not None
            assert pt["value"] > 0


def test_indexed_peer_matrix_explicit_base_year():
    companies = load_companies()
    facts = load_financial_facts()
    facts_by_ticker = {}
    for f in facts:
        facts_by_ticker.setdefault(f.ticker, []).append(f)

    # Test Indian IT group with explicit base year 2023
    indexed_res = PeerComparisonEngine.build_indexed_peer_matrix(
        companies, facts_by_ticker, "group_b_india_it", "revenue", base_year=2023
    )
    assert indexed_res["base_year"] == 2023
    for s in indexed_res["series"]:
        base_pt = next(pt for pt in s["data"] if pt["fiscal_year"] == 2023)
        assert base_pt["value"] == 100.0


def test_indexed_peer_matrix_suppression_mock():
    from fundamentals_lens.models import FinancialFact, Company
    mock_comp = [
        Company(
            ticker="LOSS", name="LossCo", peer_group_id="group_a_tech", peer_group_name="Tech",
            country="US", reporting_currency="USD", standard_unit_label="$M", scale_multiplier=1000000,
            fiscal_year_end_month="December", primary_source_url="http://sec.gov",
            exchange="NASDAQ", business_description="Mock", peer_notes="Mock"
        )
    ]
    mock_facts = {
        "LOSS": [
            FinancialFact(
                ticker="LOSS", company_name="LossCo", peer_group_id="group_a_tech", country="US",
                currency="USD", unit="$M", scale_multiplier=1000000, fiscal_year=2021,
                fiscal_year_label="FY2021", period_start="2021-01-01", period_end="2021-12-31",
                statement_basis="CONSOLIDATED", revenue=100.0, operating_income=-20.0, net_income=-30.0,
                operating_cash_flow=-10.0, capital_expenditure=5.0, source_id="S1", source_title="T1",
                source_url="http://sec.gov", filing_date="2022-01-01", statement_location="P1",
                accession_id="A1", reported_status="REPORTED", verification_status="VERIFIED"
            ),
            FinancialFact(
                ticker="LOSS", company_name="LossCo", peer_group_id="group_a_tech", country="US",
                currency="USD", unit="$M", scale_multiplier=1000000, fiscal_year=2022,
                fiscal_year_label="FY2022", period_start="2022-01-01", period_end="2022-12-31",
                statement_basis="CONSOLIDATED", revenue=120.0, operating_income=10.0, net_income=5.0,
                operating_cash_flow=15.0, capital_expenditure=5.0, source_id="S2", source_title="T2",
                source_url="http://sec.gov", filing_date="2023-01-01", statement_location="P2",
                accession_id="A2", reported_status="REPORTED", verification_status="VERIFIED"
            )
        ]
    }

    # Indexing operating income where base period is negative (-20.0)
    indexed_res = PeerComparisonEngine.build_indexed_peer_matrix(
        mock_comp, mock_facts, "group_a_tech", "operating_income", base_year=2021
    )
    s = indexed_res["series"][0]
    assert s["is_suppressed"] is True
    assert "non-positive" in s["suppress_reason"]
    assert s["data"][0]["value"] is None
    assert s["data"][1]["value"] is None

