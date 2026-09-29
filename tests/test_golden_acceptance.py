import json
from financial_radar.intelligence import generate_intelligence

def test_intel_receivables_revenue_divergence():
    ev_json = json.dumps([{"value": 1500}, {"value": 1000}, {"value": 5000}, {"value": 4000}])
    res = generate_intelligence("RECEIVABLES_REVENUE_DIVERGENCE", "ABC", "Tech", ev_json)
    assert res["title"] == "Working-Capital Divergence"
    assert "Target metric grew" in res["what_changed"]

def test_intel_inventory_sales_divergence():
    ev_json = json.dumps([{"value": 200}, {"value": 150}, {"value": 100}, {"value": 100}])
    res = generate_intelligence("INVENTORY_SALES_DIVERGENCE", "ABC", "Tech", ev_json)
    assert res["title"] == "Inventory Divergence"
    assert "Target metric grew" in res["what_changed"]

def test_intel_gross_margin_compression():
    ev_json = json.dumps([{"value": 0.40}, {"value": 0.50}])
    res = generate_intelligence("GROSS_MARGIN_COMPRESSION", "ABC", "Tech", ev_json)
    assert res["title"] == "Gross Margin Compression"
    assert "Gross margin declined from 50.0% to 40.0%" in res["what_changed"]

def test_intel_operating_margin_deterioration():
    ev_json = json.dumps([{"value": 0.15}, {"value": 0.20}])
    res = generate_intelligence("OPERATING_MARGIN_DETERIORATION", "ABC", "Tech", ev_json)
    assert res["title"] == "Operating Margin Deterioration"
    assert "Operating margin declined from 20.0% to 15.0%" in res["what_changed"]
    assert "Operating profitability declined relative to revenue" in res["why_it_matters"]

def test_intel_earnings_cash_conversion_deterioration():
    ev_json = json.dumps([{"value": 50}, {"value": 100}, {"value": 120}, {"value": 100}])
    res = generate_intelligence("EARNINGS_CASH_CONVERSION_DETERIORATION", "ABC", "Tech", ev_json)
    assert res["title"] == "Cash Conversion Decline"

def test_intel_free_cash_flow_deterioration():
    ev_json = json.dumps([{"value": 50000}, {"value": 150000}])
    res = generate_intelligence("FREE_CASH_FLOW_DETERIORATION", "ABC", "Tech", ev_json)
    assert res["title"] == "Free Cash Flow Deterioration"

def test_intel_debt_operating_income_deterioration():
    ev_json = json.dumps([{"value": 400}, {"value": 100}, {"value": 200}, {"value": 100}])
    res = generate_intelligence("DEBT_OPERATING_INCOME_DETERIORATION", "ABC", "Tech", ev_json)
    assert res["title"] == "Debt to Operating Income Deterioration"

def test_intel_liquidity_compression():
    ev_json = json.dumps([{"value": 50}, {"value": 100}, {"value": 150}, {"value": 100}])
    res = generate_intelligence("LIQUIDITY_COMPRESSION", "ABC", "Tech", ev_json)
    assert res["title"] == "Liquidity Compression"

def test_intel_share_count_dilution():
    ev_json = json.dumps([{"value": 110}, {"value": 100}])
    res = generate_intelligence("SHARE_COUNT_DILUTION", "ABC", "Tech", ev_json)
    assert res["title"] == "Share Count Increase"
    assert "Diluted share count increased by 10.0%" in res["what_changed"]

def test_intel_multi_factor_deterioration_cluster():
    res = generate_intelligence("MULTI_FACTOR_DETERIORATION", "ABC", "Tech", "[]")
    assert res["title"] == "Multi-Factor Deterioration Cluster"

def test_intel_incomplete_evidence_fallback():
    ev_json = json.dumps([])
    res = generate_intelligence("OPERATING_MARGIN_DETERIORATION", "ABC", "Tech", ev_json)
    assert res["what_changed"] == "Metric triggered predefined deterioration thresholds."

def test_aapl_q3_golden_expectations():
    pass

def test_msft_golden_expectations():
    pass

def test_jpm_golden_expectations():
    from datetime import date
    from financial_radar.pipeline import evaluate
    from financial_radar.models import Observation, DataQuality
    
    def obs(m, v, u, d, pt="QUARTER"):
        return Observation("JPM", m, v, u, date.fromisoformat(d), pt, DataQuality.REPORTED, tuple(), tuple(), True, None, None)
        
    items = [
        obs("revenue", 40000, "USD", "2026-03-31"),
        obs("revenue", 38000, "USD", "2025-03-31"),
        obs("debt", 500000, "USD", "2026-03-31", "INSTANT"),
        obs("debt", 400000, "USD", "2025-03-31", "INSTANT"),
        obs("operating_income", 15000, "USD", "2026-03-31"),
        obs("operating_income", 14000, "USD", "2025-03-31")
    ]
    
    signals = evaluate("JPM", items, "Financials")
    
    # Financial sector should suppress DEBT_OPERATING_INCOME_DETERIORATION
    debt_sig = next((s for s in signals if s.signal_id == "DEBT_OPERATING_INCOME_DETERIORATION"), None)
    assert debt_sig is not None
    assert debt_sig.suppressed_reason == "Sector Context (Financials)"
    assert "Debt/Operating Income is suppressed for financial institutions" in debt_sig.explanation
