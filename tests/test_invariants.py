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
    from financial_radar.metrics import get_comparison_pair
    obs1 = Observation("AAPL", "revenue", 100, "USD", date(2023,9,30), "QUARTER", DataQuality.REPORTED)
    obs2 = Observation("AAPL", "revenue", 100, "EUR", date(2022,9,30), "QUARTER", DataQuality.REPORTED)
    c, p = get_comparison_pair([obs1, obs2], "revenue", "QUARTER", "yoy")
    assert p is None
    
def test_period_windows_cannot_be_compared():
    from financial_radar.metrics import get_comparison_pair
    obs1 = Observation("AAPL", "revenue", 100, "USD", date(2023,9,30), "QUARTER", DataQuality.REPORTED)
    obs2 = Observation("AAPL", "revenue", 100, "USD", date(2022,9,30), "ANNUAL", DataQuality.REPORTED)
    c, p = get_comparison_pair([obs1, obs2], "revenue", "QUARTER", "yoy")
    assert p is None

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

def test_reported_derived_precedence():
    from financial_radar.models import Observation, DataQuality
    from datetime import date
    o = lambda c, m, v, u, pe, pt, q: Observation(c, m, v, u, pe, pt, q)
    
    # Simulate list of observations
    obs = [
        # DERIVED gets added last
        o("AAPL", "revenue", 110, "USD", date(2023, 9, 30), "QUARTER", DataQuality.DERIVED),
        # AMENDED is best
        o("AAPL", "revenue", 105, "USD", date(2023, 9, 30), "QUARTER", DataQuality.AMENDED),
        # REPORTED is middle
        o("AAPL", "revenue", 100, "USD", date(2023, 9, 30), "QUARTER", DataQuality.REPORTED)
    ]
    
    # We apply the dedup logic from ingest_company
    quality_rank = {
        DataQuality.AMENDED: 4,
        DataQuality.RESTATED: 4,
        DataQuality.REPORTED: 3,
        DataQuality.DERIVED: 2,
        DataQuality.NOT_REPORTED: 1
    }
    
    dedup = {}
    for ob in obs:
        key = (ob.company, ob.metric, ob.period_end, ob.period_type, ob.unit)
        if key not in dedup:
            dedup[key] = ob
        else:
            existing = dedup[key]
            eq = quality_rank.get(existing.quality, 0)
            nq = quality_rank.get(ob.quality, 0)
            if nq > eq:
                dedup[key] = ob
                
    result = list(dedup.values())
    assert len(result) == 1
    assert result[0].quality == DataQuality.AMENDED
    assert result[0].value == 105
