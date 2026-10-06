import pytest
from datetime import date
from financial_radar.models import Observation, DataQuality
from financial_radar.metrics import derive_analytical_metrics

def test_mixed_currency_rejected():
    gp = Observation("TEST", "gross_profit", 90.0, "EUR", date(2023,12,31), "QUARTER", DataQuality.REPORTED)
    rev = Observation("TEST", "revenue", 100.0, "USD", date(2023,12,31), "QUARTER", DataQuality.REPORTED)
    derived = derive_analytical_metrics([gp, rev])
    assert len(derived) == 0, "Should not compute gross_margin with mixed currency"

    gp2 = Observation("TEST", "gross_profit", 90.0, "USD", date(2023,12,31), "QUARTER", DataQuality.REPORTED)
    rev2 = Observation("TEST", "revenue", 100.0, "USD", date(2023,12,31), "QUARTER", DataQuality.REPORTED)
    derived2 = derive_analytical_metrics([gp2, rev2])
    assert len(derived2) == 1
    assert derived2[0].metric == "gross_margin"

