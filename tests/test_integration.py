import json
import logging
from datetime import date, datetime
from financial_radar.models import Observation, DataQuality, Provenance, Signal
from financial_radar.store import (
    connect,
    save_watchlist,
    save_observations,
    rows,
    save_signals,
)
from financial_radar.pipeline import evaluate
from financial_radar.events import extract_events
from financial_radar.signals import divergence, cluster


def _prov(dt="2025-07-25"):
    return Provenance(
        "ACC001",
        "https://sec.gov/filing",
        date.fromisoformat(dt),
        "10-Q",
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        datetime(2025, 7, 25),
        200_000_000,
    )


def o(m, v):
    return Observation(
        "ABC", m, v, "USD", date(2025, 6, 30), "QUARTER", DataQuality.REPORTED
    )


def test_store_and_watchlist(tmp_path):
    c = connect(tmp_path / "x.sqlite")
    save_watchlist(c, [{"ticker": "ABC", "cik": "1", "active": True}])
    save_observations(c, [o("revenue", 2)])
    assert rows(c, "select * from watchlist")[0]["ticker"] == "ABC"
    assert rows(c, "select * from observations")[0]["value"] == 2


def test_leverage_direction_and_event():
    """Leverage signal fires (ratio-based, no monetary floor)."""
    from financial_radar.signals_phase2 import leverage

    sig = leverage(o("debt", 300), o("ebit", 100), o("debt", 100), o("ebit", 100))
    assert sig is not None
    assert sig.actionable

    events = extract_events(
        "ABC",
        {"accessionNumber": "x", "filingDate": "2025-01-01", "source_url": "s"},
        "The company completed an acquisition.",
    )
    assert events


def test_persisted_signal_provenance_chain(tmp_path):
    """Verify the full signal->evidence->provenance->SEC URL chain survives SQLite.

    This is the critical traceability test: a signal read back from the
    database must contain enough information to trace every evidence
    observation to its source XBRL concept, accession number, filing form,
    filing date, and SEC source URL.
    """
    c = connect(tmp_path / "prov.sqlite")

    p = _prov()
    rev_c = Observation(
        "ABC",
        "revenue",
        200_000_000,
        "USD",
        date(2025, 6, 30),
        "QUARTER",
        DataQuality.REPORTED,
        (p,),
    )
    rev_p = Observation(
        "ABC",
        "revenue",
        100_000_000,
        "USD",
        date(2024, 6, 30),
        "QUARTER",
        DataQuality.REPORTED,
        (p,),
    )
    ar_c = Observation(
        "ABC",
        "accounts_receivable",
        300_000_000,
        "USD",
        date(2025, 6, 30),
        "INSTANT",
        DataQuality.REPORTED,
        (p,),
    )
    ar_p = Observation(
        "ABC",
        "accounts_receivable",
        100_000_000,
        "USD",
        date(2024, 6, 30),
        "INSTANT",
        DataQuality.REPORTED,
        (p,),
    )

    signals = evaluate("ABC", [rev_c, rev_p, ar_c, ar_p])
    hit = next(s for s in signals if s.signal_id == "RECEIVABLES_REVENUE_DIVERGENCE")

    # Persist to SQLite
    save_signals(c, [hit])

    # Read back from SQLite
    persisted = rows(
        c, "SELECT * FROM signals WHERE signal_id='RECEIVABLES_REVENUE_DIVERGENCE'"
    )
    assert len(persisted) == 1
    row = persisted[0]

    # Parse the evidence JSON
    evidence = json.loads(row["evidence"])

    # Verify evidence is a list of observation dicts with full provenance
    assert isinstance(evidence, list)
    assert len(evidence) >= 2  # at least revenue + AR observations

    # Trace at least one evidence observation to its provenance
    obs = evidence[0]
    assert "metric" in obs
    assert "value" in obs
    assert "unit" in obs
    assert "period_end" in obs
    assert "quality" in obs
    assert "provenance" in obs

    # Trace the provenance to SEC source
    prov = obs["provenance"]
    assert isinstance(prov, list)
    assert len(prov) >= 1
    p0 = prov[0]
    assert p0["accession"] == "ACC001"
    assert p0["source_url"] == "https://sec.gov/filing"
    assert p0["form"] == "10-Q"
    assert p0["concept"] == "RevenueFromContractWithCustomerExcludingAssessedTax"
    assert p0["filing_date"] == "2025-07-25"
    assert p0["raw_value"] == 200_000_000

    # Verify the signal metadata
    assert row["severity"] == "HIGH"
    assert row["version"] == "v1"
    assert row["suppressed"] is None


def test_mismatched_period_end_divergence():
    rev_c = Observation(
        "ABC",
        "revenue",
        200_000_000,
        "USD",
        date(2025, 6, 30),
        "QUARTER",
        DataQuality.REPORTED,
    )
    rev_p = Observation(
        "ABC",
        "revenue",
        100_000_000,
        "USD",
        date(2024, 6, 30),
        "QUARTER",
        DataQuality.REPORTED,
    )
    # AR current is deliberately from March instead of June
    ar_c = Observation(
        "ABC",
        "accounts_receivable",
        300_000_000,
        "USD",
        date(2025, 3, 31),
        "INSTANT",
        DataQuality.REPORTED,
    )
    ar_p = Observation(
        "ABC",
        "accounts_receivable",
        100_000_000,
        "USD",
        date(2024, 6, 30),
        "INSTANT",
        DataQuality.REPORTED,
    )

    sig = divergence("RECEIVABLES_REVENUE_DIVERGENCE", ar_c, rev_c, ar_p, rev_p)
    assert sig is not None
    assert sig.suppressed_reason == "misaligned periods"
    assert sig.actionable is False


def test_mismatched_period_end_ratio_calculation():
    from financial_radar.pipeline import _ratio

    gp = Observation(
        "ABC",
        "gross_profit",
        50,
        "USD",
        date(2025, 3, 31),
        "QUARTER",
        DataQuality.REPORTED,
    )
    rev = Observation(
        "ABC", "revenue", 100, "USD", date(2025, 6, 30), "QUARTER", DataQuality.REPORTED
    )
    ratio = _ratio(gp, rev, "gross_margin")
    assert ratio.value is None
    assert ratio.quality == DataQuality.CALCULATION_INVALID
    assert ratio.comparable is False


def test_mismatched_currency_ratio_calculation():
    from financial_radar.pipeline import _ratio

    gp = Observation(
        "ABC",
        "gross_profit",
        50,
        "USD",
        date(2025, 6, 30),
        "QUARTER",
        DataQuality.REPORTED,
    )
    rev = Observation(
        "ABC", "revenue", 100, "EUR", date(2025, 6, 30), "QUARTER", DataQuality.REPORTED
    )
    ratio = _ratio(gp, rev, "gross_margin")
    assert ratio.value is None
    assert ratio.quality == DataQuality.CALCULATION_INVALID
    assert ratio.comparable is False


def test_mismatched_period_fcf():
    from financial_radar.core import free_cash_flow

    ocf = Observation(
        "ABC",
        "operating_cash_flow",
        50,
        "USD",
        date(2025, 3, 31),
        "QUARTER",
        DataQuality.REPORTED,
    )
    capex = Observation(
        "ABC", "capex", -20, "USD", date(2025, 6, 30), "QUARTER", DataQuality.REPORTED
    )
    fcf = free_cash_flow(ocf, capex)
    assert fcf.value is None
    assert fcf.quality == DataQuality.CALCULATION_INVALID
    assert fcf.comparable is False


def test_persisted_cluster_component_lineage(tmp_path):
    c = connect(tmp_path / "prov.sqlite")

    p = _prov()
    obs_c = Observation(
        "ABC",
        "metric",
        1,
        "USD",
        date(2025, 6, 30),
        "QUARTER",
        DataQuality.REPORTED,
        (p,),
    )
    obs_p = Observation(
        "ABC",
        "metric",
        1,
        "USD",
        date(2024, 6, 30),
        "QUARTER",
        DataQuality.REPORTED,
        (p,),
    )

    sig1 = Signal("S1", "ABC", "HIGH", "HIGH", "exp", (obs_c, obs_p))
    sig2 = Signal("S2", "ABC", "HIGH", "HIGH", "exp", (obs_c, obs_p))
    sig3 = Signal("S3", "ABC", "HIGH", "HIGH", "exp", (obs_c, obs_p))

    clustered = cluster([sig1, sig2, sig3])
    assert len(clustered) == 1
    hit = clustered[0]

    save_signals(c, [hit])
    persisted = rows(
        c, "SELECT * FROM signals WHERE signal_id='MULTI_FACTOR_DETERIORATION_CLUSTER'"
    )
    row = persisted[0]

    components = json.loads(row["components"])
    assert isinstance(components, list)
    assert len(components) == 3
    assert set(components) == {"S1", "S2", "S3"}


def test_load_observations_for_companies(tmp_path):
    c = connect(tmp_path / "x.sqlite")
    obs1 = Observation(
        "ABC", "revenue", 100, "USD", date(2025, 6, 30), "QUARTER", DataQuality.REPORTED
    )
    obs2 = Observation(
        "DEF", "revenue", 200, "USD", date(2025, 6, 30), "QUARTER", DataQuality.REPORTED
    )
    save_observations(c, [obs1, obs2])
    from financial_radar.store import load_observations_for_companies

    loaded = load_observations_for_companies(c, ["ABC", "DEF"])
    assert len(loaded) == 2


def test_filing_persistence_idempotence(tmp_path):
    c = connect(tmp_path / "x.sqlite")
    from financial_radar.store import save_filings

    filings = {
        "0001": {
            "accessionNumber": "0001",
            "form": "10-Q",
            "filingDate": "2025-01-01",
            "source_url": "http://sec.gov",
        }
    }
    save_filings(c, "12345", filings)
    save_filings(c, "12345", filings)  # Should not raise IntegrityError
    res = rows(c, "SELECT * FROM filings")
    assert len(res) == 1


def test_derived_lineage(tmp_path):
    c = connect(tmp_path / "x.sqlite")
    ocf = Observation(
        "ABC",
        "operating_cash_flow",
        100,
        "USD",
        date(2025, 6, 30),
        "QUARTER",
        DataQuality.REPORTED,
        (_prov(),),
    )
    cap = Observation(
        "ABC",
        "capex",
        -20,
        "USD",
        date(2025, 6, 30),
        "QUARTER",
        DataQuality.REPORTED,
        (_prov(),),
    )
    from financial_radar.core import free_cash_flow

    fcf = free_cash_flow(ocf, cap)
    assert fcf.derived_from == ("operating_cash_flow", "capex")

    sig = Signal("TEST", "ABC", "LOW", "LOW", "Test", (fcf,))
    save_signals(c, [sig])
    saved = rows(c, "SELECT evidence FROM signals")[0]["evidence"]
    ev = json.loads(saved)
    assert ev[0]["derived_from"] == ["operating_cash_flow", "capex"]


def test_production_peer_pipeline(tmp_path, monkeypatch):
    c = connect(tmp_path / "x.sqlite")

    # Setup mock peer group
    pg = {"version": "v1", "groups": [{"id": "G1", "members": ["ABC", "DEF"]}]}

    # Mock SEC client
    class MockClient:
        def submissions(self, cik):
            return {
                "filings": {
                    "recent": {
                        "accessionNumber": ["0001"],
                        "form": ["10-Q"],
                        "filingDate": ["2025-01-01"],
                        "primaryDocument": ["doc.htm"],
                    }
                }
            }

        def company_facts(self, cik):
            return {
                "facts": {
                    "us-gaap": {
                        "Revenues": {
                            "units": {
                                "USD": [
                                    {
                                        "accn": "0001",
                                        "filed": "2025-01-01",
                                        "end": "2025-06-30",
                                        "val": 100,
                                        "form": "10-Q",
                                    }
                                ]
                            }
                        }
                    }
                }
            }

    from financial_radar.pipeline import ingest_company
    import financial_radar.peers
    import financial_radar.pipeline

    monkeypatch.setattr(
        financial_radar.pipeline,
        "load_peer_groups",
        lambda p="config/peer_groups.json": pg,
    )

    ingest_company(MockClient(), c, {"ticker": "DEF", "cik": "2"})

    # Ingest primary ABC
    res = ingest_company(MockClient(), c, {"ticker": "ABC", "cik": "1"})

    # Verify peer context was generated using DEF's data
    pctx = rows(
        c, "SELECT * FROM peer_context WHERE company='ABC' AND metric='revenue'"
    )
    assert len(pctx) == 1
    assert pctx[0]["n_peers"] == 1  # DEF is the only peer

    # Verify safe failure handling (if peer calculation fails, no unhandled exception)
    def failing_load(*args, **kwargs):
        raise Exception("Mock failure")

    monkeypatch.setattr(financial_radar.pipeline, "load_peer_groups", failing_load)

    res2 = ingest_company(MockClient(), c, {"ticker": "ABC", "cik": "1"})
    assert res2["peer_group"] is None


def test_observation_idempotence(tmp_path):
    c = connect(tmp_path / "x.sqlite")
    p1 = _prov(dt="2025-01-01")
    p2 = _prov(dt="2025-01-02")

    # Save the same observation with different provenance timestamps
    o1 = Observation(
        "ABC",
        "revenue",
        100,
        "USD",
        date(2025, 6, 30),
        "QUARTER",
        DataQuality.REPORTED,
        (p1,),
    )
    save_observations(c, [o1])

    o2 = Observation(
        "ABC",
        "revenue",
        100,
        "USD",
        date(2025, 6, 30),
        "QUARTER",
        DataQuality.REPORTED,
        (p2,),
    )
    save_observations(c, [o2])

    # Should only be one row!
    res = rows(c, "SELECT * FROM observations WHERE company='ABC'")
    assert len(res) == 1
    # Should have the latest provenance
    prov = json.loads(res[0]["provenance"])
    assert "2025-01-02" in prov[0]["filing_date"]
