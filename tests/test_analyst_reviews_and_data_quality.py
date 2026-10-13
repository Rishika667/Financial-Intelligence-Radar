import pytest
import sqlite3
import json
from datetime import datetime
from financial_radar.store import (
    connect, rows,
    save_analyst_review, get_analyst_review, get_analyst_reviews_for_company,
    get_all_analyst_reviews, generate_alert_fingerprint,
    save_refresh_history, get_refresh_history, get_latest_refresh_time,
    VALID_REVIEW_STATUSES
)


def test_alert_fingerprint_stability_and_period_specificity():
    """Fingerprints must be stable for identical evidence periods and distinct for different periods."""
    evidence_q1_2024 = [
        {"metric": "gross_margin", "period_end": "2024-03-31", "period_type": "QUARTER", "fiscal_year": 2024, "fiscal_period": "Q1"},
        {"metric": "gross_margin", "period_end": "2023-03-31", "period_type": "QUARTER", "fiscal_year": 2023, "fiscal_period": "Q1"}
    ]
    evidence_q2_2024 = [
        {"metric": "gross_margin", "period_end": "2024-06-30", "period_type": "QUARTER", "fiscal_year": 2024, "fiscal_period": "Q2"},
        {"metric": "gross_margin", "period_end": "2023-06-30", "period_type": "QUARTER", "fiscal_year": 2023, "fiscal_period": "Q2"}
    ]

    # Determinism / Stability
    fp1 = generate_alert_fingerprint("AAPL", "GROSS_MARGIN_COMPRESSION", evidence_q1_2024, "v1")
    fp2 = generate_alert_fingerprint("AAPL", "GROSS_MARGIN_COMPRESSION", evidence_q1_2024, "v1")
    assert fp1 == fp2, "Fingerprint must be strictly deterministic across calls"
    assert "AAPL_GROSS_MARGIN_COMPRESSION_" in fp1

    # Period specificity: different quarters must produce different fingerprints
    fp_q2 = generate_alert_fingerprint("AAPL", "GROSS_MARGIN_COMPRESSION", evidence_q2_2024, "v1")
    assert fp1 != fp_q2, "Different period evidence must yield different fingerprints to prevent note pollution"

    # Rule version specificity
    fp_v2 = generate_alert_fingerprint("AAPL", "GROSS_MARGIN_COMPRESSION", evidence_q1_2024, "v2")
    assert fp1 != fp_v2, "Different rule versions must yield distinct fingerprints"


def test_alert_fingerprint_materially_revised_and_restated_evidence():
    """
    Evidence value revisions and restatements for the same fiscal periods
    must generate distinct fingerprints to prevent newly restated alerts
    from silently inheriting stale review notes.
    """
    from financial_radar.models import DataQuality

    evidence_reported = [
        {"metric": "gross_margin", "period_end": "2024-03-31", "period_type": "QUARTER", "fiscal_year": 2024, "fiscal_period": "Q1", "value": 0.42, "unit": "pure", "quality": "REPORTED", "provenance": [{"accession": "0001-10Q"}]},
        {"metric": "gross_margin", "period_end": "2023-03-31", "period_type": "QUARTER", "fiscal_year": 2023, "fiscal_period": "Q1", "value": 0.45, "unit": "pure", "quality": "REPORTED", "provenance": [{"accession": "0002-10Q"}]}
    ]

    # Materially revised value (e.g. gross margin was actually 0.38 instead of 0.42)
    evidence_value_revised = [
        {"metric": "gross_margin", "period_end": "2024-03-31", "period_type": "QUARTER", "fiscal_year": 2024, "fiscal_period": "Q1", "value": 0.38, "unit": "pure", "quality": "REPORTED", "provenance": [{"accession": "0001-10Q"}]},
        {"metric": "gross_margin", "period_end": "2023-03-31", "period_type": "QUARTER", "fiscal_year": 2023, "fiscal_period": "Q1", "value": 0.45, "unit": "pure", "quality": "REPORTED", "provenance": [{"accession": "0002-10Q"}]}
    ]

    # Material restatement: quality changes from REPORTED to RESTATED / AMENDED with amended accession
    evidence_restated = [
        {"metric": "gross_margin", "period_end": "2024-03-31", "period_type": "QUARTER", "fiscal_year": 2024, "fiscal_period": "Q1", "value": 0.42, "unit": "pure", "quality": DataQuality.RESTATED, "provenance": [{"accession": "0001-10QA"}]},
        {"metric": "gross_margin", "period_end": "2023-03-31", "period_type": "QUARTER", "fiscal_year": 2023, "fiscal_period": "Q1", "value": 0.45, "unit": "pure", "quality": "REPORTED", "provenance": [{"accession": "0002-10Q"}]}
    ]

    fp_orig = generate_alert_fingerprint("AAPL", "GROSS_MARGIN_COMPRESSION", evidence_reported)
    fp_val_rev = generate_alert_fingerprint("AAPL", "GROSS_MARGIN_COMPRESSION", evidence_value_revised)
    fp_restated = generate_alert_fingerprint("AAPL", "GROSS_MARGIN_COMPRESSION", evidence_restated)

    assert fp_orig != fp_val_rev, "Materially revised evidence values must produce a different fingerprint"
    assert fp_orig != fp_restated, "Restated quality/provenance must produce a different fingerprint"
    assert fp_val_rev != fp_restated, "Value revisions and restatements must not collide"

    # Repeat call must remain 100% identical and stable
    assert generate_alert_fingerprint("AAPL", "GROSS_MARGIN_COMPRESSION", evidence_reported) == fp_orig



def test_analyst_review_crud_and_status_transitions():
    """Verify state transitions: NEW -> UNDER_REVIEW -> DISMISSED -> REOPEN."""
    c = connect(":memory:")
    fprint = "AAPL_TEST_FINGERPRINT_1234"

    # 1. Initial review: UNDER_REVIEW
    save_analyst_review(c, fprint, "AAPL", "GROSS_MARGIN_COMPRESSION", "UNDER_REVIEW", "Investigating supplier price hikes")
    rev = get_analyst_review(c, fprint)
    assert rev is not None
    assert rev["status"] == "UNDER_REVIEW"
    assert rev["note"] == "Investigating supplier price hikes"
    assert rev["company"] == "AAPL"

    # 2. Transition: DISMISSED
    save_analyst_review(c, fprint, "AAPL", "GROSS_MARGIN_COMPRESSION", "DISMISSED", "Transitory product transition effect")
    rev2 = get_analyst_review(c, fprint)
    assert rev2["status"] == "DISMISSED"
    assert rev2["note"] == "Transitory product transition effect"

    # 3. Transition: Reopen / ACKNOWLEDGED
    save_analyst_review(c, fprint, "AAPL", "GROSS_MARGIN_COMPRESSION", "ACKNOWLEDGED", "Reopened following revised 10-Q disclosures")
    rev3 = get_analyst_review(c, fprint)
    assert rev3["status"] == "ACKNOWLEDGED"

    # 4. Duplicate prevention: only one record per fingerprint exists
    all_revs = rows(c, "SELECT * FROM analyst_reviews WHERE fingerprint=?", (fprint,))
    assert len(all_revs) == 1, "Duplicate reviews for the same fingerprint must never exist"


def test_analyst_review_validation():
    """Invalid review statuses must be rejected immediately."""
    c = connect(":memory:")
    with pytest.raises(ValueError) as exc:
        save_analyst_review(c, "FP_INVALID", "AAPL", "SIG", "INVALID_STATUS", "Note")
    assert "Invalid review status" in str(exc.value)


def test_analyst_reviews_persistence_across_connections(tmp_path):
    """Review states must persist when database connection is closed and reopened."""
    db_file = str(tmp_path / "test_reviews.sqlite")
    c1 = connect(db_file)
    fprint = "MSFT_TEST_PERSIST_9999"

    save_analyst_review(c1, fprint, "MSFT", "OPERATING_MARGIN_DETERIORATION", "EXPECTED", "Expected R&D investment cycle")
    c1.close()

    # Reopen connection
    c2 = connect(db_file)
    rev = get_analyst_review(c2, fprint)
    assert rev is not None
    assert rev["status"] == "EXPECTED"
    assert rev["note"] == "Expected R&D investment cycle"
    c2.close()


def test_refresh_history_persistence_and_querying():
    """Verify that data refresh runs are durably recorded in SQLite."""
    c = connect(":memory:")

    # Initial state: empty
    assert get_latest_refresh_time(c) is None
    assert len(get_refresh_history(c)) == 0

    # Record successful refresh
    save_refresh_history(c, "AAPL", "SUCCESS", observations_count=120, signals_count=2, refresh_type="MONITORED_BATCH")
    save_refresh_history(c, "MSFT", "SUCCESS", observations_count=145, signals_count=0, refresh_type="MONITORED_BATCH")
    save_refresh_history(c, "NVDA", "FAILED", observations_count=0, signals_count=0, error_message="SEC rate limit 429", refresh_type="MONITORED_BATCH")

    # Verify query
    history = get_refresh_history(c, limit=10)
    assert len(history) == 3

    # Check latest success timestamp
    latest = get_latest_refresh_time(c)
    assert latest is not None

    # Check filter by ticker
    nvda_hist = get_refresh_history(c, ticker="NVDA")
    assert len(nvda_hist) == 1
    assert nvda_hist[0]["status"] == "FAILED"
    assert "429" in nvda_hist[0]["error_message"]
