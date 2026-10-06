import pytest
import json
from datetime import date
from financial_radar.models import Observation, DataQuality
from financial_radar.store import connect, save_observations, save_portfolio, save_signals
from financial_radar.pipeline import evaluate

def test_attention_queue_signals_and_portfolio():
    c = connect(':memory:')
    
    save_portfolio(c, [{"ticker": "AAPL", "weight": 0.05, "exposure": 50000}])
    
    # 1. Missing data -> no signals
    sig = evaluate("AAPL", [])
    assert len(sig) == 0, "Should not fabricate signals on empty data"

    # 2. Generation of HIGH and MEDIUM signals
    obs = [
        Observation("AAPL", "gross_margin", 0.40, "pure", date(2024,12,31), "QUARTER", DataQuality.DERIVED, tuple(), comparable=True, fiscal_year=2025, fiscal_period="Q1"),
        Observation("AAPL", "gross_margin", 0.50, "pure", date(2023,12,31), "QUARTER", DataQuality.DERIVED, tuple(), comparable=True, fiscal_year=2024, fiscal_period="Q1"),
        # Drops 10% -> HIGH
        Observation("AAPL", "operating_margin", 0.20, "pure", date(2024,12,31), "QUARTER", DataQuality.DERIVED, tuple(), comparable=True, fiscal_year=2025, fiscal_period="Q1"),
        Observation("AAPL", "operating_margin", 0.24, "pure", date(2023,12,31), "QUARTER", DataQuality.DERIVED, tuple(), comparable=True, fiscal_year=2024, fiscal_period="Q1")
        # Drops 4% -> MEDIUM
    ]
    sigs = evaluate("AAPL", obs)
    assert any(s.severity == "HIGH" and s.signal_id == "GROSS_MARGIN_COMPRESSION" for s in sigs)
    assert any(s.severity == "MEDIUM" and s.signal_id == "OPERATING_MARGIN_DETERIORATION" for s in sigs)

    # 3. Multiple simultaneous signals (Cluster)
    obs.extend([
        Observation("AAPL", "cash_conversion", 0.5, "pure", date(2024,12,31), "QUARTER", DataQuality.DERIVED, tuple(), comparable=True, fiscal_year=2025, fiscal_period="Q1"),
        Observation("AAPL", "cash_conversion", 1.0, "pure", date(2023,12,31), "QUARTER", DataQuality.DERIVED, tuple(), comparable=True, fiscal_year=2024, fiscal_period="Q1")
    ])
    sigs = evaluate("AAPL", obs)
    assert any(s.signal_id == "MULTI_FACTOR_DETERIORATION_CLUSTER" for s in sigs), "Cluster signal missing"
    
    # 4. Suppression (Sector Awareness)
    sigs_fin = evaluate("JPM", obs, sector="Financials")
    suppressed = [s for s in sigs_fin if s.suppressed_reason]
    assert any(s.signal_id == "GROSS_MARGIN_COMPRESSION" and s.severity == "UNKNOWN" for s in suppressed), "Did not suppress corporate metrics for Financials"

    # 5. Non-held vs held
    save_signals(c, sigs)
    from financial_radar.store import rows
    
    q_held = rows(c, "SELECT s.*, p.weight FROM signals s LEFT JOIN portfolio p ON s.company = p.ticker WHERE s.company = 'AAPL' AND s.signal_id = 'GROSS_MARGIN_COMPRESSION'")
    assert len(q_held) == 1
    assert q_held[0]["weight"] == 0.05
