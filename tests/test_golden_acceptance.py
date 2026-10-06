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
        Observation("AAPL", "revenue", 383285000000.0, "USD", date(2023, 9, 30), "QUARTER", DataQuality.REPORTED, tuple(), tuple(), True, None, None),
        Observation("AAPL", "gross_profit", 169148000000.0, "USD", date(2023, 9, 30), "QUARTER", DataQuality.REPORTED, tuple(), tuple(), True, None, None),
        Observation("AAPL", "operating_income", 114301000000.0, "USD", date(2023, 9, 30), "QUARTER", DataQuality.REPORTED, tuple(), tuple(), True, None, None),
        Observation("AAPL", "net_income", 96995000000.0, "USD", date(2023, 9, 30), "QUARTER", DataQuality.REPORTED, tuple(), tuple(), True, None, None),
        Observation("AAPL", "share_count", 15550061000.0, "shares", date(2023, 9, 30), "QUARTER", DataQuality.REPORTED, tuple(), tuple(), True, None, None),
        
        # Prior year (lower margin to show expansion, so NO deterioration signal)
        Observation("AAPL", "revenue", 394328000000.0, "USD", date(2022, 9, 24), "QUARTER", DataQuality.REPORTED, tuple(), tuple(), True, None, None),
        Observation("AAPL", "gross_profit", 170782000000.0, "USD", date(2022, 9, 24), "QUARTER", DataQuality.REPORTED, tuple(), tuple(), True, None, None),
        Observation("AAPL", "operating_income", 119437000000.0, "USD", date(2022, 9, 24), "QUARTER", DataQuality.REPORTED, tuple(), tuple(), True, None, None),
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
        Observation("MSFT", "revenue", 211915000000.0, "USD", date(2023, 6, 30), "QUARTER", DataQuality.REPORTED, prov_data, tuple(), True, None, None),
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
        Observation("JPM", "operating_income", 50000000.0, "USD", date(2023, 12, 31), "QUARTER", DataQuality.REPORTED, tuple(), tuple(), True, None, None),
        Observation("JPM", "debt", 1000000000.0, "USD", date(2023, 12, 31), "INSTANT", DataQuality.REPORTED, tuple(), tuple(), True, None, None),
        Observation("JPM", "operating_income", 60000000.0, "USD", date(2022, 12, 31), "QUARTER", DataQuality.REPORTED, tuple(), tuple(), True, None, None),
        Observation("JPM", "debt", 500000000.0, "USD", date(2022, 12, 31), "INSTANT", DataQuality.REPORTED, tuple(), tuple(), True, None, None),
    ]
    from financial_radar.metrics import derive_analytical_metrics
    obs.extend(derive_analytical_metrics(obs))
    
    signals = evaluate("JPM", obs, "Financials")
    
    # Check that the debt deterioration is suppressed
    debt_sig = next((s for s in signals if s.signal_id == "DEBT_OPERATING_INCOME_DETERIORATION"), None)
    assert debt_sig is not None
    assert debt_sig.severity == "UNKNOWN"
    assert "Sector Context (Financials)" in debt_sig.suppressed_reason

def test_data_readiness_contract():
    c = setup_db()
    # No obs -> NOT_READY
    state, msg = calculate_data_readiness("AAPL", c)
    assert state == ReadinessState.NOT_READY
    
    from financial_radar.normalization import Provenance
    from datetime import datetime
    prov = [Provenance("0001", "url", date(2023,1,1), "10-K", "c", datetime.now(), 1.0, "v1")]
    
    # All NULL / Invalid -> NOT_READY (Wait, it says PARTIAL if any valid exists, NOT_READY if 0 valid)
    obs = [Observation("AAPL", "revenue", None, "USD", date(2023, 9, 30), "QUARTER", DataQuality.NOT_REPORTED, tuple(), tuple(), True, None, None)]
    save_observations(c, obs)
    state, msg = calculate_data_readiness("AAPL", c)
    assert state == ReadinessState.NOT_READY
    
    # Partial obs -> PARTIAL
    obs2 = [Observation("AAPL", "revenue", 1.0, "USD", date(2023, 9, 30), "QUARTER", DataQuality.REPORTED, tuple(prov), tuple(), True, None, None)]
    save_observations(c, obs2)
    state, msg = calculate_data_readiness("AAPL", c)
    assert state == ReadinessState.PARTIAL
    assert "Missing or invalid evidence" in msg
    
    # Core obs -> READY
    obs3 = [
        Observation("AAPL", "net_income", 1.0, "USD", date(2023, 9, 30), "QUARTER", DataQuality.REPORTED, tuple(prov), tuple(), True, None, None),
        Observation("AAPL", "operating_income", 1.0, "USD", date(2023, 9, 30), "QUARTER", DataQuality.REPORTED, tuple(prov), tuple(), True, None, None),
        Observation("AAPL", "operating_cash_flow", 1.0, "USD", date(2023, 9, 30), "QUARTER", DataQuality.REPORTED, tuple(prov), tuple(), True, None, None),
        Observation("AAPL", "cash_and_equivalents", 1.0, "USD", date(2023, 9, 30), "QUARTER", DataQuality.REPORTED, tuple(prov), tuple(), True, None, None),
    ]
    save_observations(c, obs3)
    state, msg = calculate_data_readiness("AAPL", c)
    assert state == ReadinessState.READY
    
    # Real Ingestion Failure -> FAILED
    from financial_radar.models import Signal
    from financial_radar.store import save_signals
    fail_sig = [Signal("INGESTION_FAILED", "AAPL", "HIGH", "HIGH", "Failed", ())]
    save_signals(c, fail_sig)
    state, msg = calculate_data_readiness("AAPL", c)
    assert state == ReadinessState.FAILED

def test_nvda_golden_expectations():
    c = setup_db()
    # NVDA is famous for massive sequential revenue and margin growth.
    obs = [
        Observation("NVDA", "revenue", 22103000000.0, "USD", date(2024, 1, 28), "QUARTER", DataQuality.REPORTED, tuple(), tuple(), True, None, None),
        Observation("NVDA", "gross_profit", 16952000000.0, "USD", date(2024, 1, 28), "QUARTER", DataQuality.REPORTED, tuple(), tuple(), True, None, None),
        
        # Prior period
        Observation("NVDA", "revenue", 6051000000.0, "USD", date(2023, 1, 29), "QUARTER", DataQuality.REPORTED, tuple(), tuple(), True, None, None),
        Observation("NVDA", "gross_profit", 3833000000.0, "USD", date(2023, 1, 29), "QUARTER", DataQuality.REPORTED, tuple(), tuple(), True, None, None),
    ]
    save_observations(c, obs)
    
    signals = evaluate("NVDA", obs, "Information Technology")
    
    # Assert no margin compression, it expanded massively
    sig_ids = [s.signal_id for s in signals if s.actionable]
    assert "GROSS_MARGIN_COMPRESSION" not in sig_ids
