import pytest
from datetime import date
from financial_radar.models import Observation, DataQuality
from financial_radar.metrics import get_comparison_pair
from financial_radar.signals import _ok

def test_missing_not_zero():
    # If a value is missing, it should not equal zero
    obs = Observation("AAPL", "revenue", None, "USD", date(2023,9,30), "QUARTER", DataQuality.NOT_REPORTED)
    assert obs.value is not 0

def test_currencies_cannot_be_compared():
    # _ok() should return False for different units
    obs1 = Observation("AAPL", "revenue", 100, "USD", date(2023,9,30), "QUARTER", DataQuality.REPORTED)
    obs2 = Observation("AAPL", "revenue", 100, "EUR", date(2022,9,30), "QUARTER", DataQuality.REPORTED)
    assert not _ok(obs1, obs2)
    
def test_period_windows_cannot_be_compared():
    from financial_radar.signals import margin_compression
    obs1 = Observation("AAPL", "revenue", 100, "USD", date(2023,9,30), "QUARTER", DataQuality.REPORTED)
    obs2 = Observation("AAPL", "revenue", 100, "USD", date(2022,9,30), "ANNUAL", DataQuality.REPORTED)
    sig = margin_compression(obs1, obs2)
    assert sig.suppressed_reason == "data quality/comparability"

def test_yoy_comparison_engine():
    obs = [
        Observation("AAPL", "revenue", 100, "USD", date(2023,9,30), "QUARTER", DataQuality.REPORTED),
        Observation("AAPL", "revenue", 90, "USD", date(2023,6,30), "QUARTER", DataQuality.REPORTED), # Sequential
        Observation("AAPL", "revenue", 80, "USD", date(2022,9,30), "QUARTER", DataQuality.REPORTED), # YoY
    ]
    curr, prior = get_comparison_pair(obs, "revenue", "QUARTER", "yoy")
    assert prior.period_end == date(2022,9,30)
    
    curr_seq, prior_seq = get_comparison_pair(obs, "revenue", "QUARTER", "sequential")
    assert prior_seq.period_end == date(2023,6,30)
