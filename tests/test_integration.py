import json
from datetime import date
from financial_radar.store import connect, rows, save_observations, save_signals
from financial_radar.models import Observation, Provenance, DataQuality, Signal
from financial_radar.events import extract_events


def _prov(dt="2025-01-01"):
    return Provenance(
        "0001", "https://sec.example", date(2025, 1, 1),
        "10-Q", "Revenue", dt,
    )


def test_schema_creation(tmp_path):
    c = connect(tmp_path / "test.sqlite")
    tables = [
        r["name"]
        for r in rows(c, "SELECT name FROM sqlite_master WHERE type='table'")
    ]
    assert "observations" in tables
    assert "signals" in tables
    assert "watchlist" in tables


def test_watchlist_persistence(tmp_path):
    c = connect(tmp_path / "x.sqlite")
    from financial_radar.store import save_watchlist

    save_watchlist(c, [{"ticker": "ABC", "cik": "1", "active": True}])
    res = rows(c, "SELECT * FROM watchlist WHERE ticker='ABC'")
    assert len(res) == 1
    assert res[0]["active"] == 1
    assert res[0]["cik"] == "1"


def test_observation_persistence(tmp_path):
    c = connect(tmp_path / "x.sqlite")
    obs = Observation(
        "ABC", "revenue", 100, "USD",
        date(2025, 6, 30), "QUARTER", DataQuality.REPORTED, (_prov(),),
    )
    save_observations(c, [obs])
    res = rows(c, "SELECT * FROM observations WHERE company='ABC'")
    assert len(res) == 1
    assert res[0]["metric"] == "revenue"
    assert res[0]["value"] == 100
    assert res[0]["period_end"] == "2025-06-30"


def test_signal_persistence(tmp_path):
    c = connect(tmp_path / "x.sqlite")
    from financial_radar.store import clear_signals

    sig = Signal("TEST_SIG", "ABC", "HIGH", "HIGH", "Reason", ())
    save_signals(c, [sig])
    res = rows(c, "SELECT * FROM signals WHERE company='ABC'")
    assert len(res) == 1
    assert res[0]["signal_id"] == "TEST_SIG"

    clear_signals(c, "ABC")
    res2 = rows(c, "SELECT * FROM signals WHERE company='ABC'")
    assert len(res2) == 0


def test_peer_context_persistence(tmp_path):
    c = connect(tmp_path / "x.sqlite")
    from financial_radar.store import save_peer_context, clear_peer_context

    ctx = {
        "group_id": "TECH",
        "version": "v1",
        "contexts": [
            {
                "metric": "revenue",
                "company_value": 100,
                "peer_median": 120,
                "peer_range": (90, 150),
                "n_peers": 3,
                "peer_group_version": "v1",
                "group_id": "TECH",
            }
        ],
    }
    save_peer_context(c, "ABC", ctx)
    res = rows(c, "SELECT * FROM peer_context WHERE company='ABC'")
    assert len(res) == 1
    assert res[0]["group_id"] == "TECH"
    assert res[0]["peer_median"] == 120
    assert res[0]["peer_min"] == 90
    assert res[0]["peer_max"] == 150
    assert res[0]["version"] == "v1"

    clear_peer_context(c, "ABC")
    res2 = rows(c, "SELECT * FROM peer_context WHERE company='ABC'")
    assert len(res2) == 0


def test_load_observations_for_companies(tmp_path):
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

        def submissions(self, cik, fetch_historical=False):
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