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
    
    # Insert signals with different severities
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

def test_latest_period_ignores_placeholders():
    df = pd.DataFrame([
        {"period_end": date(2025, 3, 31), "quality": "REPORTED"},
        {"period_end": date(2025, 6, 30), "quality": "NOT_REPORTED"},
        {"period_end": date(2025, 9, 30), "quality": "CALCULATION_INVALID"},
    ])
    
    valid_qualities = ["REPORTED", "DERIVED", "AMENDED"]
    valid_obs = df[df["quality"].astype(str).apply(lambda x: x.split(".")[-1] in valid_qualities)]
    
    latest_period = valid_obs["period_end"].max() if not valid_obs.empty else df["period_end"].max()
    assert latest_period == date(2025, 3, 31)

def test_intelligence_mapping_leverage():
    res = generate_intelligence("DEBT_OPERATING_INCOME_DETERIORATION", "ABC", "Tech", "")
    assert "Leverage" in res["title"]
    assert "Debt increased" in res["what_changed"]
    assert "Increases financial risk" in res["why_it_matters"]
    assert "refinancing risk" in res["investigate"][0].lower()

def test_evidence_first_intelligence_deterministic():
    ev_json = json.dumps([
        {"value": 131},
        {"value": 108},
        {"value": 100},
        {"value": 100}
    ])
    res = generate_intelligence("RECEIVABLES_REVENUE_DIVERGENCE", "ABC", "Tech", ev_json)
    assert res["title"] == "Working-Capital Divergence"
    assert "Accounts receivable changed by 31.0%" in res["what_changed"]
    assert "revenue changed by 8.0%" in res["what_changed"]
    assert "Receivables are growing faster" in res["why_it_matters"]

def test_no_aggressive_fraud_assertions():
    for sig in [
        "RECEIVABLES_REVENUE_DIVERGENCE", "INVENTORY_SALES_DIVERGENCE", 
        "GROSS_MARGIN_COMPRESSION", "OPERATING_DELEVERAGE",
        "EARNINGS_CASH_CONVERSION_DETERIORATION", "FREE_CASH_FLOW_DETERIORATION",
        "DEBT_OPERATING_INCOME_DETERIORATION", "LIQUIDITY_COMPRESSION",
        "SHARE_COUNT_DILUTION", "MULTI_FACTOR_DETERIORATION_CLUSTER"
    ]:
        res = generate_intelligence(sig, "ABC", "Tech", "")
        text = str(res).lower()
        assert "fraud" not in text
        assert "misconduct" not in text
        assert "aggressive revenue" not in text
