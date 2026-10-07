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

def test_legacy_migration_partial_and_coexist():
    import os
    import sqlite3
    from financial_radar.store import connect
    if os.path.exists("test_legacy2.db"):
        os.remove("test_legacy2.db")
        
    c = sqlite3.connect("test_legacy2.db")
    c.execute("CREATE TABLE observations(company TEXT, metric TEXT, value REAL, unit TEXT, period_end TEXT, period_type TEXT, quality TEXT, provenance TEXT, derived_from TEXT, comparable INTEGER, PRIMARY KEY(company, metric, period_end, period_type))")
    c.execute("INSERT INTO observations VALUES ('AAPL', 'revenue', 100, 'USD', '2023-12-31', 'QUARTER', 'REPORTED', '', '', 1)")
    c.commit()
    c.close()
    
    db = connect("test_legacy2.db")
    
    # Insert another observation with same period_end/type but DIFFERENT period_start (now valid)
    db.execute("INSERT INTO observations (company, metric, value, unit, period_end, period_type, quality, comparable, period_start, fiscal_year, fiscal_period) VALUES ('AAPL', 'revenue', 150, 'USD', '2023-12-31', 'QUARTER', 'REPORTED', 1, '2023-10-01', 2023, 'Q4')")
    db.commit()
    
    res = db.execute("SELECT * FROM observations").fetchall()
    assert len(res) == 2, "Both observations must coexist with different period_start"
    
    # Re-running connect should be idempotent
    db.close()
    db2 = connect("test_legacy2.db")
    res2 = db2.execute("SELECT * FROM observations").fetchall()
    assert len(res2) == 2
    db2.close()
    
    if os.path.exists("test_legacy2.db"):
        os.remove("test_legacy2.db")

def test_legacy_migration_partial_peer_context():
    import os
    import sqlite3
    from financial_radar.store import connect, save_peer_context
    if os.path.exists("test_legacy_peer.db"):
        os.remove("test_legacy_peer.db")
        
    c = sqlite3.connect("test_legacy_peer.db")
    # Genuinely legacy peer_context (missing 5 columns)
    c.execute("CREATE TABLE peer_context(company TEXT, group_id TEXT, metric TEXT, company_value REAL, peer_median REAL, peer_min REAL, peer_max REAL, n_peers INTEGER, version TEXT, unavailable_peers TEXT, PRIMARY KEY(company, metric))")
    c.execute("INSERT INTO peer_context VALUES ('AAPL', 'G1', 'revenue', 100, 110, 100, 120, 5, 'v1', '[]')")
    c.commit()
    c.close()
    
    # Reopen with production connect (runs migration)
    db = connect("test_legacy_peer.db")
    
    # Save using CURRENT production API
    save_peer_context(db, 'AAPL', {
        'group_id': 'G1',
        'contexts': [{
            'metric': 'revenue',
            'company_value': 105,
            'peer_median': 115,
            'peer_range': (105, 125),
            'n_peers': 6,
            'peer_group_version': 'v1',
            'unavailable_peers': ['X'],
            'position': 'BOTTOM_QUARTILE',
            'coverage_count': 6,
            'total_peer_count': 7,
            'coverage_ratio': 0.85,
            'availability_state': 'PARTIAL'
        }]
    })
    
    # Reload the row
    res = db.execute("SELECT * FROM peer_context WHERE company='AAPL' AND metric='revenue'").fetchall()
    
    assert len(res) == 1
    row = dict(res[0])
    
    # Verify all new values survive correctly
    assert row["position"] == "BOTTOM_QUARTILE"
    assert row["coverage_count"] == 6
    assert row["coverage_ratio"] == 0.85
    assert row["availability_state"] == "PARTIAL"
    assert row["company_value"] == 105
    
    db.close()
    
    # Reopen a second time to verify idempotence
    db2 = connect("test_legacy_peer.db")
    res2 = db2.execute("SELECT * FROM peer_context WHERE company='AAPL' AND metric='revenue'").fetchall()
    assert len(res2) == 1
    db2.close()
    
    if os.path.exists("test_legacy_peer.db"):
        os.remove("test_legacy_peer.db")
        
    c = sqlite3.connect("test_legacy_peer.db")
    # Partial legacy peer_context (missing availability_state and coverage_ratio)
    c.execute("CREATE TABLE peer_context(company TEXT, group_id TEXT, metric TEXT, company_value REAL, peer_median REAL, peer_min REAL, peer_max REAL, n_peers INTEGER, version TEXT, unavailable_peers TEXT, position TEXT, coverage_count INTEGER, total_peer_count INTEGER)")
    c.execute("INSERT INTO peer_context VALUES ('AAPL', 'G1', 'revenue', 100, 110, 100, 120, 5, 'v1', '', 'BOTTOM', 5, 5)")
    c.commit()
    c.close()
    
    db = connect("test_legacy_peer.db")
    res = db.execute("SELECT * FROM peer_context").fetchall()
    
    assert len(res) == 1
    row = dict(res[0])
    assert "availability_state" in row
    assert "coverage_ratio" in row
    
    db.close()
    if os.path.exists("test_legacy_peer.db"):
        os.remove("test_legacy_peer.db")

def test_legacy_migration_index_rebuild():
    """
    Migration must rebuild table if UNIQUE constraint doesn't perfectly match
    the modern identity, even if *some* UNIQUE constraint exists.
    """
    import os
    import sqlite3
    from financial_radar.store import connect
    
    if os.path.exists("test_idx.db"): os.remove("test_idx.db")
    
    c = sqlite3.connect("test_idx.db")
    c.execute("""CREATE TABLE observations(
        company TEXT, metric TEXT, value REAL, unit TEXT, period_end TEXT, 
        period_type TEXT, quality TEXT, comparable INTEGER, reason TEXT, 
        provenance TEXT, period_start TEXT, derived_from TEXT, 
        fiscal_year INTEGER, fiscal_period TEXT,
        UNIQUE(company, metric) -- Wrong unique constraint!
    )""")
    c.execute("INSERT INTO observations (company, metric, value) VALUES ('AAPL', 'revenue', 100)")
    c.commit()
    c.close()
    
    # Run migration
    db = connect("test_idx.db")
    
    # Verify exact unique index is now present
    def has_exact_unique_index(db, table_name, expected_cols):
        for r in db.execute(f"PRAGMA index_list({table_name})").fetchall():
            if r["unique"]:
                idx_name = r["name"]
                cols = [ci["name"] for ci in db.execute(f"PRAGMA index_info({idx_name})").fetchall()]
                if cols == expected_cols:
                    return True
        return False
        
    assert has_exact_unique_index(db, "observations", ["company", "metric", "period_end", "period_type", "unit", "period_start"]), "Observations should have been rebuilt to the correct index"
    
    res = db.execute("SELECT * FROM observations").fetchall()
    assert len(res) == 1
    assert dict(res[0])["value"] == 100
    
    db.close()
    if os.path.exists("test_idx.db"): os.remove("test_idx.db")
