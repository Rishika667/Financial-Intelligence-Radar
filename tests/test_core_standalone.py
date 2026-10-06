import pytest
from datetime import date
from financial_radar.core import derive_standalone_quarter
from financial_radar.models import Observation, DataQuality, Provenance

def test_standalone_quarter_fiscal_semantics():
    p = Provenance("0001", "url", date(2025,1,1), "10-K", "c", None, None, "v1", None)
    
    # Matching fiscal years, but day diff is > 100 (e.g., 105 days due to leap year + weekends)
    ytd = Observation("A", "revenue", 1000, "USD", date(2024,6,30), "YTD_6M", DataQuality.REPORTED, (p,), fiscal_year=2024)
    q1 = Observation("A", "revenue", 400, "USD", date(2024,3,1), "QUARTER", DataQuality.REPORTED, (p,), fiscal_year=2024)
    
    q2 = derive_standalone_quarter(ytd, q1)
    assert q2.value is None
    assert q2.quality == DataQuality.CALCULATION_INVALID
            
    # Missing fiscal year -> falls back to date, should fail if days > 105
    ytd2 = Observation("B", "revenue", 1000, "USD", date(2024,6,30), "YTD_6M", DataQuality.REPORTED, (p,))
    q1_2 = Observation("B", "revenue", 400, "USD", date(2024,3,1), "QUARTER", DataQuality.REPORTED, (p,))
    
    q2_invalid = derive_standalone_quarter(ytd2, q1_2)
    assert q2_invalid.quality == DataQuality.CALCULATION_INVALID
