# Architecture
Implemented local flow: SEC submissions/companyfacts → rate-limited raw JSON → conservative accepted-concept normalization → SQLite observations/watchlist → period-safe comparable selection → deterministic signals → Streamlit portfolio/research views.

The Streamlit app reads the same SQLite tables populated by the pipeline; it does not use demo financial data. Provenance stored with each observation includes accession, SEC source URL, form, concept, raw value, filing date, retrieval timestamp, mapping version, and period_start. SEC filings are dynamically retrieved to extract 8-K intelligence automatically during ingestion, persisting events alongside metadata (form, version, snippet).

Ingestion is callable through pipeline functions and the UI. An operator sets the `SEC_USER_AGENT` environment variable (with genuine contact email) before refreshing data. No fake/generic fallback is used. Refresh is explicit and operator-initiated via the Portfolio view.

The Portfolio tab displays actionable signals for active watchlist companies only. The watchlist defaults to inactive for new companies and is saved explicitly by the user. Signals in Research Mode include an evidence drill-down that exposes the full chain: signal → explanation → evidence observations (current/prior, derived_from, period info) → XBRL provenance (concept, accession, form, filing date, raw value, SEC source URL).

Peer context is generated within explicitly configured peer groups and rendered in the UI. Restatements and amended filings are deterministically handled (later filing supersedes previous). Dimensional facts are strictly ignored to prevent cross-contamination.

Observation identity is company + metric + period_end + period_type + unit + period_start. Repeated SEC refreshes update existing observations idempotently via a unique SQLite index.

Debt aggregation prefers an existing total-debt XBRL fact. Only when no total-debt fact exists does the system derive it from current + non-current debt, preserving the full provenance chain from both inputs.
