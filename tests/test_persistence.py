import pytest
from datetime import date, datetime
from financial_radar.store import connect, save_observations, load_observations_for_companies
from financial_radar.models import Observation, Provenance, DataQuality

def test_fiscal_metadata_survives_persistence():
    c = connect(':memory:')
    p = Provenance(
        accession="0001", source_url="http", filing_date=date(2025,1,1),
        form="10-K", concept="Rev", retrieval_timestamp=datetime.now(),
        fiscal_year=2024, fiscal_period="FY"
    )
    o = Observation(
        company="AAPL", metric="revenue", value=100.0, unit="USD",
        period_end=date(2024,12,31), period_type="ANNUAL", quality=DataQuality.REPORTED,
        provenance=(p,), fiscal_year=2024, fiscal_period="FY"
    )
    
    save_observations(c, [o])
    
    loaded = load_observations_for_companies(c, ["AAPL"])
    assert len(loaded) == 1
    lo = loaded[0]
    
    assert lo.fiscal_year == 2024
    assert lo.fiscal_period == "FY"
    assert lo.provenance[0].fiscal_year == 2024
    assert lo.provenance[0].fiscal_period == "FY"

def test_observation_identity():
    c = connect(':memory:')
    from datetime import date
    from financial_radar.models import Observation, DataQuality
    
    o1 = Observation(
        company="TEST", metric="revenue", value=100.0, unit="USD",
        period_end=date(2023, 12, 31), period_type="QUARTER",
        quality=DataQuality.REPORTED, provenance=tuple(),
        period_start=date(2023, 10, 1)
    )
    o2 = Observation(
        company="TEST", metric="revenue", value=300.0, unit="USD",
        period_end=date(2023, 12, 31), period_type="QUARTER",
        quality=DataQuality.REPORTED, provenance=tuple(),
        period_start=date(2023, 1, 1) # Same end, different start
    )
    save_observations(c, [o1, o2])
    
    loaded = load_observations_for_companies(c, ["TEST"])
    assert len(loaded) == 2, "Both observations should survive because period_start differs"
    starts = {o.period_start for o in loaded}
    assert date(2023, 10, 1) in starts
    assert date(2023, 1, 1) in starts
