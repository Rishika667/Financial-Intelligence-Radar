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
CREATE TABLE IF NOT EXISTS analyst_reviews(
    fingerprint TEXT PRIMARY KEY,
    company TEXT NOT NULL,
    signal_id TEXT NOT NULL,
    status TEXT NOT NULL,
    note TEXT,
    updated_at TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS refresh_history(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    ticker TEXT NOT NULL,
    status TEXT NOT NULL,
    observations_count INTEGER DEFAULT 0,
    signals_count INTEGER DEFAULT 0,
    error_message TEXT,
    refresh_type TEXT DEFAULT 'MONITORED_BATCH'
);
"""


def connect(db_path="financial_radar.sqlite"):
    c = sqlite3.connect(db_path, check_same_thread=False, timeout=30.0)
    c.row_factory = sqlite3.Row
    if db_path != ":memory:":
        try:
            c.execute("PRAGMA journal_mode=WAL;")
            c.execute("PRAGMA busy_timeout=30000;")
        except sqlite3.Error as e:
            logger.warning("Could not set WAL/busy_timeout on %s: %s", db_path, e)

    c.executescript(DDL)
    
    # Check if migration is needed
    def has_exact_unique_index(table_name, expected_cols):
        for r in c.execute(f"PRAGMA index_list({table_name})").fetchall():
            if r["unique"]:
                idx_name = r["name"]
                cols = [ci["name"] for ci in c.execute(f"PRAGMA index_info({idx_name})").fetchall()]
                if cols == expected_cols:
                    return True
        return False

    obs_cols = [r["name"] for r in c.execute("PRAGMA table_info(observations)")]
    missing_obs_cols = [col for col in ["period_start", "derived_from", "fiscal_year", "fiscal_period", "reason"] if col not in obs_cols]
    needs_obs_rebuild = not has_exact_unique_index("observations", ["company", "metric", "period_end", "period_type", "unit", "period_start"])
    needs_obs_migration = bool(missing_obs_cols) or needs_obs_rebuild

    p_cols = [r["name"] for r in c.execute("PRAGMA table_info(peer_context)")]
    expected_new_cols = [
        ("position", "TEXT"), ("coverage_count", "INTEGER"),
        ("total_peer_count", "INTEGER"), ("coverage_ratio", "REAL"),
        ("availability_state", "TEXT"), ("group_id", "TEXT"), 
        ("company_value", "REAL"), ("peer_median", "REAL"), 
        ("peer_min", "REAL"), ("peer_max", "REAL"), 
        ("n_peers", "INTEGER"), ("version", "TEXT"), 
        ("unavailable_peers", "TEXT")
    ]
    missing_pc_cols = [col for col, _ in expected_new_cols if col not in p_cols]
    needs_pc_rebuild = not has_exact_unique_index("peer_context", ["company", "metric", "version"])
    needs_pc_migration = bool(missing_pc_cols) or needs_pc_rebuild

    if needs_obs_migration or needs_pc_migration:
        old_isolation = c.isolation_level
        c.isolation_level = None  # Manual transaction control: disable Python's implicit commits
        try:
            c.execute("BEGIN IMMEDIATE")

            # 1. Observations migration
            if missing_obs_cols:
                for col in missing_obs_cols:
                    col_type = "INTEGER" if col == "fiscal_year" else "TEXT"
                    c.execute(f"ALTER TABLE observations ADD COLUMN {col} {col_type}")

            if needs_obs_rebuild:
                c.execute("""
                    CREATE TABLE observations_migrating (
                        company TEXT, metric TEXT, value REAL, unit TEXT, period_end TEXT,
                        period_type TEXT, quality TEXT, comparable INTEGER, reason TEXT,
                        provenance TEXT, period_start TEXT, derived_from TEXT,
                        fiscal_year INTEGER, fiscal_period TEXT,
                        UNIQUE(company, metric, period_end, period_type, unit, period_start)
                    )
                """)
                c.execute("""
                    INSERT OR IGNORE INTO observations_migrating (
                        company, metric, value, unit, period_end, period_type, quality,
                        comparable, reason, provenance, period_start, derived_from,
                        fiscal_year, fiscal_period
                    ) SELECT 
                        company, metric, value, unit, period_end, period_type, quality,
                        comparable, reason, provenance, COALESCE(period_start, ''), derived_from,
                        fiscal_year, fiscal_period 
                    FROM observations
                """)
                c.execute("DROP TABLE observations")
                c.execute("ALTER TABLE observations_migrating RENAME TO observations")

            # 2. Peer context migration
            if missing_pc_cols:
                for col, col_type in expected_new_cols:
                    if col in missing_pc_cols:
                        c.execute(f"ALTER TABLE peer_context ADD COLUMN {col} {col_type}")

            if needs_pc_rebuild:
                c.execute("""
                    CREATE TABLE peer_context_migrating (
                        company TEXT, group_id TEXT, metric TEXT, company_value REAL,
                        peer_median REAL, peer_min REAL, peer_max REAL, n_peers INTEGER,
                        version TEXT, unavailable_peers TEXT, position TEXT,
                        coverage_count INTEGER, total_peer_count INTEGER,
                        coverage_ratio REAL, availability_state TEXT,
                        UNIQUE(company, metric, version)
                    )
                """)
                c.execute("""
                    INSERT OR IGNORE INTO peer_context_migrating (
                        company, group_id, metric, company_value, peer_median, peer_min, peer_max, 
                        n_peers, version, unavailable_peers, position, coverage_count, 
                        total_peer_count, coverage_ratio, availability_state
                    ) SELECT 
                        company, group_id, metric, company_value, peer_median, peer_min, peer_max, 
                        n_peers, version, unavailable_peers, position, coverage_count, 
                        total_peer_count, coverage_ratio, availability_state 
                    FROM peer_context
                """)
                c.execute("DROP TABLE peer_context")
                c.execute("ALTER TABLE peer_context_migrating RENAME TO peer_context")

            c.execute("COMMIT")
        except Exception as e:
            try:
                c.execute("ROLLBACK")
            except Exception as rollback_err:
                logger.error("Rollback failed: %s", rollback_err)
            logger.error("Migration failed, transaction rolled back cleanly: %s", e)
            try:
                c.close()
            except Exception:
                pass
            raise
        finally:
            try:
                c.isolation_level = old_isolation
            except Exception:
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


VALID_REVIEW_STATUSES = {"NEW", "ACKNOWLEDGED", "UNDER_REVIEW", "DISMISSED", "EXPECTED", "RESOLVED"}


def generate_alert_fingerprint(company, signal_id, evidence=None, version="v1"):
    """Generate a stable, deterministic alert fingerprint incorporating company,
    signal_id, rule version, and relevant comparison-period evidence including canonical
    values, units, quality, and accession provenance.
    """
    import hashlib
    evidence_items = []
    if evidence:
        ev_items = evidence
        if isinstance(ev_items, str):
            try:
                ev_items = json.loads(ev_items)
            except Exception:
                ev_items = []
        if isinstance(ev_items, (list, tuple)):
            for item in ev_items:
                if isinstance(item, dict):
                    m = item.get("metric", "")
                    pe = str(item.get("period_end", ""))
                    pt = str(item.get("period_type", ""))
                    fy = str(item.get("fiscal_year", ""))
                    fp = str(item.get("fiscal_period", ""))
                    u = str(item.get("unit", ""))
                    q = item.get("quality", "")
                    q_str = getattr(q, "value", str(q)) if q is not None else ""
                    val = item.get("value")
                    val_str = f"{float(val):.8g}" if (val is not None and isinstance(val, (int, float))) else ("None" if val is None else str(val))
                    prov = item.get("provenance")
                elif hasattr(item, "metric"):
                    m = getattr(item, "metric", "")
                    pe = str(getattr(item, "period_end", ""))
                    pt = getattr(item, "period_type", "")
                    fy = str(getattr(item, "fiscal_year", ""))
                    fp = str(getattr(item, "fiscal_period", ""))
                    u = str(getattr(item, "unit", ""))
                    q = getattr(item, "quality", None)
                    q_str = getattr(q, "value", str(q)) if q is not None else ""
                    val = getattr(item, "value", None)
                    val_str = f"{float(val):.8g}" if (val is not None and isinstance(val, (int, float))) else ("None" if val is None else str(val))
                    prov = getattr(item, "provenance", None)
                else:
                    continue

                accs = []
                if prov:
                    if isinstance(prov, str):
                        try:
                            prov = json.loads(prov)
                        except Exception:
                            prov = []
                    if isinstance(prov, (list, tuple)):
                        for p in prov:
                            if isinstance(p, dict) and p.get("accession"):
                                accs.append(str(p["accession"]))
                            elif hasattr(p, "accession") and p.accession:
                                accs.append(str(p.accession))
                accs_str = ",".join(sorted(set(accs)))

                evidence_items.append(f"{m}_{pe}_{pt}_{fy}_{fp}_val:{val_str}_u:{u}_q:{q_str}_acc:{accs_str}")

    evidence_str = "|".join(sorted(set(evidence_items)))
    raw = f"{company}:{signal_id}:{version}:{evidence_str}"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    return f"{company}_{signal_id}_{digest}"


def save_analyst_review(c, fingerprint, company, signal_id, status, note=None):
    """Save or update an analyst review record transactionally."""
    if status not in VALID_REVIEW_STATUSES:
        raise ValueError(f"Invalid review status '{status}'. Must be one of {VALID_REVIEW_STATUSES}")

    from datetime import datetime
    now = datetime.utcnow().isoformat()
    existing = rows(c, "SELECT * FROM analyst_reviews WHERE fingerprint=?", (fingerprint,))
    if existing:
        c.execute(
            "UPDATE analyst_reviews SET status=?, note=?, updated_at=? WHERE fingerprint=?",
            (status, note, now, fingerprint),
        )
    else:
        c.execute(
            "INSERT INTO analyst_reviews (fingerprint, company, signal_id, status, note, updated_at, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (fingerprint, company, signal_id, status, note, now, now),
        )
    c.commit()


def get_analyst_review(c, fingerprint):
    r = rows(c, "SELECT * FROM analyst_reviews WHERE fingerprint=?", (fingerprint,))
    return r[0] if r else None


def get_analyst_reviews_for_company(c, company):
    return rows(c, "SELECT * FROM analyst_reviews WHERE company=? ORDER BY updated_at DESC", (company,))


def get_all_analyst_reviews(c):
    return {r["fingerprint"]: r for r in rows(c, "SELECT * FROM analyst_reviews")}


def save_refresh_history(c, ticker, status, observations_count=0, signals_count=0, error_message=None, refresh_type="MONITORED_BATCH"):
    """Record an ingestion / refresh run in the persistent audit trail."""
    from datetime import datetime
    now = datetime.utcnow().isoformat()
    c.execute(
        "INSERT INTO refresh_history (timestamp, ticker, status, observations_count, signals_count, error_message, refresh_type) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (now, ticker, status, observations_count, signals_count, error_message, refresh_type),
    )
    c.commit()


def get_refresh_history(c, limit=50, ticker=None):
    if ticker:
        return rows(c, "SELECT * FROM refresh_history WHERE ticker=? ORDER BY id DESC LIMIT ?", (ticker, limit))
    return rows(c, "SELECT * FROM refresh_history ORDER BY id DESC LIMIT ?", (limit,))


def get_latest_refresh_time(c):
    r = rows(c, "SELECT timestamp FROM refresh_history WHERE status='SUCCESS' ORDER BY id DESC LIMIT 1")
    return r[0]["timestamp"] if r else None

