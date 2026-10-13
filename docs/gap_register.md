# Financial Intelligence Radar — Gap Register

**Current Audit Date**: 2026-10-13  
**Status**: MVP Completion Pass Complete across Workstreams A–G. All material functional gaps closed.

---

## 1. Closed Workstream Items

### Workstream A: Full Searchable Company Universe
- **Requirement**: Full S&P 500 universe representation instead of only 51 companies, with authoritative metadata and backward compatibility.
- **Resolution**: Generated `config/sp500_universe_2026.json` representing 503 constituents from the official S&P 500 index (snapshot: 2026-10-13). Mapped 10-digit zero-padded CIKs, GICS sectors, sub-industries, dual share classes (e.g., GOOG/GOOGL), and curated peer mappings. Preserved `config/sp500_representative_51_2026.json` as an optional baseline.

### Workstream B: Research Mode for Full Universe
- **Requirement**: Research mode should allow selecting any supported company in the universe, not merely monitored tickers.
- **Resolution**: Updated `app.py` Tab 3 (Research Mode) to allow selecting any company from `universe`. Added explicit `NOT-YET-LOADED` state when data is not yet ingested, with an on-demand single-company SEC fetch action and full SEC evidence linking.

### Workstream C: Persistent Analyst Review Workflow
- **Requirement**: Attention Queue alerts must have persistent triage states and notes surviving restarts.
- **Resolution**: Created `analyst_reviews` table in `src/financial_radar/store.py` with columns `(alert_fingerprint, company, signal_id, status, notes, updated_at, updated_by)`. Implemented deterministic alert fingerprinting (`generate_alert_fingerprint`), CRUD operations, status filters, and UI forms in `app.py`.

### Workstream D: Data Quality & Refresh Monitoring
- **Requirement**: Dedicated data quality surface beyond simple status messages.
- **Resolution**: Implemented Tab 4 "Data Quality & Refresh" with universe vs monitoring counters, readiness state distributions, core financial metrics diagnostics, peer coverage integrity, suppressed signal audit, regulatory freshness rules, and persistent refresh history log backed by `refresh_history` SQLite table.

### Workstream E: 10-Company Multi-Period SEC Fixtures
- **Requirement**: Multi-company, multi-period offline fixtures across diverse sectors to validate multi-year trends.
- **Resolution**: Acquired, compacted, and checked in official SEC submissions and company facts for 10 prominent companies: AAPL, MSFT, NVDA, JPM, AMZN, GOOGL, META, TSLA, JNJ, XOM. Added comprehensive test suite `tests/test_sec_multi_period_fixtures.py` and updated `tests/test_sec_golden.py`.

### Workstream F: Preflight Hardening, SQLite Safety & Migrations
- **Requirement**: Hardened SEC connectivity checks and safe SQLite migrations with WAL mode.
- **Resolution**: Refactored `test_sec_connectivity()` into 3 independent diagnostic probes (homepage, submissions endpoint, company facts endpoint) with operator email validation. Configured SQLite with WAL mode (`PRAGMA journal_mode=WAL`) and `PRAGMA busy_timeout=30000`. Wrapped migrations in rollback-safe transaction blocks.

---

## 3. Final Resume-Readiness Closeout Repairs

### 1. SQLite Migration Atomicity & Rollback Safety
- **Issue**: Multi-step migrations previously invoked `executescript(DDL)` which triggered implicit commits in SQLite, preventing full rollback upon mid-migration failures.
- **Resolution**: Eliminated `executescript()` inside the migration transaction. Implemented explicit transaction control (`c.isolation_level = None`, `BEGIN IMMEDIATE`, and `COMMIT`/`ROLLBACK`) using purely transactional DDL/DML statements (`CREATE TABLE ...`, `INSERT ...`, `DROP TABLE ...`, `ALTER TABLE ... RENAME`). Added failure-injection regression test verifying database integrity after simulated mid-migration crash.

### 2. Full Universe Enforcement & CIK Integrity
- **Issue**: `load_universe()` previously silently fell back to the 51-company baseline if the full universe was absent; test checks were wrapped in file-existence conditions.
- **Resolution**: `load_universe()` now raises `FileNotFoundError` if the full 503-constituent universe file is missing. The 51-company baseline is preserved solely as an explicit compatibility mode. Added unconditional test suite assertions verifying 503 unique constituents, valid 10-digit zero-padded CIKs, and restricted duplicate CIKs exclusively to verified dual-class shares (`GOOG/GOOGL`, `FOX/FOXA`, `NWSA/NWS`).

### 3. Unconditional Multi-Period Assertions & Exact Values
- **Issue**: Previous multi-period comparison assertions for MSFT were conditional (`if curr and prior:`) and aggregate coverage checks permitted 40% of companies to lack multi-year data.
- **Resolution**: Replaced conditional logic with strict unconditional assertions across 5 companies with verified YoY quarterly matching (`AMZN`, `META`, `TSLA`, `JNJ`, `XOM`) with exact expected revenue amounts and growth rates. Confirmed 9 of 10 companies have multi-year data in checked-in fixtures, and verified that incomplete periods (`MSFT`, `JPM`) are strictly withheld without generating spurious signals.

### 4. Alert Fingerprint Integrity for Revised/Restated Evidence
- **Issue**: Alert fingerprints previously omitted evidence values and quality, risking that materially revised or restated data could inherit stale review notes.
- **Resolution**: Enhanced `generate_alert_fingerprint()` to incorporate canonical values, units, data quality (`REPORTED`, `RESTATED`, `AMENDED`), and accession numbers. Added regression tests verifying distinct fingerprints for revised values and restatements while guaranteeing identical fingerprints on repeat evaluations.

### 5. Clear Freshness Guidance & Portfolio Wording
- **Resolution**: Rephrased the Data Quality freshness documentation to explicitly state that aging disclosures represent documented regulatory guidance (automated calculation engine is out-of-scope). Updated portfolio CSV validation error message to reference "supported company universe" rather than "51-company universe".

