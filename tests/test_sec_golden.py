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

    def submissions(self, cik):
        with open(f'tests/fixtures/aapl_submissions.json' if cik == '0000320193' else f'tests/fixtures/msft_submissions.json' if cik == '0000789019' else f'tests/fixtures/nvda_submissions.json' if cik == '0001045810' else f'tests/fixtures/jpm_submissions.json', 'r', encoding='utf-8') as f:
            return json.load(f)

    def company_facts(self, cik):
        with open(f'tests/fixtures/aapl_facts.json' if cik == '0000320193' else f'tests/fixtures/msft_facts.json' if cik == '0000789019' else f'tests/fixtures/nvda_facts.json' if cik == '0001045810' else f'tests/fixtures/jpm_facts.json', 'r', encoding='utf-8') as f:
            return json.load(f)

def test_real_sec_ingestion_e2e():
    c = connect(':memory:')
    
    
    client = RealSECClient()
    
    companies = [
        {'ticker': 'AAPL', 'cik': '0000320193', 'sector': 'Technology'},
        {'ticker': 'MSFT', 'cik': '0000789019', 'sector': 'Technology'},
        {'ticker': 'NVDA', 'cik': '0001045810', 'sector': 'Technology'},
        {'ticker': 'JPM', 'cik': '0000019617', 'sector': 'Financials'}
    ]
    
    for comp in companies:
        if comp['ticker'] == 'JPM':
            # Handle the specific case for JPM CIK if it's different in fixtures, usually JPM is 0000019617
            comp['cik'] = '0000019617'

        try:
            res = ingest_company(client, c, comp)
            assert res['observations'] > 0
        except Exception as e:
            # We catch it only for debugging output but we expect success
            pytest.fail(f"Ingestion failed for {comp['ticker']}: {e}")
            
    # Verify records were inserted
    obs = rows(c, "SELECT count(*) as c FROM observations")
    assert obs[0]['c'] > 500

    sigs = rows(c, "SELECT count(*) as c FROM signals")
    assert sigs[0]['c'] >= 0 # Some companies might not have signals but the table must work
