"""
Unit tests for SEC EDGAR submissions audit script (scripts/audit_sec_filings_online.py).
Tests offline structural validation and mocked online audit modes.
"""

import sys
import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

# Ensure repo root is on sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from scripts.audit_sec_filings_online import audit_sec_filings, ACCESSION_PATTERN


def test_accession_pattern_regex():
    assert ACCESSION_PATTERN.match("0000320193-21-000105")
    assert ACCESSION_PATTERN.match("0000789019-23-000032")
    assert not ACCESSION_PATTERN.match("000032019321000105")  # Missing dashes
    assert not ACCESSION_PATTERN.match("BSE-500209-2022")     # Indian format
    assert not ACCESSION_PATTERN.match("0000320193-21-00105")  # Too short


def test_offline_audit_canonical_facts():
    """Verify that canonical bundled facts all pass offline structure validation."""
    summary = audit_sec_filings(offline=True, strict=True)
    assert summary["mode"] == "OFFLINE"
    assert summary["total_us_periods"] == 30
    assert summary["failure_detected"] is False
    assert summary["status_counts"].get("OFFLINE_STRUCTURE_ONLY") == 30
    for r in summary["results"]:
        assert r["status"] == "OFFLINE_STRUCTURE_ONLY"
        assert r["error"] is None


def test_offline_audit_detects_corrupt_accession(tmp_path):
    """Verify that offline audit detects malformed accession numbers."""
    mock_facts = [
        {
            "ticker": "AAPL",
            "fiscal_year_label": "FY2021",
            "accession_id": "CORRUPT-ACCESSION",
            "source_url": "https://www.sec.gov/Archives/edgar/data/320193/sample.htm",
            "country": "US"
        }
    ]
    facts_file = tmp_path / "facts.json"
    facts_file.write_text(json.dumps(mock_facts), encoding="utf-8")
    rep_file = tmp_path / "report.json"

    summary = audit_sec_filings(offline=True, strict=False, facts_path=facts_file, report_path=rep_file)
    assert summary["failure_detected"] is True
    assert summary["status_counts"].get("MISMATCH") == 1
    assert summary["results"][0]["status"] == "MISMATCH"


def test_online_audit_mocked_verified_match(tmp_path):
    """Verify that a successful SEC response marks status as ONLINE_VERIFIED."""
    mock_facts = [
        {
            "ticker": "AAPL",
            "fiscal_year_label": "FY2021",
            "accession_id": "0000320193-21-000105",
            "filing_date": "2021-10-29",
            "period_end": "2021-09-25",
            "source_url": "https://www.sec.gov/Archives/edgar/data/320193/000032019321000105/aapl-20210925.htm",
            "country": "US"
        }
    ]
    facts_file = tmp_path / "facts.json"
    facts_file.write_text(json.dumps(mock_facts), encoding="utf-8")
    rep_file = tmp_path / "report.json"

    sec_json = {
        "filings": {
            "recent": {
                "accessionNumber": ["0000320193-21-000105"],
                "form": ["10-K"],
                "filingDate": ["2021-10-29"],
                "primaryDocument": ["aapl-20210925.htm"],
                "reportDate": ["2021-09-25"]
            }
        }
    }

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = sec_json

    with patch("scripts.audit_sec_filings_online.requests.get", return_value=mock_resp), \
         patch("scripts.audit_sec_filings_online.CIK_MAP", {"AAPL": "0000320193"}), \
         patch("scripts.audit_sec_filings_online.time.sleep", return_value=None):
        summary = audit_sec_filings(offline=False, strict=True, facts_path=facts_file, report_path=rep_file)

    assert summary["mode"] == "ONLINE"
    assert summary["status_counts"].get("ONLINE_VERIFIED") == 1
    assert summary["failure_detected"] is False
    assert summary["results"][0]["status"] == "ONLINE_VERIFIED"
    assert summary["results"][0]["primary_document"] == "aapl-20210925.htm"


def test_online_audit_mocked_mismatch(tmp_path):
    """Verify that if SEC reports Form 10-Q or different date, status is MISMATCH."""
    mock_facts = [
        {
            "ticker": "AAPL",
            "fiscal_year_label": "FY2021",
            "accession_id": "0000320193-21-000105",
            "filing_date": "2021-10-29",
            "country": "US"
        }
    ]
    facts_file = tmp_path / "facts.json"
    facts_file.write_text(json.dumps(mock_facts), encoding="utf-8")
    rep_file = tmp_path / "report.json"

    sec_json = {
        "filings": {
            "recent": {
                "accessionNumber": ["0000320193-21-000105"],
                "form": ["10-Q"],  # Discrepancy: not 10-K
                "filingDate": ["2021-10-29"],
                "primaryDocument": ["aapl-20210925.htm"]
            }
        }
    }

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = sec_json

    with patch("scripts.audit_sec_filings_online.requests.get", return_value=mock_resp), \
         patch("scripts.audit_sec_filings_online.CIK_MAP", {"AAPL": "0000320193"}), \
         patch("scripts.audit_sec_filings_online.time.sleep", return_value=None):
        summary = audit_sec_filings(offline=False, strict=False, facts_path=facts_file, report_path=rep_file)

    assert summary["status_counts"].get("MISMATCH") == 1
    assert summary["failure_detected"] is True
    assert "Expected Form 10-K" in summary["results"][0]["error"]


def test_online_audit_mocked_not_found(tmp_path):
    """Verify that accession missing from recent filings is marked NOT_FOUND."""
    mock_facts = [
        {
            "ticker": "AAPL",
            "fiscal_year_label": "FY2021",
            "accession_id": "0000320193-21-999999",
            "country": "US"
        }
    ]
    facts_file = tmp_path / "facts.json"
    facts_file.write_text(json.dumps(mock_facts), encoding="utf-8")
    rep_file = tmp_path / "report.json"

    sec_json = {
        "filings": {
            "recent": {
                "accessionNumber": ["0000320193-21-000105"],
                "form": ["10-K"],
                "filingDate": ["2021-10-29"],
                "primaryDocument": ["aapl-20210925.htm"]
            }
        }
    }

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = sec_json

    with patch("scripts.audit_sec_filings_online.requests.get", return_value=mock_resp), \
         patch("scripts.audit_sec_filings_online.CIK_MAP", {"AAPL": "0000320193"}), \
         patch("scripts.audit_sec_filings_online.time.sleep", return_value=None):
        summary = audit_sec_filings(offline=False, strict=False, facts_path=facts_file, report_path=rep_file)

    assert summary["status_counts"].get("NOT_FOUND") == 1
    assert summary["failure_detected"] is True


def test_online_audit_mocked_unavailable(tmp_path):
    """Verify that network timeout or 429 returns UNAVAILABLE without hard crashing."""
    mock_facts = [
        {
            "ticker": "AAPL",
            "fiscal_year_label": "FY2021",
            "accession_id": "0000320193-21-000105",
            "country": "US"
        }
    ]
    facts_file = tmp_path / "facts.json"
    facts_file.write_text(json.dumps(mock_facts), encoding="utf-8")
    rep_file = tmp_path / "report.json"

    mock_resp = MagicMock()
    mock_resp.status_code = 429

    with patch("scripts.audit_sec_filings_online.requests.get", return_value=mock_resp), \
         patch("scripts.audit_sec_filings_online.CIK_MAP", {"AAPL": "0000320193"}), \
         patch("scripts.audit_sec_filings_online.time.sleep", return_value=None):
        summary = audit_sec_filings(offline=False, strict=False, facts_path=facts_file, report_path=rep_file)

    assert summary["status_counts"].get("UNAVAILABLE") == 1
    assert summary["results"][0]["status"] == "UNAVAILABLE"
