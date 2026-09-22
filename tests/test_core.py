from datetime import date
from financial_radar.core import pct_change, derive_standalone_quarter, free_cash_flow
from financial_radar.models import Observation, Provenance, DataQuality
import datetime


def _prov():
    return Provenance(
        "0001", "https://sec.example", date(2025, 1, 1),
        "10-Q", "Revenue", datetime.datetime(2025, 1, 1),
    )


def o(metric, value, end, pt="YTD", quality=DataQuality.REPORTED):
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
    ytd = o("revenue", 300, date(2025, 6, 30))
    prior_ytd = o("revenue", 100, date(2025, 3, 31))
    sq = derive_standalone_quarter(ytd, prior_ytd)
    assert sq.value == 200
    assert sq.period_type == "QUARTER"
    assert sq.quality == DataQuality.DERIVED


def test_standalone_quarter_missing_value():
    ytd = o("revenue", None, date(2025, 6, 30))
    prior_ytd = o("revenue", 100, date(2025, 3, 31))
    sq = derive_standalone_quarter(ytd, prior_ytd)
    assert sq.value is None
    assert sq.quality == DataQuality.CALCULATION_INVALID


def test_standalone_quarter_mismatched_metrics():
    ytd = o("revenue", 300, date(2025, 6, 30))
    prior_ytd = o("gross_profit", 100, date(2025, 3, 31))
    sq = derive_standalone_quarter(ytd, prior_ytd)
    assert sq.quality == DataQuality.CALCULATION_INVALID
    assert sq.comparable is False


def test_standalone_quarter_wrong_period_type():
    ytd = Observation(
        "ABC", "revenue", 300, "USD", date(2025, 6, 30),
        "ANNUAL", DataQuality.REPORTED, (_prov(),),
    )
    prior_ytd = o("revenue", 100, date(2025, 3, 31))
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
