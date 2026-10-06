import pytest
import sqlite3
import sys
sys.path.append("src")
from financial_radar.store import connect
from financial_radar.models import Observation, DataQuality
from datetime import date
import os

def test_legacy_migration():
    if os.path.exists("test_legacy.db"):
        os.remove("test_legacy.db")
        
    c = sqlite3.connect("test_legacy.db")
    c.execute("""
        CREATE TABLE observations(
            company TEXT, metric TEXT, value REAL, unit TEXT, period_end TEXT, period_type TEXT,
            quality TEXT, provenance TEXT, derived_from TEXT, comparable INTEGER,
            PRIMARY KEY(company, metric, period_end, period_type)
        )
    """)
    c.execute("""
        CREATE TABLE peer_context(
            company TEXT, metric TEXT, unit TEXT, period_end TEXT, period_type TEXT,
            peer_group TEXT, peer_group_version TEXT, peers_configured TEXT,
            peers_available TEXT, peers_unavailable TEXT,
            coverage_ratio REAL, company_value REAL, peer_median REAL,
            peer_min REAL, peer_max REAL,
            PRIMARY KEY(company, metric, period_end, period_type)
        )
    """)
    c.execute("INSERT INTO observations VALUES ('AAPL', 'revenue', 100, 'USD', '2023-12-31', 'QUARTER', 'REPORTED', '', '', 1)")
    c.execute("INSERT INTO peer_context VALUES ('AAPL', 'revenue', 'USD', '2023-12-31', 'QUARTER', 'GRP', 'v1', 'MSFT', 'MSFT', '', 1.0, 100, 110, 100, 120)")
    c.commit()
    c.close()
    
    db = connect("test_legacy.db")
    
    db.execute("""
        INSERT INTO observations (
            company, metric, value, unit, period_end, period_type, quality, comparable, period_start, fiscal_year, fiscal_period
        ) VALUES (
            'AAPL', 'revenue', 200, 'USD', '2024-12-31', 'QUARTER', 'REPORTED', 1, '2024-10-01', 2024, 'Q4'
        )
    """)
    db.commit()
    
    res_obs = db.execute("SELECT * FROM observations ORDER BY period_end").fetchall()
    assert len(res_obs) == 2
    assert 'period_start' in dict(res_obs[0])
    
    res_peer = db.execute("SELECT * FROM peer_context").fetchall()
    assert len(res_peer) == 1
    assert 'availability_state' in dict(res_peer[0])
    
    db.close()
    if os.path.exists("test_legacy.db"):
        os.remove("test_legacy.db")
