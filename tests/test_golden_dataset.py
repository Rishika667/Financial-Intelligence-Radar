from datetime import date, datetime
from financial_radar.models import Observation, Provenance, DataQuality, Signal
from financial_radar.pipeline import evaluate
from financial_radar.normalization import extract_companyfacts
from financial_radar.core import derive_standalone_quarter
from financial_radar.events import extract_events
from financial_radar.signals import cluster


def _prov(acc="0001", tag="Revenue", dt="2025-01-01", val=100, form="10-Q"):
    return Provenance(acc, "https://sec.example", date.fromisoformat(dt), form, tag, datetime.utcnow(), val)


def o(metric, value, end, pt="QUARTER", quality=DataQuality.REPORTED, prov=None):
    return Observation("ABC", metric, value, "USD", date.fromisoformat(end), pt, quality, (prov or _prov(),))


# ---------------------------------------------------------
# PRIORITY 1: STANDALONE QUARTER DERIVATION & EVALUATION
# ---------------------------------------------------------
def test_golden_standalone_q2_derivation():
    """Q2 derived from H1 YTD - Q1 QUARTER."""
    q1 = o("revenue", 100, "2025-03-31", pt="QUARTER")
    ytd_6m = o("revenue", 300, "2025-06-30", pt="YTD_6M")

    q2 = derive_standalone_quarter(ytd_6m, q1)
    assert q2.value == 200
    assert q2.period_type == "QUARTER"
    assert q2.quality == DataQuality.DERIVED
    assert len(q2.provenance) == 2


def test_golden_standalone_q3_derivation():
    """Q3 derived from 9M YTD - H1 YTD."""
    ytd_6m = o("revenue", 300, "2025-06-30", pt="YTD_6M")
    ytd_9m = o("revenue", 600, "2025-09-30", pt="YTD_9M")

    q3 = derive_standalone_quarter(ytd_9m, ytd_6m)
    assert q3.value == 300
    assert q3.period_type == "QUARTER"


def test_golden_evaluate_consumes_derived_quarter():
    """Production pipeline derives Q2, signal evaluation uses it.

    The test constructs XBRL facts where Q2 can only be obtained by
    deriving H1 YTD - Q1 QUARTER. Realistic dollar values ensure the
    $1M monetary materiality floor is exceeded.
    """
    payload = {
        "facts": {
            "us-gaap": {
                "RevenueFromContractWithCustomerExcludingAssessedTax": {
                    "units": {
                        "USD": [
                            {"accn": "prior", "filed": "2024-07-25", "form": "10-Q",
                             "start": "2024-04-01", "end": "2024-06-30", "val": 80_000_000},
                            {"accn": "q1", "filed": "2025-04-25", "form": "10-Q",
                             "start": "2025-01-01", "end": "2025-03-31", "val": 100_000_000},
                            {"accn": "h1", "filed": "2025-07-25", "form": "10-Q",
                             "start": "2025-01-01", "end": "2025-06-30", "val": 300_000_000},
                        ]
                    }
                },
                "AccountsReceivableNetCurrent": {
                    "units": {
                        "USD": [
                            {"accn": "prior", "filed": "2024-07-25", "form": "10-Q",
                             "end": "2024-06-30", "val": 100_000_000},
                            {"accn": "h1", "filed": "2025-07-25", "form": "10-Q",
                             "end": "2025-06-30", "val": 300_000_000},
                        ]
                    }
                },
            }
        }
    }
    filings = {
        accession: {"source_url": f"https://sec.example/{accession}", "accessionNumber": accession}
        for accession in ("prior", "q1", "h1")
    }
    observations = extract_companyfacts("ABC", "1", payload, filings)

    derived_q2 = next(
        x for x in observations
        if x.metric == "revenue"
        and x.period_end == date(2025, 6, 30)
        and x.period_type == "QUARTER"
    )
    assert derived_q2.value == 200_000_000
    assert derived_q2.quality == DataQuality.DERIVED

    signals = evaluate("ABC", observations)
    div = next(
        (s for s in signals if s.signal_id == "RECEIVABLES_REVENUE_DIVERGENCE"),
        None
    )

    # Derived Q2 revenue grew 150% (80M->200M); AR grew 200% (100M->300M).
    # Gap = 50pp > 15% threshold. All values > $1M.
    assert div is not None
    assert div.severity == "HIGH"
    assert div.confidence == "MEDIUM"  # derived input
    assert derived_q2 in div.evidence


# ---------------------------------------------------------
# PRIORITY 2 & 3: XBRL NORMALIZATION, DEBT, RESTATEMENTS
# ---------------------------------------------------------
def test_golden_debt_aggregation():
    """Debt current + noncurrent aggregation when total is absent."""
    payload = {
        "facts": {
            "us-gaap": {
                "DebtCurrent": {
                    "units": {"USD": [{"accn": "1", "filed": "2025-03-31", "form": "10-Q", "end": "2025-03-31", "val": 50_000_000}]}
                },
                "LongTermDebtNoncurrent": {
                    "units": {"USD": [{"accn": "1", "filed": "2025-03-31", "form": "10-Q", "end": "2025-03-31", "val": 150_000_000}]}
                }
            }
        }
    }
    rows = extract_companyfacts("ABC", "1", payload, {"1": {"source_url": "url", "accessionNumber": "1"}})
    debt = next((x for x in rows if x.metric == "debt" and x.value is not None), None)

    assert debt is not None
    assert debt.value == 200_000_000
    assert debt.quality == DataQuality.DERIVED
    assert len(debt.provenance) == 2
    assert {p.concept for p in debt.provenance} == {"DebtCurrent", "LongTermDebtNoncurrent"}
    # No duplicate debt observations
    assert len([x for x in rows if x.metric == "debt" and x.value is not None]) == 1


def test_golden_restatement_selection():
    """Later filing supersedes original for the same period."""
    payload = {
        "facts": {
            "us-gaap": {
                "Revenues": {
                    "units": {
                        "USD": [
                            {"accn": "orig", "filed": "2024-05-01", "form": "10-Q",
                             "end": "2024-03-31", "start": "2024-01-01", "val": 100_000_000},
                            {"accn": "restated", "filed": "2025-05-01", "form": "10-K",
                             "end": "2024-03-31", "start": "2024-01-01", "val": 90_000_000}
                        ]
                    }
                }
            }
        }
    }
    rows = extract_companyfacts("ABC", "1", payload, {
        "orig": {"source_url": "url", "accessionNumber": "orig"},
        "restated": {"source_url": "url", "accessionNumber": "restated"}
    })

    rev = next(x for x in rows if x.metric == "revenue" and x.value is not None)
    assert rev.value == 90_000_000
    assert rev.provenance[0].accession == "restated"


def test_golden_amendment_selection():
    """Amended filing supersedes original when filed on the same day."""
    payload = {
        "facts": {
            "us-gaap": {
                "Revenues": {
                    "units": {
                        "USD": [
                            {"accn": "orig", "filed": "2024-05-01", "form": "10-Q",
                             "end": "2024-03-31", "start": "2024-01-01", "val": 100_000_000},
                            {"accn": "amend", "filed": "2024-05-01", "form": "10-Q/A",
                             "end": "2024-03-31", "start": "2024-01-01", "val": 95_000_000}
                        ]
                    }
                }
            }
        }
    }
    rows = extract_companyfacts("ABC", "1", payload, {
        "orig": {"source_url": "url", "accessionNumber": "orig"},
        "amend": {"source_url": "url", "accessionNumber": "amend"}
    })

    rev = next(x for x in rows if x.metric == "revenue" and x.value is not None)
    assert rev.value == 95_000_000
    assert rev.quality == DataQuality.AMENDED


def test_golden_missing_fact_not_zero():
    """Genuine missing value is NOT treated as zero."""
    payload = {"facts": {"us-gaap": {}}}
    rows = extract_companyfacts("ABC", "1", payload, {})
    rev = next(x for x in rows if x.metric == "revenue")
    assert rev.value is None
    assert rev.quality == DataQuality.NOT_REPORTED


# ---------------------------------------------------------
# PRIORITY 5: MATERIALITY FRAMEWORK
# ---------------------------------------------------------
def test_golden_materiality_insignificant_monetary():
    """Economically insignificant monetary movement is suppressed.

    Revenue change: $100 -> $200 (only $100 absolute change, below $1M).
    AR change: $50 -> $100 (only $50 absolute change, below $1M).
    Despite large percentage divergence, the signal is suppressed.
    """
    q2_current = o("revenue", 100, "2025-06-30")
    q2_prior = o("revenue", 200, "2024-06-30")
    ar_q2_current = o("accounts_receivable", 100, "2025-06-30", pt="INSTANT")
    ar_q2_prior = o("accounts_receivable", 50, "2024-06-30", pt="INSTANT")

    signals = evaluate("ABC", [q2_current, q2_prior, ar_q2_current, ar_q2_prior])
    div = next(
        (s for s in signals if s.signal_id == "RECEIVABLES_REVENUE_DIVERGENCE"),
        None
    )

    assert div is not None
    assert div.suppressed_reason == "economic insignificance"


def test_golden_materiality_incomparable():
    """Incomparable data produces a suppressed signal, not false positive."""
    q2_current = o("revenue", 10_000_000, "2025-06-30")
    q2_prior = Observation(
        "ABC", "revenue", 5_000_000, "USD", date(2024, 6, 30), "QUARTER",
        DataQuality.REPORTED, (), comparable=False
    )
    ar_q2_current = o("accounts_receivable", 30_000_000, "2025-06-30", pt="INSTANT")
    ar_q2_prior = o("accounts_receivable", 10_000_000, "2024-06-30", pt="INSTANT")

    signals = evaluate("ABC", [q2_current, q2_prior, ar_q2_current, ar_q2_prior])
    div = next(
        (s for s in signals if s.signal_id == "RECEIVABLES_REVENUE_DIVERGENCE"),
        None
    )

    # The incomparable prior revenue should cause suppression.
    # _comparable_pair skips non-comparable observations for value selection,
    # so without a valid prior, no signal should be generated.
    # If it IS generated, it must be suppressed.
    if div is not None:
        assert div.suppressed_reason is not None


def test_golden_materiality_ratio_no_monetary_floor():
    """Ratio-based signals (margins) should NOT apply the $1M monetary floor.

    Operating margin 0.1 -> 0.2 is a 10pp decline — this should fire even
    though the absolute difference is 0.1 (far below $1M).
    """
    from financial_radar.signals_phase2 import operating_deleverage
    current_margin = o("operating_margin", 0.10, "2025-06-30")
    prior_margin = o("operating_margin", 0.20, "2024-06-30")

    sig = operating_deleverage(current_margin, prior_margin)
    assert sig is not None
    assert sig.actionable  # NOT suppressed
    assert sig.severity in ("HIGH", "MODERATE")


# ---------------------------------------------------------
# PRIORITY 6: MULTI-SIGNAL CLUSTER LOGIC
# ---------------------------------------------------------
def test_golden_multi_factor_cluster():
    """Cluster requires at least 3 valid unsuppressed signals.

    Uses realistic $ values (>$1M) so divergence signals fire.
    Also includes margin compression (ratio-based, no monetary floor).
    """
    rev_c = o("revenue", 100_000_000, "2025-06-30")
    rev_p = o("revenue", 200_000_000, "2024-06-30")

    ar_c = o("accounts_receivable", 300_000_000, "2025-06-30", pt="INSTANT")
    ar_p = o("accounts_receivable", 100_000_000, "2024-06-30", pt="INSTANT")

    inv_c = o("inventory", 400_000_000, "2025-06-30", pt="INSTANT")
    inv_p = o("inventory", 100_000_000, "2024-06-30", pt="INSTANT")

    gp_c = o("gross_profit", 20_000_000, "2025-06-30")
    gp_p = o("gross_profit", 150_000_000, "2024-06-30")

    obs = [rev_c, rev_p, ar_c, ar_p, inv_c, inv_p, gp_c, gp_p]
    signals = evaluate("ABC", obs)

    cluster_sig = next(
        (s for s in signals if s.signal_id == "MULTI_FACTOR_DETERIORATION_CLUSTER"),
        None
    )
    assert cluster_sig is not None
    assert cluster_sig.severity == "HIGH"
    assert set(cluster_sig.component_signal_ids) == {
        "RECEIVABLES_REVENUE_DIVERGENCE",
        "INVENTORY_SALES_DIVERGENCE",
        "GROSS_MARGIN_COMPRESSION",
    }


def test_golden_cluster_requires_same_comparison_window():
    """Signals from different comparison windows cannot form a cluster."""
    current_window = (
        o("metric", 2, "2025-06-30"),
        o("metric", 1, "2024-06-30"),
    )
    older_window = (
        o("metric", 2, "2024-06-30"),
        o("metric", 1, "2023-06-30"),
    )
    component_signals = [
        Signal("SIGNAL_A", "ABC", "HIGH", "HIGH", "A", current_window),
        Signal("SIGNAL_B", "ABC", "HIGH", "HIGH", "B", current_window),
        Signal("SIGNAL_C", "ABC", "HIGH", "HIGH", "C", older_window),
    ]

    assert cluster(component_signals) == []


def test_golden_cluster_ignores_suppressed():
    """Cluster ignores suppressed signals — small values produce suppressed divergence."""
    rev_c = o("revenue", 100, "2025-06-30")
    rev_p = o("revenue", 200, "2024-06-30")
    ar_c = o("accounts_receivable", 300, "2025-06-30", pt="INSTANT")
    ar_p = o("accounts_receivable", 100, "2024-06-30", pt="INSTANT")
    inv_c = o("inventory", 400, "2025-06-30", pt="INSTANT")
    inv_p = o("inventory", 100, "2024-06-30", pt="INSTANT")
    gp_c = o("gross_profit", -50, "2025-06-30")
    gp_p = o("gross_profit", 150, "2024-06-30")

    obs = [rev_c, rev_p, ar_c, ar_p, inv_c, inv_p, gp_c, gp_p]
    signals = evaluate("ABC", obs)

    # Divergence signals are suppressed (< $1M) but margin compression
    # IS ratio-based and WILL fire. So we should NOT get a 3-signal cluster.
    cluster_sig = next(
        (s for s in signals if s.signal_id == "MULTI_FACTOR_DETERIORATION_CLUSTER"),
        None
    )
    assert cluster_sig is None


# ---------------------------------------------------------
# PRIORITY 4: EVENT EXTRACTION
# ---------------------------------------------------------
def test_golden_event_extraction():
    """Events extracted from filing text with conservative matching."""
    text = "The company completed multiple business combinations and acquisitions."
    events = extract_events("ABC", {"accessionNumber": "1", "filingDate": "2025-01-01"}, text)
    assert any(e["type"] == "acquisition" for e in events)


def test_golden_irrelevant_event_keyword():
    """Irrelevant occurrence must not become an event due to word boundary."""
    text = "The company recorded a nonacquisition expense."
    events = extract_events("ABC", {"accessionNumber": "1", "filingDate": "2025-01-01"}, text)
    assert not any(e["type"] == "acquisition" for e in events)


def test_golden_event_idempotent():
    """Same filing text produces identical event IDs."""
    text = "The company completed an acquisition."
    filing = {"accessionNumber": "1", "filingDate": "2025-01-01"}
    e1 = extract_events("ABC", filing, text)
    e2 = extract_events("ABC", filing, text)
    assert e1[0]["id"] == e2[0]["id"]


def test_golden_event_no_filing_text():
    """Empty/missing filing text produces no events."""
    assert extract_events("ABC", {"accessionNumber": "1"}, "") == []
    assert extract_events("ABC", {"accessionNumber": "1"}, None) == []


# ---------------------------------------------------------
# PRIORITY 7: PROVENANCE
# ---------------------------------------------------------
def test_golden_signal_provenance_chain():
    """Signal evidence preserves provenance to source XBRL filing."""
    p = Provenance(
        "ACC001", "https://sec.gov/filing", date(2025, 7, 25),
        "10-Q", "RevenueFromContractWithCustomerExcludingAssessedTax",
        datetime(2025, 7, 25), 200_000_000
    )
    rev_c = Observation(
        "ABC", "revenue", 200_000_000, "USD", date(2025, 6, 30),
        "QUARTER", DataQuality.REPORTED, (p,)
    )
    rev_p = Observation(
        "ABC", "revenue", 100_000_000, "USD", date(2024, 6, 30),
        "QUARTER", DataQuality.REPORTED, (p,)
    )
    ar_c = Observation(
        "ABC", "accounts_receivable", 300_000_000, "USD", date(2025, 6, 30),
        "INSTANT", DataQuality.REPORTED, (p,)
    )
    ar_p = Observation(
        "ABC", "accounts_receivable", 100_000_000, "USD", date(2024, 6, 30),
        "INSTANT", DataQuality.REPORTED, (p,)
    )

    sigs = evaluate("ABC", [rev_c, rev_p, ar_c, ar_p])
    hit = next(s for s in sigs if s.signal_id == "RECEIVABLES_REVENUE_DIVERGENCE")

    # Trace: signal -> evidence observation -> provenance -> accession
    assert hit.evidence[0].provenance[0].accession == "ACC001"
    assert hit.evidence[0].provenance[0].source_url == "https://sec.gov/filing"
    assert hit.version == "v1"
