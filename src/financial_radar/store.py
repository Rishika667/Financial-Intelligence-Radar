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
    UNIQUE(company, metric, version)
);
"""


def connect(path="data/radar.sqlite"):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(path)
    c.row_factory = sqlite3.Row
    c.executescript(DDL)
    # Safely migrate existing databases
    for stmt in [
        "ALTER TABLE events ADD COLUMN form TEXT",
        "ALTER TABLE events ADD COLUMN extraction_version TEXT",
        "ALTER TABLE signals ADD COLUMN components TEXT",
        "ALTER TABLE observations ADD COLUMN period_start TEXT",
        "ALTER TABLE observations ADD COLUMN derived_from TEXT",
    ]:
        try:
            c.execute(stmt)
        except sqlite3.OperationalError:
            pass
    # Idempotent unique index on natural observation identity
    try:
        c.execute(
            'CREATE UNIQUE INDEX IF NOT EXISTS idx_obs_identity '
            'ON observations(company, metric, period_end, period_type, unit, '
            'IFNULL(period_start, ""))'
        )
    except sqlite3.OperationalError:
        pass
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
                }
                for p in o.provenance
            ],
            default=str,
        )
        c.execute(
            "INSERT OR REPLACE INTO observations"
            "(company, metric, value, unit, period_end, period_type, "
            "quality, comparable, reason, provenance, period_start, derived_from) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
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
                o.period_start.isoformat() if getattr(o, "period_start", None) else None,
                json.dumps(list(o.derived_from)) if getattr(o, "derived_from", None) else None,
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
            "period_start": o.period_start.isoformat() if getattr(o, "period_start", None) else None,
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
            ))

        start_str = r.get("period_start")
        start_dt = date.fromisoformat(start_str) if start_str else None
        der_str = r.get("derived_from")
        der_from = tuple(json.loads(der_str)) if der_str else ()

        out.append(Observation(
            r["company"], r["metric"], r["value"], r["unit"],
            date.fromisoformat(r["period_end"]), r["period_type"],
            DataQuality(r["quality"]), tuple(provs), der_from,
            bool(r["comparable"]), r.get("reason"), start_dt,
        ))
    return out
