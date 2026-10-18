"""
Unit tests for SEC EDGAR submissions audit script (scripts/audit_sec_filings_online.py).
Tests offline structural validation and comprehensive mocked online audit scenarios:
- Wrong ticker/CIK
- Wrong accession
- Wrong filing form
- Wrong filing date
- Wrong report period
- Mismatched primary-document path
- Mismatched stored source URL (accession directory or CIK directory)
- Historical submissions lookup
- Missing network library
- Rate limit and server errors (HTTP 429, 500, 403)
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


def test_offline_audit_canonical_facts(tmp_path):
    """Verify that canonical bundled facts all pass offline structure validation."""
    rep_file = tmp_path / "report.json"
    summary = audit_sec_filings(offline=True, strict=True, report_path=rep_file)
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
    """Verify that a successful SEC response with all matching criteria marks ONLINE_VERIFIED."""
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
        "cik": "0000320193",
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


def test_online_audit_detects_wrong_ticker_cik(tmp_path):
    """Verify that mismatched CIK in SEC submissions root triggers MISMATCH."""
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

    sec_json = {
        "cik": "0000999999",  # Contradicts AAPL CIK 0000320193
        "filings": {"recent": {}}
    }
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = sec_json

    with patch("scripts.audit_sec_filings_online.requests.get", return_value=mock_resp), \
         patch("scripts.audit_sec_filings_online.CIK_MAP", {"AAPL": "0000320193"}), \
         patch("scripts.audit_sec_filings_online.time.sleep", return_value=None):
        summary = audit_sec_filings(offline=False, strict=False, facts_path=facts_file, report_path=rep_file)

    assert summary["failure_detected"] is True
    assert summary["results"][0]["status"] == "MISMATCH"
    assert "CIK" in summary["results"][0]["error"]


def test_online_audit_detects_wrong_accession(tmp_path):
    """Verify that accession not present in SEC filings is marked NOT_FOUND."""
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
        "cik": "0000320193",
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
        summary = audit_sec_filings(offline=False, strict=False, facts_path=facts_file, report_path=rep_file)

    assert summary["status_counts"].get("NOT_FOUND") == 1
    assert summary["failure_detected"] is True


def test_online_audit_detects_wrong_filing_form(tmp_path):
    """Verify that Form other than 10-K triggers MISMATCH."""
    mock_facts = [
        {
            "ticker": "AAPL",
            "fiscal_year_label": "FY2021",
            "accession_id": "0000320193-21-000105",
            "source_url": "https://www.sec.gov/Archives/edgar/data/320193/000032019321000105/aapl-20210925.htm",
            "country": "US"
        }
    ]
    facts_file = tmp_path / "facts.json"
    facts_file.write_text(json.dumps(mock_facts), encoding="utf-8")
    rep_file = tmp_path / "report.json"

    sec_json = {
        "cik": "0000320193",
        "filings": {
            "recent": {
                "accessionNumber": ["0000320193-21-000105"],
                "form": ["10-Q"],  # Discrepancy
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
        summary = audit_sec_filings(offline=False, strict=False, facts_path=facts_file, report_path=rep_file)

    assert summary["status_counts"].get("MISMATCH") == 1
    assert "Expected Form 10-K" in summary["results"][0]["error"]


def test_online_audit_detects_wrong_filing_date(tmp_path):
    """Verify that filing date mismatch triggers MISMATCH."""
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
        "cik": "0000320193",
        "filings": {
            "recent": {
                "accessionNumber": ["0000320193-21-000105"],
                "form": ["10-K"],
                "filingDate": ["2021-11-05"],  # Discrepancy
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
        summary = audit_sec_filings(offline=False, strict=False, facts_path=facts_file, report_path=rep_file)

    assert summary["status_counts"].get("MISMATCH") == 1
    assert "Filing date mismatch" in summary["results"][0]["error"]


def test_online_audit_detects_wrong_report_period(tmp_path):
    """Verify that report period mismatch triggers MISMATCH."""
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
        "cik": "0000320193",
        "filings": {
            "recent": {
                "accessionNumber": ["0000320193-21-000105"],
                "form": ["10-K"],
                "filingDate": ["2021-10-29"],
                "primaryDocument": ["aapl-20210925.htm"],
                "reportDate": ["2021-09-30"]  # Discrepancy
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
    assert "Report period mismatch" in summary["results"][0]["error"]


def test_online_audit_detects_mismatched_primary_document_path(tmp_path):
    """Verify that primary document not matching source_url filename triggers MISMATCH."""
    mock_facts = [
        {
            "ticker": "AAPL",
            "fiscal_year_label": "FY2021",
            "accession_id": "0000320193-21-000105",
            "filing_date": "2021-10-29",
            "period_end": "2021-09-25",
            "source_url": "https://www.sec.gov/Archives/edgar/data/320193/000032019321000105/wrong-doc.htm",
            "country": "US"
        }
    ]
    facts_file = tmp_path / "facts.json"
    facts_file.write_text(json.dumps(mock_facts), encoding="utf-8")
    rep_file = tmp_path / "report.json"

    sec_json = {
        "cik": "0000320193",
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
        summary = audit_sec_filings(offline=False, strict=False, facts_path=facts_file, report_path=rep_file)

    assert summary["status_counts"].get("MISMATCH") == 1
    assert "Primary document" in summary["results"][0]["error"]


def test_online_audit_detects_mismatched_stored_source_url(tmp_path):
    """Verify that wrong accession directory in source URL triggers MISMATCH."""
    mock_facts = [
        {
            "ticker": "AAPL",
            "fiscal_year_label": "FY2021",
            "accession_id": "0000320193-21-000105",
            "filing_date": "2021-10-29",
            "period_end": "2021-09-25",
            "source_url": "https://www.sec.gov/Archives/edgar/data/320193/999999999999000000/aapl-20210925.htm",
            "country": "US"
        }
    ]
    facts_file = tmp_path / "facts.json"
    facts_file.write_text(json.dumps(mock_facts), encoding="utf-8")
    rep_file = tmp_path / "report.json"

    sec_json = {
        "cik": "0000320193",
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
        summary = audit_sec_filings(offline=False, strict=False, facts_path=facts_file, report_path=rep_file)

    assert summary["status_counts"].get("MISMATCH") == 1
    assert "Accession directory" in summary["results"][0]["error"]


def test_online_audit_historical_submissions_lookup(tmp_path):
    """Verify that filings located in filings.files are resolved properly."""
    mock_facts = [
        {
            "ticker": "WMT",
            "fiscal_year_label": "FY2022",
            "accession_id": "0000104169-22-000012",
            "filing_date": "2022-03-18",
            "period_end": "2022-01-31",
            "source_url": "https://www.sec.gov/Archives/edgar/data/104169/000010416922000012/wmt-20220131.htm",
            "country": "US"
        }
    ]
    facts_file = tmp_path / "facts.json"
    facts_file.write_text(json.dumps(mock_facts), encoding="utf-8")
    rep_file = tmp_path / "report.json"

    recent_json = {
        "cik": "0000104169",
        "filings": {
            "recent": {
                "accessionNumber": ["0000104169-26-000055"],
                "form": ["10-K"],
                "filingDate": ["2026-03-19"],
                "primaryDocument": ["wmt-20260131.htm"],
                "reportDate": ["2026-01-31"]
            },
            "files": [
                {"name": "CIK0000104169-submissions-001.json"}
            ]
        }
    }
    hist_json = {
        "accessionNumber": ["0000104169-22-000012"],
        "form": ["10-K"],
        "filingDate": ["2022-03-18"],
        "primaryDocument": ["wmt-20220131.htm"],
        "reportDate": ["2022-01-31"]
    }

    def mock_get(url, *args, **kwargs):
        resp = MagicMock()
        resp.status_code = 200
        if "submissions-001.json" in url:
            resp.json.return_value = hist_json
        else:
            resp.json.return_value = recent_json
        return resp

    with patch("scripts.audit_sec_filings_online.requests.get", side_effect=mock_get), \
         patch("scripts.audit_sec_filings_online.CIK_MAP", {"WMT": "0000104169"}), \
         patch("scripts.audit_sec_filings_online.time.sleep", return_value=None):
        summary = audit_sec_filings(offline=False, strict=True, facts_path=facts_file, report_path=rep_file)

    assert summary["status_counts"].get("ONLINE_VERIFIED") == 1
    assert summary["failure_detected"] is False
    assert summary["results"][0]["status"] == "ONLINE_VERIFIED"


def test_online_audit_missing_network_library(tmp_path):
    """Verify that when REQUESTS_AVAILABLE is False, audit defaults safely to OFFLINE mode."""
    mock_facts = [
        {
            "ticker": "AAPL",
            "fiscal_year_label": "FY2021",
            "accession_id": "0000320193-21-000105",
            "source_url": "https://www.sec.gov/Archives/edgar/data/320193/000032019321000105/aapl-20210925.htm",
            "country": "US"
        }
    ]
    facts_file = tmp_path / "facts.json"
    facts_file.write_text(json.dumps(mock_facts), encoding="utf-8")
    rep_file = tmp_path / "report.json"

    with patch("scripts.audit_sec_filings_online.REQUESTS_AVAILABLE", False), \
         patch("scripts.audit_sec_filings_online.CIK_MAP", {"AAPL": "0000320193"}):
        summary = audit_sec_filings(offline=False, strict=False, facts_path=facts_file, report_path=rep_file)

    assert summary["mode"] == "OFFLINE"
    assert summary["status_counts"].get("OFFLINE_STRUCTURE_ONLY") == 1


def test_online_audit_rate_limit_and_server_errors(tmp_path):
    """Verify that 429 and 500 status codes return UNAVAILABLE without failing code execution."""
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

    for code in [429, 500, 403]:
        mock_resp = MagicMock()
        mock_resp.status_code = code

        with patch("scripts.audit_sec_filings_online.requests.get", return_value=mock_resp), \
             patch("scripts.audit_sec_filings_online.CIK_MAP", {"AAPL": "0000320193"}), \
             patch("scripts.audit_sec_filings_online.time.sleep", return_value=None):
            summary = audit_sec_filings(offline=False, strict=False, facts_path=facts_file, report_path=rep_file)

        assert summary["status_counts"].get("UNAVAILABLE") == 1
        assert summary["results"][0]["status"] == "UNAVAILABLE"
