import pytest
from datetime import date
from financial_radar.metrics import derive_analytical_metrics, get_comparison_pair
from financial_radar.models import Observation, DataQuality, Provenance

def test_historical_growth_calculation_and_metadata_preservation():
    p = Provenance("0001", "url", date(2025,1,1), "10-K", "c", None, None, "v1", None)
    
    obs = [
        Observation("A", "revenue", 100, "USD", date(2024,3,31), "QUARTER", DataQuality.REPORTED, (p,), comparable=True, fiscal_year=2025, fiscal_period="Q1"),
        Observation("A", "revenue", 120, "USD", date(2025,3,31), "QUARTER", DataQuality.REPORTED, (p,), comparable=True, fiscal_year=2026, fiscal_period="Q1"),
        Observation("A", "revenue", 150, "USD", date(2024,6,30), "QUARTER", DataQuality.REPORTED, (p,), comparable=True, fiscal_year=2025, fiscal_period="Q2"),
        Observation("A", "revenue", 165, "USD", date(2025,6,30), "QUARTER", DataQuality.REPORTED, (p,), comparable=True, fiscal_year=2026, fiscal_period="Q2"),
        Observation("A", "gross_profit", 50, "USD", date(2025,6,30), "QUARTER", DataQuality.REPORTED, (p,), comparable=True, fiscal_year=2026, fiscal_period="Q2"),
    ]
    
    # Run the derivation
    derived = derive_analytical_metrics(obs)
    
    # Defect 3: Preserve Fiscal Metadata on Derived Metrics
    gm = [o for o in derived if o.metric == "gross_margin"]
    assert len(gm) == 1
    assert getattr(gm[0], "fiscal_year", None) == 2026
    assert getattr(gm[0], "fiscal_period", None) == "Q2"
    
    # Defect 2 and 5: Growth metrics for historically independent periods
    growth = [o for o in derived if o.metric == "revenue_growth_yoy"]
    assert len(growth) == 2
    
    # Q1 FY2026 growth = (120 - 100) / 100 = 20%
    q1_growth = [o for o in growth if getattr(o, "fiscal_period", None) == "Q1"][0]
    assert abs(q1_growth.value - 0.20) < 0.001
    assert getattr(q1_growth, "fiscal_year", None) == 2026
    
    # Q2 FY2026 growth = (165 - 150) / 150 = 10%
    q2_growth = [o for o in growth if getattr(o, "fiscal_period", None) == "Q2"][0]
    assert abs(q2_growth.value - 0.10) < 0.001
    assert getattr(q2_growth, "fiscal_year", None) == 2026
