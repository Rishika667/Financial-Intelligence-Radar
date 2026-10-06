import pytest
from datetime import date
from financial_radar.pipeline import deduplicate_observations
from financial_radar.models import Observation, DataQuality, Provenance

def _obs(q, val=100):
    p = Provenance("0001", "url", date(2025,1,1), "10-K", "c", None, val, "v1", None)
    return Observation("A", "revenue", val, "USD", date(2024,12,31), "QUARTER", q, (p,))

def test_quality_precedence_matrix():
    # AMENDED vs RESTATED
    o1, o2 = _obs(DataQuality.RESTATED, 100), _obs(DataQuality.AMENDED, 120)
    assert deduplicate_observations([o1, o2])[0].quality == DataQuality.AMENDED
    assert deduplicate_observations([o2, o1])[0].quality == DataQuality.AMENDED

    # AMENDED vs REPORTED
    o1, o2 = _obs(DataQuality.REPORTED, 100), _obs(DataQuality.AMENDED, 120)
    assert deduplicate_observations([o1, o2])[0].quality == DataQuality.AMENDED
    assert deduplicate_observations([o2, o1])[0].quality == DataQuality.AMENDED
    
    # RESTATED vs REPORTED
    o1, o2 = _obs(DataQuality.REPORTED, 100), _obs(DataQuality.RESTATED, 130)
    assert deduplicate_observations([o1, o2])[0].quality == DataQuality.RESTATED
    assert deduplicate_observations([o2, o1])[0].quality == DataQuality.RESTATED
    
    # REPORTED vs DERIVED
    o1, o2 = _obs(DataQuality.DERIVED, 100), _obs(DataQuality.REPORTED, 140)
    assert deduplicate_observations([o1, o2])[0].quality == DataQuality.REPORTED
    assert deduplicate_observations([o2, o1])[0].quality == DataQuality.REPORTED
    
    # REPORTED vs NOT_REPORTED
    o1, o2 = _obs(DataQuality.NOT_REPORTED, 100), _obs(DataQuality.REPORTED, 150)
    assert deduplicate_observations([o1, o2])[0].quality == DataQuality.REPORTED
    assert deduplicate_observations([o2, o1])[0].quality == DataQuality.REPORTED
    
    # DERIVED vs NOT_REPORTED
    o1, o2 = _obs(DataQuality.NOT_REPORTED, 100), _obs(DataQuality.DERIVED, 160)
    assert deduplicate_observations([o1, o2])[0].quality == DataQuality.DERIVED
    assert deduplicate_observations([o2, o1])[0].quality == DataQuality.DERIVED
