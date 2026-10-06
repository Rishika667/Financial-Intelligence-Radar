import pytest
from datetime import date
from financial_radar.pipeline import evaluate
from financial_radar.models import Observation, DataQuality

def test_sector_safe_signaling():
    # Setup Observations (trigger GM compression and OM deterioration)
    obs = [
        Observation("C", "gross_margin", 0.40, "pure", date(2025,1,1), "QUARTER", DataQuality.REPORTED, tuple(), comparable=True, fiscal_year=2025, fiscal_period="Q1"),
        Observation("C", "gross_margin", 0.50, "pure", date(2024,1,1), "QUARTER", DataQuality.REPORTED, tuple(), comparable=True, fiscal_year=2024, fiscal_period="Q1"),
        Observation("C", "operating_margin", 0.10, "pure", date(2025,1,1), "QUARTER", DataQuality.REPORTED, tuple(), comparable=True, fiscal_year=2025, fiscal_period="Q1"),
        Observation("C", "operating_margin", 0.20, "pure", date(2024,1,1), "QUARTER", DataQuality.REPORTED, tuple(), comparable=True, fiscal_year=2024, fiscal_period="Q1")
    ]
    
    # 1. Corporate company receives corporate signals
    corp_sigs = evaluate("C", obs, sector="Technology")
    assert any(s.signal_id == "GROSS_MARGIN_COMPRESSION" and s.severity == "HIGH" for s in corp_sigs)
    assert any(s.signal_id == "OPERATING_MARGIN_DETERIORATION" and s.severity == "HIGH" for s in corp_sigs)
    
    # 2. Financial company does not receive corporate signals
    fin_sigs = evaluate("C", obs, sector="Financials")
    gm_sig = next((s for s in fin_sigs if s.signal_id == "GROSS_MARGIN_COMPRESSION"), None)
    assert gm_sig is not None
    assert gm_sig.severity == "UNKNOWN"
    assert gm_sig.suppressed_reason == "Sector Context (Financials)"
    
    # 3. Valid financial signals are NOT suppressed (e.g. operating margin)
    om_sig = next((s for s in fin_sigs if s.signal_id == "OPERATING_MARGIN_DETERIORATION"), None)
    assert om_sig is not None
    assert om_sig.severity == "HIGH"
    assert om_sig.suppressed_reason is None

    # 4. Unknown sector does not silently become Financials
    unk_sigs = evaluate("C", obs, sector="Unknown")
    assert any(s.signal_id == "GROSS_MARGIN_COMPRESSION" and s.severity == "HIGH" for s in unk_sigs)
