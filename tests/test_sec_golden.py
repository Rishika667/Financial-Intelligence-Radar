import pytest
import sqlite3
import json
from financial_radar.store import connect, rows
from financial_radar.pipeline import ingest_company

class RealSECClient:
    def __init__(self):
        self.delay = 0
        self.last = 0
        self.s = None
        self.cik_to_ticker = {
            '0000320193': 'aapl',
            '0000789019': 'msft',
            '0001045810': 'nvda',
            '0000019617': 'jpm',
            '0001018724': 'amzn',
            '0001652044': 'googl',
            '0001326801': 'meta',
            '0001318605': 'tsla',
            '0000200406': 'jnj',
            '0000034088': 'xom',
        }

    def submissions(self, cik):
        cik_clean = str(int(cik)).zfill(10)
        t = self.cik_to_ticker.get(cik_clean, "aapl")
        with open(f'tests/fixtures/{t}_submissions.json', 'r', encoding='utf-8') as f:
            return json.load(f)

    def company_facts(self, cik):
        cik_clean = str(int(cik)).zfill(10)
        t = self.cik_to_ticker.get(cik_clean, "aapl")
        with open(f'tests/fixtures/{t}_facts.json', 'r', encoding='utf-8') as f:
            return json.load(f)

def test_real_sec_ingestion_e2e():
    c = connect(':memory:')
    client = RealSECClient()
    
    companies = [
        {'ticker': 'AAPL', 'cik': '0000320193', 'sector': 'Information Technology'},
        {'ticker': 'MSFT', 'cik': '0000789019', 'sector': 'Information Technology'},
        {'ticker': 'NVDA', 'cik': '0001045810', 'sector': 'Information Technology'},
        {'ticker': 'JPM', 'cik': '0000019617', 'sector': 'Financials'},
        {'ticker': 'AMZN', 'cik': '0001018724', 'sector': 'Consumer Discretionary'},
        {'ticker': 'GOOGL', 'cik': '0001652044', 'sector': 'Communication Services'},
        {'ticker': 'META', 'cik': '0001326801', 'sector': 'Communication Services'},
        {'ticker': 'TSLA', 'cik': '0001318605', 'sector': 'Consumer Discretionary'},
        {'ticker': 'JNJ', 'cik': '0000200406', 'sector': 'Health Care'},
        {'ticker': 'XOM', 'cik': '0000034088', 'sector': 'Energy'},
    ]
    
    for comp in companies:
        try:
            res = ingest_company(client, c, comp)
            assert res['observations'] > 0, f"Expected observations for {comp['ticker']}"
        except Exception as e:
            pytest.fail(f"Ingestion failed for {comp['ticker']}: {e}")
            
    # Verify records were inserted across all 10 companies
    obs = rows(c, "SELECT count(*) as c FROM observations")
    assert obs[0]['c'] > 1000, f"Expected >1000 observations across 10 companies, got {obs[0]['c']}"

    # Verify each distinct company has observations in SQLite
    comps_in_db = rows(c, "SELECT DISTINCT company FROM observations")
    assert len(comps_in_db) == 10, f"Expected 10 distinct companies in observations, got {len(comps_in_db)}"

    # Verify provenance preserved across companies with reported metrics (excluding JPM financial institution)
    corporate_comps = [comp for comp in companies if comp["ticker"] != "JPM"]
    for comp in corporate_comps:
        p_rows = rows(c, "SELECT provenance FROM observations WHERE company=? AND provenance != '[]' LIMIT 2", (comp["ticker"],))
        assert len(p_rows) > 0, f"Expected non-empty provenance for {comp['ticker']}"
        p_list = json.loads(p_rows[0]['provenance'])
        assert len(p_list) > 0, f"Expected provenance entries for {comp['ticker']}"
        assert p_list[0]['accession'] != "", f"Expected non-empty accession for {comp['ticker']}"
        assert "sec.gov" in p_list[0]['source_url'], f"Expected SEC source URL for {comp['ticker']}"

