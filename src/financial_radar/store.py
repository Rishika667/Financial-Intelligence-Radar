import json
import sqlite3
from pathlib import Path

DDL = """CREATE TABLE IF NOT EXISTS watchlist(
    ticker TEXT PRIMARY KEY, cik TEXT, active INTEGER, metadata TEXT
);
CREATE TABLE IF NOT EXISTS filings(
    accession TEXT PRIMARY KEY, cik TEXT, form TEXT, filed TEXT, source_url TEXT
);
CREATE TABLE IF NOT EXISTS observations(
    company TEXT, metric TEXT, value REAL, unit TEXT, period_end TEXT,
    period_type TEXT, quality TEXT, comparable INTEGER, reason TEXT,
    provenance TEXT,
    UNIQUE(company, metric, period_end, period_type, provenance)
);
CREATE TABLE IF NOT EXISTS signals(
    signal_id TEXT, company TEXT, severity TEXT, confidence TEXT,
    explanation TEXT, suppressed TEXT, evidence TEXT, version TEXT DEFAULT 'v1'
);
CREATE TABLE IF NOT EXISTS events(
    id TEXT PRIMARY KEY, company TEXT, type TEXT, filed TEXT,
    accession TEXT, source_url TEXT, description TEXT
);
CREATE TABLE IF NOT EXISTS peer_context(
    company TEXT, group_id TEXT, metric TEXT, company_value REAL,
    peer_median REAL, peer_min REAL, peer_max REAL, n_peers INTEGER,
    version TEXT,
    UNIQUE(company, metric, version)
);
"""


def connect(path="data/radar.sqlite"):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(path)
    c.row_factory = sqlite3.Row
    c.executescript(DDL)
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
                p.__dict__
                | {
                    "filing_date": p.filing_date.isoformat(),
                    "retrieval_timestamp": p.retrieval_timestamp.isoformat(),
                }
                for p in o.provenance
            ],
            default=str,
        )
        c.execute(
            "INSERT OR REPLACE INTO observations VALUES(?,?,?,?,?,?,?,?,?,?)",
            (
                o.company,
                o.metric,
                o.value,
                o.unit,
                o.period_end.isoformat(),
                o.period_type,
                o.quality.value,
                int(o.comparable),
                o.comparability_reason,
                p,
            ),
        )
    c.commit()


def save_signals(c, rows):
    for s in rows:
        if s:
            c.execute(
                "INSERT INTO signals VALUES(?,?,?,?,?,?,?,?)",
                (
                    s.signal_id,
                    s.company,
                    s.severity,
                    s.confidence,
                    s.explanation,
                    s.suppressed_reason,
                    json.dumps([o.metric for o in s.evidence]),
                    getattr(s, "version", "v1"),
                ),
            )
    c.commit()


def save_events(c, rows):
    for e in rows:
        c.execute(
            "INSERT OR REPLACE INTO events VALUES(?,?,?,?,?,?,?)",
            (
                e["id"],
                e["company"],
                e["type"],
                e.get("filing_date"),
                e.get("accession"),
                e.get("source_url"),
                e["description"],
            ),
        )
    c.commit()


def save_peer_context(c, company, contexts):
    """Persist peer context rows for a company."""
    for ctx in contexts.get("contexts", []):
        pr = ctx.get("peer_range") or (None, None)
        c.execute(
            "INSERT OR REPLACE INTO peer_context VALUES(?,?,?,?,?,?,?,?,?)",
            (
                company,
                ctx.get("group_id"),
                ctx["metric"],
                ctx.get("company_value"),
                ctx.get("peer_median"),
                pr[0],
                pr[1],
                ctx.get("n_peers"),
                ctx.get("peer_group_version"),
            ),
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
