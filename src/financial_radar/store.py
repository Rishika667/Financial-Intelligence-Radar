import json
import sqlite3
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

DDL = """CREATE TABLE IF NOT EXISTS watchlist(
    ticker TEXT PRIMARY KEY, cik TEXT, active INTEGER, metadata TEXT
);
CREATE TABLE IF NOT EXISTS filings(
    accession TEXT PRIMARY KEY, cik TEXT, form TEXT, filed TEXT, source_url TEXT
);
CREATE TABLE IF NOT EXISTS observations(
    company TEXT, metric TEXT, value REAL, unit TEXT, period_end TEXT,
    period_type TEXT, quality TEXT, comparable INTEGER, reason TEXT,
    provenance TEXT, period_start TEXT, derived_from TEXT,
    fiscal_year INTEGER, fiscal_period TEXT,
    UNIQUE(company, metric, period_end, period_type, unit, period_start)
);
CREATE TABLE IF NOT EXISTS signals(
    signal_id TEXT, company TEXT, severity TEXT, confidence TEXT,
    explanation TEXT, suppressed TEXT, evidence TEXT, version TEXT DEFAULT 'v1',
    components TEXT
);
CREATE TABLE IF NOT EXISTS events(
    id TEXT PRIMARY KEY, company TEXT, type TEXT, filed TEXT,
    accession TEXT, source_url TEXT, description TEXT,
    form TEXT, extraction_version TEXT
);
CREATE TABLE IF NOT EXISTS peer_context(
    company TEXT, group_id TEXT, metric TEXT, company_value REAL,
    peer_median REAL, peer_min REAL, peer_max REAL, n_peers INTEGER,
    version TEXT,
    unavailable_peers TEXT,
    position TEXT,
    coverage_count INTEGER,
    total_peer_count INTEGER,
    coverage_ratio REAL,
    availability_state TEXT,
    UNIQUE(company, metric, version)
);

CREATE TABLE IF NOT EXISTS portfolio(
    ticker TEXT PRIMARY KEY, shares REAL, weight REAL, exposure REAL, cost_basis REAL
);
CREATE TABLE IF NOT EXISTS system_state(
    key TEXT PRIMARY KEY, value TEXT
);
"""


def connect(db_path="financial_radar.sqlite"):
    c = sqlite3.connect(db_path, check_same_thread=False)
    c.row_factory = sqlite3.Row
    c.executescript(DDL)
    
# Grab original SQL to check if it's the legacy schema
    row = c.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='observations'").fetchone()
    old_sql = row["sql"] if row else ""
    needs_rebuild = "UNIQUE(company, metric, period_end, period_type, unit, period_start)" not in old_sql

    # Safe migration for existing observations table
    cols = [r["name"] for r in c.execute("PRAGMA table_info(observations)")]
    if "period_start" not in cols:
        c.execute("ALTER TABLE observations ADD COLUMN period_start TEXT")
    if "derived_from" not in cols:
        c.execute("ALTER TABLE observations ADD COLUMN derived_from TEXT")
    if "fiscal_year" not in cols:
        c.execute("ALTER TABLE observations ADD COLUMN fiscal_year INTEGER")
    if "fiscal_period" not in cols:
        c.execute("ALTER TABLE observations ADD COLUMN fiscal_period TEXT")
    if "reason" not in cols:
        c.execute("ALTER TABLE observations ADD COLUMN reason TEXT")

    if needs_rebuild:
        # Create temp table, copy data, replace
        c.execute("CREATE TABLE observations_new AS SELECT * FROM observations WHERE 0")
        c.execute("DROP TABLE observations_new")
        # Rename old to old, create new with DDL, copy
        c.execute("ALTER TABLE observations RENAME TO observations_old")
        c.executescript(DDL)
        # Note: DDL creates new observations table
        
        # Now copy. The columns in observations_old match the newly added ones
        # We need to list them explicitly to match the new schema order or just insert by name
        c.execute("INSERT OR IGNORE INTO observations (company, metric, value, unit, period_end, period_type, quality, comparable, reason, provenance, period_start, derived_from, fiscal_year, fiscal_period) SELECT company, metric, value, unit, period_end, period_type, quality, comparable, reason, provenance, COALESCE(period_start, ''), derived_from, fiscal_year, fiscal_period FROM observations_old")
        c.execute("DROP TABLE observations_old")

    # Migrate peer_context table
    p_cols = [r["name"] for r in c.execute("PRAGMA table_info(peer_context)")]
    for col, col_type in [("position", "TEXT"), ("coverage_count", "INTEGER"), ("total_peer_count", "INTEGER"), ("coverage_ratio", "REAL"), ("availability_state", "TEXT")]:
        if col not in p_cols:
            c.execute(f"ALTER TABLE peer_context ADD COLUMN {col} {col_type}")

    return c


def save_watchlist(c, rows):
    for x in rows:
        c.execute(
            "INSERT OR REPLACE INTO watchlist VALUES(?,?,?,?)",
            (x["ticker"], x["cik"], int(x.get("active", True)), json.dumps(x)),
        )
    c.commit()


def save_observations(c, rows):
    for o in rows:
        p = json.dumps(
            [
                {
                    "accession": p.accession,
                    "source_url": p.source_url,
                    "filing_date": p.filing_date.isoformat(),
                    "form": p.form,
                    "concept": p.concept,
                    "retrieval_timestamp": p.retrieval_timestamp.isoformat(),
                    "raw_value": p.raw_value,
                    "mapping_version": p.mapping_version,
                    "period_start": p.period_start.isoformat() if getattr(p, "period_start", None) else None,
                    "fiscal_year": getattr(p, "fiscal_year", None),
                    "fiscal_period": getattr(p, "fiscal_period", None),
                }
                for p in o.provenance
            ],
            default=str,
        )
        c.execute(
            "INSERT OR REPLACE INTO observations"
            "(company, metric, value, unit, period_end, period_type, "
            "quality, comparable, reason, provenance, period_start, derived_from, "
            "fiscal_year, fiscal_period) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                o.company,
                o.metric,
                o.value,
                o.unit,
                o.period_end.isoformat(),
                o.period_type,
                o.quality.value if hasattr(o.quality, "value") else str(o.quality),
                int(o.comparable),
                o.comparability_reason,
                p,
                o.period_start.isoformat() if getattr(o, "period_start", None) else '',
                json.dumps(list(o.derived_from)) if getattr(o, "derived_from", None) else None,
                getattr(o, "fiscal_year", None),
                getattr(o, "fiscal_period", None),
            ),
        )
    c.commit()


def _serialize_evidence(evidence):
    """Serialize signal evidence observations with full provenance chain.

    Persists metric, value, unit, period_end, period_type, quality,
    period_start, derived_from, and the complete provenance array for each
    evidence observation.  This allows a persisted signal to be traced back to:
      signal -> evidence observation -> provenance -> accession/form/date/SEC URL.
    """
    out = []
    for o in evidence:
        prov_list = []
        for p in o.provenance:
            prov_list.append({
                "accession": p.accession,
                "source_url": p.source_url,
                "filing_date": p.filing_date.isoformat(),
                "form": p.form,
                "concept": p.concept,
                "raw_value": p.raw_value,
                "mapping_version": p.mapping_version,
                "period_start": p.period_start.isoformat() if getattr(p, "period_start", None) else None,
                "fiscal_year": getattr(p, "fiscal_year", None),
                "fiscal_period": getattr(p, "fiscal_period", None),
            })
        out.append({
            "metric": o.metric,
            "value": o.value,
            "unit": o.unit,
            "period_end": o.period_end.isoformat(),
            "period_type": o.period_type,
            "quality": o.quality.value if hasattr(o.quality, 'value') else str(o.quality),
            "comparable": o.comparable,
            "provenance": prov_list,
            "derived_from": list(o.derived_from),
            "period_start": o.period_start.isoformat() if getattr(o, "period_start", None) else '',
            "fiscal_year": getattr(o, "fiscal_year", None),
            "fiscal_period": getattr(o, "fiscal_period", None),
        })
    return out


def save_signals(c, rows):
    for s in rows:
        if s:
            c.execute(
                "INSERT INTO signals VALUES(?,?,?,?,?,?,?,?,?)",
                (
                    s.signal_id,
                    s.company,
                    s.severity,
                    s.confidence,
                    s.explanation,
                    s.suppressed_reason,
                    json.dumps(_serialize_evidence(s.evidence)),
                    getattr(s, "version", "v1"),
                    json.dumps(s.component_signal_ids) if getattr(s, "component_signal_ids", None) else None,
                ),
            )
    c.commit()


def save_events(c, rows):
    for e in rows:
        c.execute(
            "INSERT OR REPLACE INTO events VALUES(?,?,?,?,?,?,?,?,?)",
            (
                e["id"],
                e["company"],
                e["type"],
                e.get("filing_date"),
                e.get("accession"),
                e.get("source_url"),
                e["description"],
                e.get("form"),
                e.get("extraction_version"),
            ),
        )
    c.commit()


def save_peer_context(c, company, contexts):
    """Persist peer context rows for a company."""
    for ctx in contexts.get("contexts", []):
        pr = ctx.get("peer_range") or (None, None)
        c.execute(
            "INSERT OR REPLACE INTO peer_context VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                company,
                contexts.get("group_id"),
                ctx.get("metric"),
                ctx.get("company_value"),
                ctx.get("peer_median"),
                pr[0],
                pr[1],
                ctx.get("n_peers"),
                ctx.get("peer_group_version"),
                json.dumps(ctx.get("unavailable_peers", [])),
                ctx.get("position"),
                ctx.get("coverage_count"),
                ctx.get("total_peer_count"),
                ctx.get("coverage_ratio"),
                ctx.get("availability_state")
            )
        )
    c.commit()


def clear_signals(c, company):
    """Remove old signals for a company before re-evaluation."""
    c.execute("DELETE FROM signals WHERE company=?", (company,))
    c.commit()


def clear_peer_context(c, company):
    """Remove old peer context for a company before refresh."""
    c.execute("DELETE FROM peer_context WHERE company=?", (company,))
    c.commit()


def rows(c, sql, args=()):
    return [dict(x) for x in c.execute(sql, args).fetchall()]


def save_filings(c, cik, filings_dict):
    for f in filings_dict.values():
        c.execute(
            "INSERT OR REPLACE INTO filings VALUES(?,?,?,?,?)",
            (
                f.get("accessionNumber"),
                cik,
                f.get("form"),
                f.get("filingDate"),
                f.get("source_url"),
            ),
        )
    c.commit()


def load_observations_for_companies(c, companies):
    """Load observations for a list of companies from SQLite.

    Converts each sqlite3.Row to a dict first so .get() works for
    columns that may not exist in older databases (period_start,
    derived_from).
    """
    from datetime import date, datetime
    from .models import Observation, DataQuality, Provenance

    out = []
    if not companies:
        return out

    placeholders = ",".join("?" * len(companies))
    q = f"SELECT * FROM observations WHERE company IN ({placeholders})"
    for raw_row in c.execute(q, tuple(companies)):
        r = dict(raw_row)
        p_raw = json.loads(r["provenance"])
        provs = []
        for p in p_raw:
            provs.append(Provenance(
                p["accession"],
                p["source_url"],
                date.fromisoformat(p["filing_date"]),
                p["form"],
                p["concept"],
                datetime.fromisoformat(p["retrieval_timestamp"]),
                p.get("raw_value"),
                p.get("mapping_version", "v1"),
                date.fromisoformat(p["period_start"]) if p.get("period_start") else None,
                p.get("fiscal_year"),
                p.get("fiscal_period")
            ))

        start_str = r.get("period_start")
        start_dt = date.fromisoformat(start_str) if start_str else None
        der_str = r.get("derived_from")
        der_from = tuple(json.loads(der_str)) if der_str else ()

        out.append(Observation(
            company=r["company"], metric=r["metric"], value=r["value"], unit=r["unit"],
            period_end=date.fromisoformat(r["period_end"]), period_type=r["period_type"],
            quality=DataQuality(r["quality"]), provenance=tuple(provs), derived_from=der_from,
            comparable=bool(r["comparable"]), comparability_reason=r.get("reason"), 
            period_start=start_dt, fiscal_year=r.get("fiscal_year"), fiscal_period=r.get("fiscal_period"),
        ))
    return out

def save_portfolio(c, rows):
    c.execute("DELETE FROM portfolio")
    for r in rows:
        c.execute(
            "INSERT OR REPLACE INTO portfolio VALUES(?,?,?,?,?)",
            (r["ticker"], r.get("shares"), r.get("weight"), r.get("exposure"), r.get("cost_basis"))
        )
    c.commit()

def load_portfolio(c):
    return rows(c, "SELECT * FROM portfolio")
