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


def test_mismatched_period_end_ratio_calculation():
    from financial_radar.metrics import derive_analytical_metrics

    gp = Observation(
        "ABC", "gross_profit", 50, "USD",
        date(2025, 6, 30), "QUARTER", DataQuality.REPORTED,
    )
    rev = Observation(
        "ABC", "revenue", 100, "USD",
        date(2025, 3, 31), "QUARTER", DataQuality.REPORTED,
    )
    
    # Passing both into derivation should NOT yield a gross margin for Q2
    # because they have different period ends and won't group together.
    derived = derive_analytical_metrics([gp, rev])
    has_gm = any(o.metric == "gross_margin" for o in derived)
    assert not has_gm, "Should not derive ratio from mismatched period ends"


def test_mismatched_currency_ratio_calculation():
    from financial_radar.metrics import derive_analytical_metrics

    gp = Observation(
        "ABC", "gross_profit", 50, "EUR",
        date(2025, 6, 30), "QUARTER", DataQuality.REPORTED,
    )
    rev = Observation(
        "ABC", "revenue", 100, "USD",
        date(2025, 6, 30), "QUARTER", DataQuality.REPORTED,
    )
    
    # Passing both into derivation should NOT yield a gross margin
    # because they have different units and unit is in the grouping key.
    derived = derive_analytical_metrics([gp, rev])
    has_gm = any(o.metric == "gross_margin" for o in derived)
    assert not has_gm, "Should not derive ratio from mismatched currencies"


def test_store_and_watchlist(tmp_path):
    c = connect(tmp_path / "x.sqlite")
    save_watchlist(c, [{"ticker": "ABC", "cik": "1", "active": True}])
    save_observations(c, [o("revenue", 2)])
    assert rows(c, "select * from watchlist")[0]["ticker"] == "ABC"
    assert rows(c, "select * from observations")[0]["value"] == 2


def test_persisted_signal_provenance_chain(tmp_path):
    c = connect(tmp_path / "prov.sqlite")

    p = _prov()
    rev_c = Observation(
        "ABC", "revenue", 200_000_000, "USD",
        date(2025, 6, 30), "QUARTER", DataQuality.REPORTED, (p,),
    )
    rev_p = Observation(
        "ABC", "revenue", 100_000_000, "USD",
        date(2024, 6, 30), "QUARTER", DataQuality.REPORTED, (p,),
    )
    ar_c = Observation(
        "ABC", "accounts_receivable", 300_000_000, "USD",
        date(2025, 6, 30), "INSTANT", DataQuality.REPORTED, (p,),
    )
    ar_p = Observation(
        "ABC", "accounts_receivable", 100_000_000, "USD",
        date(2024, 6, 30), "INSTANT", DataQuality.REPORTED, (p,),
    )
    signals = evaluate("ABC", [rev_c, rev_p, ar_c, ar_p, Observation("ABC", "receivables_revenue_ratio", 1.5, "pure", date(2025, 6, 30), "QUARTER", DataQuality.REPORTED, (p,)), Observation("ABC", "receivables_revenue_ratio", 1.0, "pure", date(2024, 6, 30), "QUARTER", DataQuality.REPORTED, (p,))])
    hit = next(s for s in signals if s.signal_id == "RECEIVABLES_REVENUE_DIVERGENCE")

    save_signals(c, [hit])
    persisted = rows(
        c, "SELECT * FROM signals WHERE signal_id='RECEIVABLES_REVENUE_DIVERGENCE'"
    )
    assert len(persisted) == 1
    row = persisted[0]

    evidence = json.loads(row["evidence"])
    assert isinstance(evidence, list)
    assert len(evidence) >= 2

    obs = evidence[0]
    assert "metric" in obs
    assert "value" in obs
    assert "unit" in obs
    assert "period_end" in obs
    assert "quality" in obs
    assert "provenance" in obs

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

    assert row["severity"] == "HIGH"
    assert row["version"] == "v1"
    assert row["suppressed"] is None


def test_persisted_cluster_component_lineage(tmp_path):
    c = connect(tmp_path / "prov.sqlite")

    p = _prov()
    obs_c = Observation(
        "ABC", "metric", 1, "USD",
        date(2025, 6, 30), "QUARTER", DataQuality.REPORTED, (p,),
    )
    obs_p = Observation(
        "ABC", "metric", 1, "USD",
        date(2024, 6, 30), "QUARTER", DataQuality.REPORTED, (p,),
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
    import financial_radar.peers

    monkeypatch.setattr(
        financial_radar.peers,
        "load_peer_groups",
        lambda p="config/sp500_representative_51_2026.json": pg,
    )

    # Ingest peer DEF first
    ingest_company(MockClient(), c, {"ticker": "DEF", "cik": "2"})
    ingest_company(MockClient(), c, {"ticker": "GHI", "cik": "3"})

    # Ingest primary ABC — peer context should load DEF from DB
    res = ingest_company(MockClient(), c, {"ticker": "ABC", "cik": "1"})
    financial_radar.pipeline.refresh_peer_contexts(c, ["ABC", "DEF", "GHI"])

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

def test_readiness_stale_data(tmp_path):
    c = connect(tmp_path / "stale.sqlite")
    save_watchlist(c, [{"ticker": "ABC", "cik": "1", "active": True}])
    p = _prov()
    
    # Old annual data
    o1 = Observation("ABC", "revenue", 100, "USD", date(2020, 12, 31), "ANNUAL", DataQuality.REPORTED, (p,))
    o2 = Observation("ABC", "net_income", 10, "USD", date(2020, 12, 31), "ANNUAL", DataQuality.REPORTED, (p,))
    o3 = Observation("ABC", "operating_income", 20, "USD", date(2020, 12, 31), "ANNUAL", DataQuality.REPORTED, (p,))
    o4 = Observation("ABC", "operating_cash_flow", 30, "USD", date(2020, 12, 31), "ANNUAL", DataQuality.REPORTED, (p,))
    o5 = Observation("ABC", "cash_and_equivalents", 40, "USD", date(2020, 12, 31), "ANNUAL", DataQuality.REPORTED, (p,))
    
    save_observations(c, [o1, o2, o3, o4, o5])
    
    from financial_radar.pipeline import calculate_data_readiness
    from financial_radar.models import ReadinessState
    
    state, msg = calculate_data_readiness("ABC", c)
    assert state == ReadinessState.NOT_READY
    assert "quarterly" in msg.lower()

def test_sec_connectivity_behavior(monkeypatch):
    import sys; sys.path.append("."); import app
    
    # 1. Invalid/missing user agent -> failure
    res = app.test_sec_connectivity("")
    assert not res['USER_AGENT_CONFIGURED']
    assert "Invalid or missing" in res['ERRORS'][0]
    assert not all([res.get(k) for k in ('USER_AGENT_CONFIGURED', 'SEC_REACHABLE', 'SUBMISSIONS_REACHABLE', 'XBRL_REACHABLE')])
    
    # 2. Network exception -> visible diagnostic error
    import requests
    class MockRequests:
        @staticmethod
        def get(*args, **kwargs):
            raise requests.exceptions.RequestException("Mock Timeout")
    monkeypatch.setattr(requests, "get", MockRequests.get)
    
    res = app.test_sec_connectivity("valid_user@test.com")
    assert res['USER_AGENT_CONFIGURED']
    assert not res['SEC_REACHABLE']
    assert len(res["ERRORS"]) > 0
    
    # 3. All endpoints successful -> success
    class MockSuccess:
        @staticmethod
        def get(*args, **kwargs):
            class Response:
                def raise_for_status(self): pass
            return Response()
    monkeypatch.setattr(requests, "get", MockSuccess.get)
    
    res = app.test_sec_connectivity("valid_user@test.com")
    assert res['USER_AGENT_CONFIGURED']
    assert res['SEC_REACHABLE']
    assert res['SUBMISSIONS_REACHABLE']
    assert res['XBRL_REACHABLE']
    assert len(res['ERRORS']) == 0
    
    # 4. One endpoint fails -> failure
    class MockPartial:
        @staticmethod
        def get(url, *args, **kwargs):
            class Response:
                def raise_for_status(self): 
                    if "companyfacts" in url:
                        raise requests.exceptions.RequestException("Facts failed")
            return Response()
    monkeypatch.setattr(requests, "get", MockPartial.get)
    
    res = app.test_sec_connectivity("valid_user@test.com")
    assert res['SEC_REACHABLE']
    assert res['SUBMISSIONS_REACHABLE']
    assert not res['XBRL_REACHABLE']
    assert len(res["ERRORS"]) > 0

def test_portfolio_exposure_contract():
    import pandas as pd
    from financial_radar.pipeline import validate_portfolio_csv
    
    # Missing exposure -> failure
    df = pd.DataFrame({"ticker": ["ABC"], "shares": [10], "weight": [1.0], "cost_basis": [100]})
    is_valid, msg = validate_portfolio_csv(df, ["ABC"])
    assert not is_valid
    assert "exposure" in msg.lower()
    
    # With exposure -> success
    df_valid = pd.DataFrame({"ticker": ["ABC"], "shares": [10], "weight": [1.0], "cost_basis": [100], "exposure": [1000]})
    is_valid_valid, msg_valid = validate_portfolio_csv(df_valid, ["ABC"])
    assert is_valid_valid

def test_universe_contract_is_exactly_51():
    import json
    d = json.load(open("config/sp500_representative_51_2026.json"))
    assert len(d["companies"]) == 51, "Universe MUST be exactly 51 companies."
    assert "peer_references" in d, "peer_references must exist."
