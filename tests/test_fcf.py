import pytest
from datetime import date
from financial_radar.metrics import derive_analytical_metrics
from financial_radar.models import Observation, DataQuality, Provenance

def test_free_cash_flow_capex_sign_handling():
    p = Provenance("0001", "url", date(2025,1,1), "10-K", "c", None, None, "v1", None)
    # Positive capex representation
    ocf1 = Observation("A", "operating_cash_flow", 1000, "USD", date(2025,1,1), "QUARTER", DataQuality.REPORTED, (p,))
    cap1 = Observation("A", "capital_expenditures", 200, "USD", date(2025,1,1), "QUARTER", DataQuality.REPORTED, (p,))
    
    # Negative capex representation
    ocf2 = Observation("B", "operating_cash_flow", 1000, "USD", date(2025,1,1), "QUARTER", DataQuality.REPORTED, (p,))
    cap2 = Observation("B", "capital_expenditures", -200, "USD", date(2025,1,1), "QUARTER", DataQuality.REPORTED, (p,))
    
    der1 = derive_analytical_metrics([ocf1, cap1])
    fcf1 = [o for o in der1 if o.metric == 'free_cash_flow'][0]
    
    der2 = derive_analytical_metrics([ocf2, cap2])
    fcf2 = [o for o in der2 if o.metric == 'free_cash_flow'][0]
    
    assert fcf1.value == 800
    assert fcf2.value == 800
