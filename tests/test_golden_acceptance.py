import pytest
import sqlite3
import json
from datetime import date

from financial_radar.models import DataQuality, Observation, ReadinessState
from financial_radar.store import DDL, save_observations, save_peer_context
from financial_radar.pipeline import evaluate, calculate_data_readiness
from financial_radar.intelligence import generate_intelligence

def setup_db():
    c = sqlite3.connect(":memory:", check_same_thread=False)
    c.row_factory = sqlite3.Row
    c.executescript(DDL)
    return c

def test_aapl_golden_expectations():
    c = setup_db()
    # Mock some realistic AAPL observations
    obs = [
        Observation("AAPL", "revenue", 383285000000.0, "USD", date(2023, 9, 30), "ANNUAL", DataQuality.REPORTED, tuple(), tuple(), True, None, None),
        Observation("AAPL", "gross_profit", 169148000000.0, "USD", date(2023, 9, 30), "ANNUAL", DataQuality.REPORTED, tuple(), tuple(), True, None, None),
        Observation("AAPL", "operating_income", 114301000000.0, "USD", date(2023, 9, 30), "ANNUAL", DataQuality.REPORTED, tuple(), tuple(), True, None, None),
        Observation("AAPL", "net_income", 96995000000.0, "USD", date(2023, 9, 30), "ANNUAL", DataQuality.REPORTED, tuple(), tuple(), True, None, None),
        Observation("AAPL", "share_count", 15550061000.0, "shares", date(2023, 9, 30), "ANNUAL", DataQuality.REPORTED, tuple(), tuple(), True, None, None),
        
        # Prior year (lower margin to show expansion, so NO deterioration signal)
        Observation("AAPL", "revenue", 394328000000.0, "USD", date(2022, 9, 24), "ANNUAL", DataQuality.REPORTED, tuple(), tuple(), True, None, None),
        Observation("AAPL", "gross_profit", 170782000000.0, "USD", date(2022, 9, 24), "ANNUAL", DataQuality.REPORTED, tuple(), tuple(), True, None, None),
        Observation("AAPL", "operating_income", 119437000000.0, "USD", date(2022, 9, 24), "ANNUAL", DataQuality.REPORTED, tuple(), tuple(), True, None, None),
    ]
    # Gross margin 2023: 169.1 / 383.2 = 44.1%
    # Gross margin 2022: 170.7 / 394.3 = 43.2%
    # Margin expanded!
    save_observations(c, obs)
    
    signals = evaluate("AAPL", obs, "Information Technology")
    
    # Assert NO deterioration signals because margin expanded
    sig_ids = [s.signal_id for s in signals]
    assert "GROSS_MARGIN_DETERIORATION" not in sig_ids
    
def test_msft_golden_expectations():
    c = setup_db()
    from financial_radar.normalization import Provenance; from datetime import datetime; prov_data = [Provenance("0001", "https://sec.gov/msft", date(2023,6,30), "10-K", "Revenues", datetime.now(), 211915000000.0, "v1", date(2022,7,1))]
    obs = [
        Observation("MSFT", "revenue", 211915000000.0, "USD", date(2023, 6, 30), "ANNUAL", DataQuality.REPORTED, prov_data, tuple(), True, None, None),
    ]
    save_observations(c, obs)
    
    # Check that provenance is saved correctly
    res = c.execute("SELECT provenance FROM observations WHERE company='MSFT' AND metric='revenue'").fetchone()
    prov_out = json.loads(res["provenance"])
    assert prov_out[0]["source_url"] == "https://sec.gov/msft"
    
def test_jpm_golden_expectations():
    c = setup_db()
    # JPM has debt, but being a financial, we suppress DEBT metrics
    obs = [
        Observation("JPM", "operating_income", 50000000.0, "USD", date(2023, 12, 31), "ANNUAL", DataQuality.REPORTED, tuple(), tuple(), True, None, None),
        Observation("JPM", "debt", 1000000000.0, "USD", date(2023, 12, 31), "ANNUAL", DataQuality.REPORTED, tuple(), tuple(), True, None, None),
        Observation("JPM", "operating_income", 60000000.0, "USD", date(2022, 12, 31), "ANNUAL", DataQuality.REPORTED, tuple(), tuple(), True, None, None),
        Observation("JPM", "debt", 500000000.0, "USD", date(2022, 12, 31), "ANNUAL", DataQuality.REPORTED, tuple(), tuple(), True, None, None),
    ]
    signals = evaluate("JPM", obs, "Financials")
    
    # Check that the debt deterioration is suppressed
    debt_sig = next((s for s in signals if s.signal_id == "DEBT_OPERATING_INCOME_DETERIORATION"), None)
    assert debt_sig is not None
    assert debt_sig.actionable is False
    assert "Sector Context (Financials)" in debt_sig.suppressed_reason

def test_data_readiness_contract():
    c = setup_db()
    # No obs -> NOT_READY
    state, msg = calculate_data_readiness("AAPL", c)
    assert state == ReadinessState.NOT_READY
    
    # Partial obs -> PARTIAL
    obs = [Observation("AAPL", "revenue", 1.0, "USD", date(2023, 9, 30), "ANNUAL", DataQuality.REPORTED, tuple(), tuple(), True, None, None)]
    save_observations(c, obs)
    state, msg = calculate_data_readiness("AAPL", c)
    assert state == ReadinessState.PARTIAL
    assert "Missing" in msg
    
    # Core obs -> READY
    obs2 = [
        Observation("AAPL", "net_income", 1.0, "USD", date(2023, 9, 30), "ANNUAL", DataQuality.REPORTED, tuple(), tuple(), True, None, None),
        Observation("AAPL", "operating_income", 1.0, "USD", date(2023, 9, 30), "ANNUAL", DataQuality.REPORTED, tuple(), tuple(), True, None, None),
        Observation("AAPL", "operating_cash_flow", 1.0, "USD", date(2023, 9, 30), "ANNUAL", DataQuality.REPORTED, tuple(), tuple(), True, None, None),
        Observation("AAPL", "cash_and_equivalents", 1.0, "USD", date(2023, 9, 30), "ANNUAL", DataQuality.REPORTED, tuple(), tuple(), True, None, None),
    ]
    save_observations(c, obs2)
    state, msg = calculate_data_readiness("AAPL", c)
    assert state == ReadinessState.READY
