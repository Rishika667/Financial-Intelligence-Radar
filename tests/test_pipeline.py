from datetime import date, datetime
from financial_radar.models import Observation, Provenance, DataQuality
from financial_radar.pipeline import evaluate
from financial_radar.normalization import extract_companyfacts


def o(metric, value, end, provenance=(), period_type="QUARTER"):
    return Observation("ABC", metric, value, "USD", end, period_type, DataQuality.REPORTED, provenance)


def test_pipeline_signal_keeps_provenance():
    """Signal evidence preserves observation provenance.

    Uses $M-scale values and ~365-day gap for _comparable_pair matching.
    """
    p = Provenance(
        "0001", "https://sec.example/f", date(2025, 1, 1), "10-Q",
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        datetime(2025, 1, 2), 100_000_000
    )
    now = date(2025, 6, 30)
    old = date(2024, 6, 30)
    data = [
        o("revenue", 100_000_000, now, (p,)),
        o("revenue", 50_000_000, old, (p,)),
        o("accounts_receivable", 200_000_000, now, (p,), "INSTANT"),
        o("accounts_receivable", 50_000_000, old, (p,), "INSTANT"),
    ]
    signals = evaluate("ABC", data)
    hit = next(s for s in signals if s.signal_id == "RECEIVABLES_REVENUE_DIVERGENCE")
    assert hit.evidence[0].provenance[0].accession == "0001"


def test_normalization_missing_is_not_zero():
    payload = {
        "facts": {
            "us-gaap": {
                "RevenueFromContractWithCustomerExcludingAssessedTax": {
                    "units": {
                        "USD": [
                            {
                                "accn": "0001", "filed": "2025-01-01",
                                "form": "10-Q", "end": "2024-12-31",
                                "start": "2024-10-01", "val": 10
                            }
                        ]
                    }
                }
            }
        }
    }
    rows = extract_companyfacts(
        "ABC", "1", payload,
        {"0001": {"source_url": "https://sec.example", "accessionNumber": "0001"}}
    )
    revenue = next(x for x in rows if x.metric == "revenue" and x.value is not None)
    inventory = next(x for x in rows if x.metric == "inventory")
    assert revenue.value == 10
    assert inventory.value is None
    assert inventory.quality == DataQuality.NOT_REPORTED


def test_pipeline_retrieval_failure_does_not_crash(caplog):
    """Event extraction handles HTTP/retrieval failures safely without crashing."""
    from financial_radar.pipeline import _extract_events_from_submissions
    import logging

    class MockClient:
        delay = 0
        last = 0
        class s:
            @staticmethod
            def get(url, timeout):
                raise ValueError("Simulated HTTP failure")

    filings = {
        "1": {"form": "8-K", "source_url": "http://sec.example/1", "accessionNumber": "1"}
    }
    
    with caplog.at_level(logging.WARNING):
        count = _extract_events_from_submissions("ABC", filings, None, MockClient())
    
    assert count == 0
    assert "Event extraction failed for ABC filing 1: Simulated HTTP failure" in caplog.text


def test_pipeline_malformed_filing_index():
    """filing_index handles malformed SEC submission JSONs safely."""
    from financial_radar.pipeline import filing_index
    # Missing primaryDocument or form
    submissions = {
        "filings": {
            "recent": {
                "accessionNumber": ["111-222", "333-444"],
                "form": ["10-K", None],
                "primaryDocument": ["doc1.htm", ""],
                "filingDate": ["2025-01-01", "2025-01-02"]
            }
        }
    }
    idx = filing_index(submissions, "1")
    # Only the valid filing should be included
    assert "111222" in idx
    assert "333444" not in idx
    assert idx["111222"]["form"] == "10-K"
