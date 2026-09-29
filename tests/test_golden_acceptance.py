import json
import sqlite3
from datetime import date
import pytest
import pandas as pd

from financial_radar.store import connect, DDL
from financial_radar.intelligence import generate_intelligence

def test_severity_ordering():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.executescript(DDL)
    
    c.execute("INSERT INTO signals(signal_id, company, severity) VALUES(?, ?, ?)", ("S1", "ABC", "LOW"))
    c.execute("INSERT INTO signals(signal_id, company, severity) VALUES(?, ?, ?)", ("S2", "ABC", "HIGH"))
    c.execute("INSERT INTO signals(signal_id, company, severity) VALUES(?, ?, ?)", ("S3", "ABC", "MODERATE"))
    
    active_tickers = ["ABC"]
    placeholders = ",".join("?" * len(active_tickers))
    q = f"SELECT * FROM signals WHERE company IN ({placeholders}) AND suppressed IS NULL ORDER BY CASE severity WHEN 'HIGH' THEN 1 WHEN 'MODERATE' THEN 2 WHEN 'LOW' THEN 3 ELSE 4 END ASC"
    
    res = c.execute(q, active_tickers).fetchall()
    assert len(res) == 3
    assert res[0]["severity"] == "HIGH"
    assert res[1]["severity"] == "MODERATE"
    assert res[2]["severity"] == "LOW"

def test_latest_period_all_invalid():
    df = pd.DataFrame([
        {"period_end": date(2025, 6, 30), "quality": "NOT_REPORTED"},
        {"period_end": date(2025, 9, 30), "quality": "CALCULATION_INVALID"},
    ])
    valid_qualities = ["REPORTED", "DERIVED", "AMENDED"]
    valid_obs = df[df["quality"].astype(str).apply(lambda x: str(x).split(".")[-1] in valid_qualities)]
    assert valid_obs.empty
    
def test_latest_period_mixed_valid_invalid():
    df = pd.DataFrame([
        {"period_end": date(2025, 3, 31), "quality": "REPORTED"},
        {"period_end": date(2025, 6, 30), "quality": "NOT_REPORTED"},
    ])
    valid_qualities = ["REPORTED", "DERIVED", "AMENDED"]
    valid_obs = df[df["quality"].astype(str).apply(lambda x: str(x).split(".")[-1] in valid_qualities)]
    assert not valid_obs.empty
    assert valid_obs["period_end"].max() == date(2025, 3, 31)


# =========================================================
# 10 DETERMINISTIC SIGNAL INTELLIGENCE TESTS
# =========================================================

def test_intel_receivables_revenue_divergence():
    ev_json = json.dumps([{"value": 150}, {"value": 110}, {"value": 100}, {"value": 100}])
    res = generate_intelligence("RECEIVABLES_REVENUE_DIVERGENCE", "ABC", "Tech", ev_json)
    assert res["title"] == "Working-Capital Divergence"
    assert "Accounts receivable changed by 50.0% while revenue changed by 10.0%" in res["what_changed"]
    assert "Receivables are growing faster" in res["why_it_matters"]
    assert "DSO trend" in res["investigate"]

def test_intel_inventory_sales_divergence():
    ev_json = json.dumps([{"value": 200}, {"value": 150}, {"value": 100}, {"value": 100}])
    res = generate_intelligence("INVENTORY_SALES_DIVERGENCE", "ABC", "Tech", ev_json)
    assert res["title"] == "Inventory Divergence"
    assert "Inventory changed by 100.0% while sales changed by 50.0%" in res["what_changed"]
    assert "Inventory is growing faster than sales" in res["why_it_matters"]

def test_intel_gross_margin_compression():
    ev_json = json.dumps([{"value": 0.40}, {"value": 0.50}])
    res = generate_intelligence("GROSS_MARGIN_COMPRESSION", "ABC", "Tech", ev_json)
    assert res["title"] == "Gross Margin Compression"
    assert "Gross margin changed from 50.0% to 40.0%, a 10.0 percentage-point decline" in res["what_changed"]
    assert "cost of goods sold" in res["why_it_matters"]

def test_intel_operating_margin_deterioration():
    ev_json = json.dumps([{"value": 0.15}, {"value": 0.20}])
    res = generate_intelligence("OPERATING_MARGIN_DETERIORATION", "ABC", "Tech", ev_json)
    assert res["title"] == "Operating Margin Deterioration"
    assert "Operating margin declined from 20.0% to 15.0%, a 5.0 percentage-point decline" in res["what_changed"]
    assert "structurally higher operating expenses" in res["why_it_matters"]

def test_intel_earnings_cash_conversion_deterioration():
    # curr_ocf, curr_ni, prev_ocf, prev_ni
    ev_json = json.dumps([{"value": 50}, {"value": 100}, {"value": 120}, {"value": 100}])
    res = generate_intelligence("EARNINGS_CASH_CONVERSION_DETERIORATION", "ABC", "Tech", ev_json)
    assert res["title"] == "Cash Conversion Decline"
    assert "OCF/net-income declined from 1.20x to 0.50x" in res["what_changed"]
    assert "working capital drag" in res["why_it_matters"]

def test_intel_free_cash_flow_deterioration():
    ev_json = json.dumps([{"value": 50000}, {"value": 150000}])
    res = generate_intelligence("FREE_CASH_FLOW_DETERIORATION", "ABC", "Tech", ev_json)
    assert res["title"] == "Free Cash Flow Deterioration"
    assert "Free cash flow changed from 150,000 to 50,000" in res["what_changed"]
    assert "capital available for debt service" in res["why_it_matters"]

def test_intel_debt_operating_income_deterioration():
    # curr_debt, curr_oi, prev_debt, prev_oi
    ev_json = json.dumps([{"value": 400}, {"value": 100}, {"value": 200}, {"value": 100}])
    res = generate_intelligence("DEBT_OPERATING_INCOME_DETERIORATION", "ABC", "Tech", ev_json)
    assert res["title"] == "Leverage / Interest Burden Increase"
    assert "Debt/operating-income increased from 2.00x to 4.00x" in res["what_changed"]
    assert "debt service burden" in res["why_it_matters"]

def test_intel_liquidity_compression():
    # curr_cash, curr_cl, prev_cash, prev_cl
    ev_json = json.dumps([{"value": 50}, {"value": 100}, {"value": 150}, {"value": 100}])
    res = generate_intelligence("LIQUIDITY_COMPRESSION", "ABC", "Tech", ev_json)
    assert res["title"] == "Liquidity Compression"
    assert "Cash/current-liabilities declined from 1.50x to 0.50x" in res["what_changed"]
    assert "short-term funding pressure" in res["why_it_matters"]

def test_intel_share_count_dilution():
    ev_json = json.dumps([{"value": 110}, {"value": 100}])
    res = generate_intelligence("SHARE_COUNT_DILUTION", "ABC", "Tech", ev_json)
    assert res["title"] == "Share Count Dilution"
    assert "Diluted share count increased by 10.0%" in res["what_changed"]
    assert "dilutes existing shareholder equity" in res["why_it_matters"]

def test_intel_multi_factor_deterioration_cluster():
    # Deterministic cluster explanation fallback
    res = generate_intelligence("MULTI_FACTOR_DETERIORATION_CLUSTER", "ABC", "Tech", "[]")
    assert res["title"] == "Multi-Factor Deterioration Cluster"
    assert "3 or more fundamental deterioration signals fired" in res["what_changed"]
    assert "broad structural deterioration" in res["why_it_matters"]

def test_intel_incomplete_evidence_fallback():
    # Provide an empty payload where quantitative calc should fail gracefully
    ev_json = json.dumps([])
    res = generate_intelligence("OPERATING_MARGIN_DETERIORATION", "ABC", "Tech", ev_json)
    # The default text without quantitative interpolation is returned
    assert res["what_changed"] == "Operating margin declined period-over-period."

def test_no_aggressive_fraud_assertions():
    for sig in [
        "RECEIVABLES_REVENUE_DIVERGENCE", "INVENTORY_SALES_DIVERGENCE", 
        "GROSS_MARGIN_COMPRESSION", "OPERATING_MARGIN_DETERIORATION",
        "EARNINGS_CASH_CONVERSION_DETERIORATION", "FREE_CASH_FLOW_DETERIORATION",
        "DEBT_OPERATING_INCOME_DETERIORATION", "LIQUIDITY_COMPRESSION",
        "SHARE_COUNT_DILUTION", "MULTI_FACTOR_DETERIORATION_CLUSTER"
    ]:
        res = generate_intelligence(sig, "ABC", "Tech", "")
        text = str(res).lower()
        assert "fraud" not in text
        assert "misconduct" not in text
        assert "aggressive revenue" not in text
        assert "lower quality of earnings" not in text
