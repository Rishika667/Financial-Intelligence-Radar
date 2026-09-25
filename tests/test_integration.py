import json
import logging
from datetime import date
import sqlite3

from financial_radar.models import (
    Observation,
    DataQuality,
    Provenance,
    Signal,
)
from financial_radar.store import (
    connect,
    save_watchlist,
    save_observations,
    save_signals,
    save_peer_context,
    rows,
)
from financial_radar.pipeline import _ratio
from financial_radar.events import extract_events


def _prov(dt="2025-01-01"):
    return Provenance("0001", "url", date.fromisoformat(dt), "10-Q", "rev", 100)


def o(m, v):
    return Observation(
        "ABC", m, v, "USD", date(2025, 6, 30), "QUARTER", DataQuality.REPORTED
    )


def test_mismatched_period_end_ratio_calculation():
    gp = Observation(
        "ABC", "gross_profit", 50, "USD",
        date(2025, 6, 30), "QUARTER", DataQuality.REPORTED,
    )
    rev = Observation(
        "ABC", "revenue", 100, "USD",
        date(2025, 3, 31), "QUARTER", DataQuality.REPORTED,
    )
    ratio = _ratio(gp, rev, "gross_margin")
    assert ratio.value is None
    assert ratio.quality == DataQuality.CALCULATION_INVALID
    assert ratio.comparable is False


def test_mismatched_currency_ratio_calculation():
    gp = Observation(
        "ABC", "gross_profit", 50, "EUR",
        date(2025, 6, 30), "QUARTER", DataQuality.REPORTED,
    )
    rev = Observation(
        "ABC", "revenue", 100, "USD",
        date(2025, 6, 30), "QUARTER", DataQuality.REPORTED,
    )
    ratio = _ratio(gp, rev, "gross_margin")
    assert ratio.value is None
    assert ratio.quality == DataQuality.CALCULATION_INVALID
    assert ratio.comparable is False


def test_mismatched_period_fcf():
    from financial_radar.core import free_cash_flow

    ocf = Observation(
        "ABC", "operating_cash_flow", 50, "USD",
        date(2025, 3, 31), "QUARTER", DataQuality.REPORTED,
    )
    capex = Observation(
        "ABC", "capex", -20, "USD",
        date(2025, 6, 30), "QUARTER", DataQuality.REPORTED,
    )
    fcf = free_cash_flow(ocf, capex)
    assert fcf.value is None
    assert fcf.quality == DataQuality.CALCULATION_INVALID
    assert fcf.comparable is False


def test_store_and_watchlist(tmp_path):
    c = connect(tmp_path / "x.sqlite")
    save_watchlist(c, [{"ticker": "ABC", "cik": "1", "active": True}])
    save_observations(c, [o("revenue", 2)])
    assert rows(c, "select * from watchlist")[0]["ticker"] == "ABC"
    assert rows(c, "select * from observations")[0]["value"] == 2


def test_persisted_signal_provenance_chain(tmp_path):
    c = connect(tmp_path / "x.sqlite")
    from financial_radar.signals import evaluate

    p = Provenance(
        "0001", "url", date(2025, 1, 1), "10-Q", "us-gaap_Revenues", 200_000_000
    )
    rev_c = Observation("ABC", "revenue", 200_000_000, "USD", date(2025, 6, 30), "QUARTER", DataQuality.REPORTED, (p,))
    rev_p = Observation("ABC", "revenue", 100_000_000, "USD", date(2024, 6, 30), "QUARTER", DataQuality.REPORTED, (p,))
    ar_c = Observation("ABC", "accounts_receivable", 300_000_000, "USD", date(2025, 6, 30), "INSTANT", DataQuality.REPORTED, (p,))
    ar_p = Observation("ABC", "accounts_receivable", 100_000_000, "USD", date(2024, 6, 30), "INSTANT", DataQuality.REPORTED, (p,))
    
    signals = evaluate("ABC", [rev_c, rev_p, ar_c, ar_p])
    hit = next(s for s in signals if s.signal_id == "RECEIVABLES_REVENUE_DIVERGENCE")
    save_signals(c, [hit])

    saved = rows(c, "SELECT evidence FROM signals")[0]["evidence"]
    ev = json.loads(saved)
    # verify nested provenance survives round trip
    assert "us-gaap_Revenues" in ev[0]["provenance"][0]["concept"]


def test_persisted_cluster_component_lineage(tmp_path):
    c = connect(tmp_path / "x.sqlite")
    obs_c = o("margin", 0.10)
    obs_p = Observation("ABC", "margin", 0.15, "pure", date(2024, 6, 30), "QUARTER", DataQuality.REPORTED)
    sig1 = Signal("S1", "ABC", "HIGH", "HIGH", "exp", (obs_c, obs_p))
    sig2 = Signal("S2", "ABC", "HIGH", "HIGH", "exp", (obs_c, obs_p))
    sig3 = Signal("S3", "ABC", "HIGH", "HIGH", "exp", (obs_c, obs_p))
    
    from financial_radar.signals_phase2 import cluster
    clustered = cluster([sig1, sig2, sig3])
    save_signals(c, clustered)
    
    persisted = rows(c, "SELECT * FROM signals WHERE signal_id='MARGIN_CONTRACTION_CLUSTER'")
    assert len(persisted) == 1
    row = persisted[0]

    components = json.loads(row["components"])
    assert isinstance(components, list)
    assert len(components) == 3
    assert set(components) == {"S1", "S2", "S3"}


def test_load_observations_for_companies(tmp_path):
    """Verify observations round-trip through SQLite correctly."""
    c = connect(tmp_path / "x.sqlite")
    obs1 = Observation(
        "ABC", "revenue", 100, "USD",
        date(2025, 6, 30), "QUARTER", DataQuality.REPORTED,
    )
    obs2 = Observation(
        "DEF", "revenue", 200, "USD",
        date(2025, 6, 30), "QUARTER", DataQuality.REPORTED,
    )
    save_observations(c, [obs1, obs2])
    from financial_radar.store import load_observations_for_companies

    loaded = load_observations_for_companies(c, ["ABC", "DEF"])
    assert len(loaded) == 2
    tickers = {o.company for o in loaded}
    assert tickers == {"ABC", "DEF"}
    for ob in loaded:
        assert ob.metric == "revenue"
        assert ob.quality == DataQuality.REPORTED


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
    save_filings(c, "12345", filings)
    res = rows(c, "SELECT * FROM filings")
    assert len(res) == 1


def test_derived_lineage(tmp_path):
    c = connect(tmp_path / "x.sqlite")
    ocf = Observation(
        "ABC", "operating_cash_flow", 100, "USD",
        date(2025, 6, 30), "QUARTER", DataQuality.REPORTED, (_prov(),),
    )
    cap = Observation(
        "ABC", "capex", -20, "USD",
        date(2025, 6, 30), "QUARTER", DataQuality.REPORTED, (_prov(),),
    )
    from financial_radar.core import free_cash_flow

    fcf = free_cash_flow(ocf, cap)
    assert fcf.derived_from == ("operating_cash_flow 2025-06-30 QUARTER", "capex 2025-06-30 QUARTER")

    sig = Signal("TEST", "ABC", "LOW", "LOW", "Test", (fcf,))
    save_signals(c, [sig])
    saved = rows(c, "SELECT evidence FROM signals")[0]["evidence"]
    ev = json.loads(saved)
    assert ev[0]["derived_from"] == ["operating_cash_flow 2025-06-30 QUARTER", "capex 2025-06-30 QUARTER"]


def test_production_peer_pipeline(tmp_path, monkeypatch):
    """End-to-end: ingest -> persist -> reload -> peer context -> persist -> retrieve."""
    c = connect(tmp_path / "x.sqlite")

    pg = {"version": "v1", "groups": [{"id": "G1", "members": ["ABC", "DEF", "GHI"]}]}

    class MockClient:
        delay = 0
        last = 0
        class s:
            @staticmethod
            def get(*a, **kw):
                raise RuntimeError("no 8-K fetch in test")

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
                                        "start": "2025-04-01",
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
    import financial_radar.pipeline

    monkeypatch.setattr(
        financial_radar.pipeline,
        "load_peer_groups",
        lambda p="config/peer_groups.json": pg,
    )

    # Ingest peer DEF first
    ingest_company(MockClient(), c, {"ticker": "DEF", "cik": "2"})
    ingest_company(MockClient(), c, {"ticker": "GHI", "cik": "3"})

    # Ingest primary ABC — peer context should load DEF from DB
    res = ingest_company(MockClient(), c, {"ticker": "ABC", "cik": "1"})

    # Verify peer context was generated
    pctx = rows(
        c, "SELECT * FROM peer_context WHERE company='ABC' AND metric='revenue'"
    )
    assert len(pctx) == 1
    assert pctx[0]["n_peers"] == 2

    # Verify safe failure handling
    def failing_load(*args, **kwargs):
        raise Exception("Mock failure")

    monkeypatch.setattr(financial_radar.pipeline, "load_peer_groups", failing_load)

    res2 = ingest_company(MockClient(), c, {"ticker": "ABC", "cik": "1"})
    assert res2["peer_group"] is None


def test_observation_idempotence(tmp_path):
    """Repeated saves with different provenance timestamps must not duplicate rows."""
    c = connect(tmp_path / "x.sqlite")
    p1 = _prov(dt="2025-01-01")
    p2 = _prov(dt="2025-01-02")

    o1 = Observation(
        "ABC", "revenue", 100, "USD",
        date(2025, 6, 30), "QUARTER", DataQuality.REPORTED, (p1,),
    )
    save_observations(c, [o1])

    o2 = Observation(
        "ABC", "revenue", 100, "USD",
        date(2025, 6, 30), "QUARTER", DataQuality.REPORTED, (p2,),
    )
    save_observations(c, [o2])

    res = rows(c, "SELECT * FROM observations WHERE company='ABC' AND metric='revenue'")
    assert len(res) == 1
    prov = json.loads(res[0]["provenance"])
    assert "2025-01-02" in prov[0]["filing_date"]


# --- Event extraction regression tests ---

def test_event_positive_acquisition():
    """Positive completed acquisition should be extracted."""
    events = extract_events(
        "XYZ",
        {"accessionNumber": "ACC1", "filingDate": "2025-06-01", "source_url": "s", "form": "8-K"},
        "On June 1, the company completed an acquisition of Widget Corp for $500M.",
    )
    types = [e["type"] for e in events]
    assert "acquisition" in types


def test_event_negative_not_completed():
    """Negated acquisition should be suppressed."""
    events = extract_events(
        "XYZ",
        {"accessionNumber": "ACC2", "filingDate": "2025-06-01", "source_url": "s", "form": "8-K"},
        "The company did not complete the acquisition.",
    )
    types = [e["type"] for e in events]
    assert "acquisition" not in types


def test_event_terminated():
    """Terminated acquisition should be suppressed via postfix check."""
    events = extract_events(
        "XYZ",
        {"accessionNumber": "ACC3", "filingDate": "2025-06-01", "source_url": "s", "form": "8-K"},
        "The previously announced acquisition was terminated effective immediately.",
    )
    types = [e["type"] for e in events]
    assert "acquisition" not in types


def test_event_historical_conditional():
    """Historical/conditional mention of litigation should still extract."""
    events = extract_events(
        "XYZ",
        {"accessionNumber": "ACC4", "filingDate": "2025-06-01", "source_url": "s", "form": "8-K"},
        "The company is currently involved in litigation regarding patent infringement.",
    )
    types = [e["type"] for e in events]
    assert "legal" in types


def test_observation_with_period_start_roundtrip(tmp_path):
    """period_start survives save/load cycle."""
    c = connect(tmp_path / "ps.sqlite")
    p = _prov()
    obs = Observation(
        "ABC", "revenue", 100, "USD",
        date(2025, 6, 30), "QUARTER", DataQuality.REPORTED, (p,),
        (), True, None, date(2025, 4, 1),
    )
    save_observations(c, [obs])
    from financial_radar.store import load_observations_for_companies
    loaded = load_observations_for_companies(c, ["ABC"])
    assert len(loaded) == 1
    assert loaded[0].period_start == date(2025, 4, 1)
    assert loaded[0].metric == "revenue"
    assert loaded[0].value == 100
