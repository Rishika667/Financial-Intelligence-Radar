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

## 2. Documented Out-of-Scope Boundaries & Deferred Items

1. **Specialized Banking Ratios**: Specialized bank accounting metrics (Net Interest Margin, Common Equity Tier 1 ratio, non-accrual loan classifications) are out of scope for general corporate disclosure triage.
2. **Predictive / Speculative Modeling**: Share price targets, automated trading recommendations, and speculative price models are strictly out of scope per product principles.
3. **LLM / Generative Text Synthesis**: Unauditable generative LLM summaries are avoided in favor of deterministic accounting calculations with strict provenance linking back to exact SEC accession numbers.
4. **SEC EDGAR Rate Limit**: 10 requests per second limit enforced by SEC EDGAR policy.
