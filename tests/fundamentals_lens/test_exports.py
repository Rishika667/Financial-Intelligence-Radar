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

    # Exactly 1 header + 5 observations
    assert len(rows) == 6
    for row in rows[1:]:
        assert row[0] == company.ticker
        assert float(row[10]) > 0 # Revenue > 0


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
    assert "What Changed, Why It Matters, and What to Investigate" in brief
    assert "Primary Source Verification" in brief
    assert "Disclaimer" in brief
    assert "not constitute investment advice" in brief
