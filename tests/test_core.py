from datetime import date
from financial_radar.core import pct_change, derive_standalone_quarter, free_cash_flow
from financial_radar.models import Observation, Provenance, DataQuality
import datetime


def _prov():
    return Provenance(
        "0001", "https://sec.example", date(2025, 1, 1),
        "10-Q", "Revenue", datetime.datetime(2025, 1, 1),
    )


def o(metric, value, end, pt="QUARTER", quality=DataQuality.REPORTED):
    return Observation(
        "ABC", metric, value, "USD", end, pt, quality, (_prov(),)
    )


def test_pct_change_normal():
    assert pct_change(120, 100) == 0.2


def test_pct_change_zero_prior():
    assert pct_change(100, 0) is None


def test_pct_change_none_values():
    assert pct_change(None, 100) is None
    assert pct_change(100, None) is None


def test_standalone_quarter_valid():
    ytd = o("revenue", 300, date(2025, 6, 30), "YTD_6M")
    prior_ytd = o("revenue", 100, date(2025, 3, 31), "QUARTER")
    sq = derive_standalone_quarter(ytd, prior_ytd)
    assert sq.value == 200
    assert sq.period_type == "QUARTER"
    assert sq.quality == DataQuality.DERIVED


def test_standalone_quarter_missing_value():
    ytd = o("revenue", None, date(2025, 6, 30), "YTD_6M")
    prior_ytd = o("revenue", 100, date(2025, 3, 31), "QUARTER")
    sq = derive_standalone_quarter(ytd, prior_ytd)
    assert sq.value is None
    assert sq.quality == DataQuality.CALCULATION_INVALID


def test_standalone_quarter_mismatched_metrics():
    ytd = o("revenue", 300, date(2025, 6, 30), "YTD_6M")
    prior_ytd = o("gross_profit", 100, date(2025, 3, 31), "QUARTER")
    sq = derive_standalone_quarter(ytd, prior_ytd)
    assert sq.quality == DataQuality.CALCULATION_INVALID
    assert sq.comparable is False


def test_standalone_quarter_wrong_period_type():
    ytd = Observation(
        "ABC", "revenue", 300, "USD", date(2025, 6, 30),
        "ANNUAL", DataQuality.REPORTED, (_prov(),),
    )
    prior_ytd = o("revenue", 100, date(2025, 3, 31), "QUARTER")
    sq = derive_standalone_quarter(ytd, prior_ytd)
    assert sq.quality == DataQuality.CALCULATION_INVALID


def test_free_cash_flow_normal():
    ocf = o("operating_cash_flow", 500, date(2025, 6, 30), "QUARTER")
    capex = o("capex", -100, date(2025, 6, 30), "QUARTER")
    fcf = free_cash_flow(ocf, capex)
    assert fcf.value == 400
    assert fcf.metric == "free_cash_flow"
    assert fcf.quality == DataQuality.DERIVED


def test_free_cash_flow_missing_input():
    ocf = o("operating_cash_flow", None, date(2025, 6, 30), "QUARTER")
    capex = o("capex", -100, date(2025, 6, 30), "QUARTER")
    fcf = free_cash_flow(ocf, capex)
    assert fcf.value is None
    assert fcf.quality == DataQuality.CALCULATION_INVALID


def test_free_cash_flow_incomparable_input():
    ocf = Observation(
        "ABC", "operating_cash_flow", 500, "USD", date(2025, 6, 30),
        "QUARTER", DataQuality.REPORTED, (_prov(),), comparable=False,
    )
    capex = o("capex", -100, date(2025, 6, 30), "QUARTER")
    fcf = free_cash_flow(ocf, capex)
    assert fcf.quality == DataQuality.CALCULATION_INVALID

def test_historical_submissions(tmp_path, monkeypatch):
    from financial_radar.core import SECClient
    import json

    client = SECClient("test@example.com", raw_dir=str(tmp_path))
    
    # Mock requests.Session.get
    class MockResponse:
        def __init__(self, data):
            self._data = data
        def raise_for_status(self):
            pass
        def json(self):
            return self._data
            
    def mock_get(url, timeout=30):
        if "CIK0000000001.json" in url:
            return MockResponse({
                "filings": {
                    "recent": {"accessionNumber": ["111-222"]},
                    "files": [{"name": "CIK0000000001-submissions-001.json"}]
                }
            })
        elif "CIK0000000001-submissions-001.json" in url:
            return MockResponse({"accessionNumber": ["333-444"]})
        raise ValueError(f"Unexpected url: {url}")
        
    monkeypatch.setattr(client.s, "get", mock_get)
    
    # Test without fetch_historical
    res1 = client.submissions("1", fetch_historical=False)
    assert res1["filings"]["recent"]["accessionNumber"] == ["111-222"]
    
    # Test with fetch_historical
    res2 = client.submissions("1", fetch_historical=True)
    assert "333-444" in res2["filings"]["recent"]["accessionNumber"]

