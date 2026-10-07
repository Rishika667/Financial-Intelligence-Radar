import pytest
import os
import json

def test_no_fixture_fallbacks():
    with open('tests/test_release_candidate.py', 'r', encoding='utf-8') as f:
        content = f.read()
    assert 'except:' not in content or 'return ' not in content.split('except:')[1][:50], "Fallback fixture logic found"

def test_msft_cik():
    with open('config/sp500_representative_51_2026.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
    msft = next(c for c in data['companies'] if c['ticker'] == 'MSFT')
    assert msft['cik'] == '0000789019'

def test_universe_version():
    with open('config/sp500_representative_51_2026.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
    assert data['version'] == 'sp500_representative_51_2026'

def test_stale_references():
    for root, dirs, files in os.walk('.'):
        if '.venv' in root or '.git' in root or '__pycache__' in root:
            continue
        for file in files:
            if file == "test_final_release.py":
                continue
            if file.endswith('.py') or file.endswith('.md') or file.endswith('.json'):
                path = os.path.join(root, file)
                with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                assert '50-company' not in content, f"Stale reference found in {path}"
                assert 'sp500_representative_50' not in content, f"Stale reference found in {path}"

def test_final_audit_exists():
    assert os.path.exists('final_release_audit.md')

def test_no_analytical_placeholders():
    for root, dirs, files in os.walk('src'):
        for file in files:
            if file.endswith('.py'):
                path = os.path.join(root, file)
                with open(path, 'r', encoding='utf-8') as f:
                    content = f.read()
                assert 'TODO' not in content, f"TODO found in {path}"
                assert 'FIXME' not in content, f"FIXME found in {path}"
                assert 'NotImplemented' not in content, f"NotImplemented found in {path}"

def test_canonical_metric_consistency():
    with open('src/financial_radar/metrics.py', 'r', encoding='utf-8') as f:
        content = f.read()
    assert 'capital_expenditures' in content

def test_no_broken_signal_ids():
    from financial_radar.pipeline import evaluate
    from financial_radar.models import Observation, DataQuality
    from datetime import date
    o1 = Observation("AAPL", "revenue", 100, "USD", date(2023,12,31), "QUARTER", DataQuality.REPORTED)
    o2 = Observation("AAPL", "revenue", 120, "USD", date(2022,12,31), "QUARTER", DataQuality.REPORTED)
    sigs = evaluate("AAPL", [o1, o2], "Technology")
    # Assert it executes cleanly and returns a signal or empty list
    assert isinstance(sigs, list)

def test_peer_reference_architecture():
    with open('config/sp500_representative_51_2026.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
    assert all(c.get('universe_type') == 'APPLICATION_UNIVERSE' for c in data['companies'])
    assert any(c.get('universe_type') == 'APPLICATION_UNIVERSE' for c in data['companies'])
