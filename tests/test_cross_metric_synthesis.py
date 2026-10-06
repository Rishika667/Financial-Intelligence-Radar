import pytest
from financial_radar.synthesis import synthesize_company
from financial_radar.store import connect, save_observations
from financial_radar.models import Observation, DataQuality
from datetime import date

def test_cross_metric_synthesis_patterns():
    c = connect(':memory:')
    c.execute("CREATE TABLE IF NOT EXISTS signals(company TEXT, signal_id TEXT, severity TEXT, confidence TEXT, explanation TEXT, evidence TEXT, suppressed INTEGER, suppression_reason TEXT, UNIQUE(company, signal_id))")
    c.execute("CREATE TABLE IF NOT EXISTS events(company TEXT, event_type TEXT, description TEXT, url TEXT, filed TEXT, form TEXT, UNIQUE(url, company))")
    c.execute("CREATE TABLE IF NOT EXISTS observations(company TEXT, metric TEXT, value REAL, unit TEXT, period_end TEXT, period_type TEXT, quality TEXT, comparable INTEGER, fiscal_year INTEGER, fiscal_period TEXT)")

    def _setup_obs(rev_curr, rev_prev, ar_curr, ar_prev, ocf_curr, ocf_prev, om_curr=None, om_prev=None, fcf_curr=None, fcf_prev=None):
        obs = []
        if rev_curr is not None: obs.append(Observation("AAPL", "revenue", rev_curr, "USD", date(2024,12,31), "QUARTER", DataQuality.REPORTED, tuple(), comparable=True, fiscal_year=2025, fiscal_period="Q1"))
        if rev_prev is not None: obs.append(Observation("AAPL", "revenue", rev_prev, "USD", date(2023,12,31), "QUARTER", DataQuality.REPORTED, tuple(), comparable=True, fiscal_year=2024, fiscal_period="Q1"))
        
        if ar_curr is not None: obs.append(Observation("AAPL", "receivables_revenue_ratio", ar_curr, "pure", date(2024,12,31), "QUARTER", DataQuality.DERIVED, tuple(), comparable=True, fiscal_year=2025, fiscal_period="Q1"))
        if ar_prev is not None: obs.append(Observation("AAPL", "receivables_revenue_ratio", ar_prev, "pure", date(2023,12,31), "QUARTER", DataQuality.DERIVED, tuple(), comparable=True, fiscal_year=2024, fiscal_period="Q1"))
        
        if ocf_curr is not None: obs.append(Observation("AAPL", "operating_cash_flow", ocf_curr, "USD", date(2024,12,31), "QUARTER", DataQuality.REPORTED, tuple(), comparable=True, fiscal_year=2025, fiscal_period="Q1"))
        if ocf_prev is not None: obs.append(Observation("AAPL", "operating_cash_flow", ocf_prev, "USD", date(2023,12,31), "QUARTER", DataQuality.REPORTED, tuple(), comparable=True, fiscal_year=2024, fiscal_period="Q1"))

        if om_curr is not None: obs.append(Observation("AAPL", "operating_margin", om_curr, "pure", date(2024,12,31), "QUARTER", DataQuality.DERIVED, tuple(), comparable=True, fiscal_year=2025, fiscal_period="Q1"))
        if om_prev is not None: obs.append(Observation("AAPL", "operating_margin", om_prev, "pure", date(2023,12,31), "QUARTER", DataQuality.DERIVED, tuple(), comparable=True, fiscal_year=2024, fiscal_period="Q1"))

        if fcf_curr is not None: obs.append(Observation("AAPL", "free_cash_flow", fcf_curr, "USD", date(2024,12,31), "QUARTER", DataQuality.DERIVED, tuple(), comparable=True, fiscal_year=2025, fiscal_period="Q1"))
        if fcf_prev is not None: obs.append(Observation("AAPL", "free_cash_flow", fcf_prev, "USD", date(2023,12,31), "QUARTER", DataQuality.DERIVED, tuple(), comparable=True, fiscal_year=2024, fiscal_period="Q1"))

        c.execute("DELETE FROM observations")
        save_observations(c, obs)
    
    # PATTERN A: Working Capital Deterioration (Rev down, AR up, OCF down)
    _setup_obs(100, 120, 0.5, 0.4, 50, 80)
    synth = synthesize_company("AAPL", c)
    assert any("working-capital deterioration pattern" in s for s in synth["context"]), "Pattern A Positive failed"

    _setup_obs(150, 120, 0.3, 0.4, 100, 80)
    assert not any("working-capital deterioration pattern" in s for s in synthesize_company("AAPL", c)["context"]), "Pattern A Negative failed"

    _setup_obs(100, 120, 0.5, 0.4, 100, 80) # Mixed (OCF up)
    assert not any("working-capital deterioration pattern" in s for s in synthesize_company("AAPL", c)["context"]), "Pattern A Mixed failed"

    _setup_obs(100, 120, 0.5, 0.4, None, None) # Missing OCF
    assert not any("working-capital deterioration pattern" in s for s in synthesize_company("AAPL", c)["context"]), "Pattern A Missing failed"

    # PATTERN B: Multi-dimensional Operating Deterioration (Rev down, OM down, FCF down)
    _setup_obs(100, 120, None, None, None, None, om_curr=0.1, om_prev=0.2, fcf_curr=40, fcf_prev=80)
    assert any("multi-dimensional operating and cash deterioration" in s for s in synthesize_company("AAPL", c)["context"]), "Pattern B Positive failed"

    _setup_obs(150, 120, None, None, None, None, om_curr=0.3, om_prev=0.2, fcf_curr=100, fcf_prev=80)
    assert not any("multi-dimensional operating and cash deterioration" in s for s in synthesize_company("AAPL", c)["context"]), "Pattern B Negative failed"

    _setup_obs(100, 120, None, None, None, None, om_curr=0.3, om_prev=0.2, fcf_curr=40, fcf_prev=80) # Mixed (OM up)
    assert not any("multi-dimensional operating and cash deterioration" in s for s in synthesize_company("AAPL", c)["context"]), "Pattern B Mixed failed"

    _setup_obs(100, 120, None, None, None, None, om_curr=0.1, om_prev=0.2, fcf_curr=None, fcf_prev=None) # Missing FCF
    assert not any("multi-dimensional operating and cash deterioration" in s for s in synthesize_company("AAPL", c)["context"]), "Pattern B Missing failed"
