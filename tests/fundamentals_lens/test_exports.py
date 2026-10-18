import pytest
import csv
import io
from fundamentals_lens.data_loader import load_companies, load_financial_facts
from fundamentals_lens.exports import ExportGenerator


def test_company_csv_export():
    companies = load_companies()
    facts = load_financial_facts()
    company = companies[0]
    company_facts = [f for f in facts if f.ticker == company.ticker]

    csv_data = ExportGenerator.generate_company_csv(company, company_facts)
    assert isinstance(csv_data, str)
    assert len(csv_data) > 200

    reader = csv.reader(io.StringIO(csv_data))
    rows = list(reader)
    header = rows[0]

    assert "Ticker" in header
    assert "Revenue" in header
    assert "Operating Margin (%)" in header
    assert "Free Cash Flow" in header
    assert "Accession ID" in header
    assert "Source URL" in header
    assert "Comparability Flag" in header
    assert "Accounting Notes" in header
    assert "Reconciliation Tier" in header

    # Exactly 1 header + 5 observations
    assert len(rows) == 6
    for row in rows[1:]:
        assert row[0] == company.ticker
        assert float(row[10]) > 0  # Revenue > 0
        assert row[27] in ["DIRECT", "PROXY", "LIMITED"]
        assert row[29] in ["INDEPENDENTLY_RECONCILED", "SOURCE_LINKED_AUDITED"]


def test_research_brief_export():
    companies = load_companies()
    facts = load_financial_facts()
    company = companies[0]
    company_facts = [f for f in facts if f.ticker == company.ticker]

    brief = ExportGenerator.generate_research_brief(company, company_facts)
    assert isinstance(brief, str)
    assert len(brief) > 1000

    assert company.name in brief
    assert company.ticker in brief
    assert "Business Context" in brief
    assert "Historical Financial Disclosures" in brief
    assert "Derived Analytical Indicators" in brief
    assert "Mathematical Formulas & Calculation Invariants" in brief
    assert "What Changed, Why It Matters, and What to Investigate" in brief
    assert "Primary Source Verification" in brief
    assert "Disclaimer" in brief
    assert "CONSOLIDATED" in brief
    assert "not constitute investment advice" in brief


def test_peer_comparison_csv_export():
    from fundamentals_lens.peers import PeerComparisonEngine
    companies = load_companies()
    facts = load_financial_facts()
    facts_by_ticker = {}
    for f in facts:
        facts_by_ticker.setdefault(f.ticker, []).append(f)

    matrix = PeerComparisonEngine.build_peer_comparison_matrix(
        companies, facts_by_ticker, "group_a_tech", "operating_margin"
    )
    csv_str = ExportGenerator.generate_peer_comparison_csv(matrix, "Global Technology Leaders")

    assert isinstance(csv_str, str)
    assert len(csv_str) > 100
    assert "# Peer Comparison Export" in csv_str
    assert "Global Technology Leaders" in csv_str
    assert "operating_margin" in csv_str

    reader = csv.reader(io.StringIO(csv_str))
    data_rows = [r for r in reader if r and not r[0].startswith("#")]
    assert len(data_rows) >= 5  # header + at least 4 periods
    header = data_rows[0]
    assert header[0] == "Fiscal Period"
    assert any("MSFT" in col for col in header)
    assert any("GOOGL" in col for col in header)
