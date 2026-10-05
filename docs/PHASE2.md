# Phase 2 Documentation

Phase 2 implements a 51-company representative universe, sector-aware peer groups, SQLite persistence (portfolio, watchlist, observations, signals, and events), robust SEC EDGAR ingestion, and 10 deterministic financial signals.

Unknown XBRL concepts remain `NOT_REPORTED` rather than guessed. The `app.py` dashboard surfaces actionable intel with full tabular drill-down into the raw JSON evidence, providing explicit provenance (Accession, Form, XBRL Concept, and Filing URL). Peer context distinguishes gracefully between missing data, inadequate comparable peers, and available metrics. Portfolio positions (via CSV import) are seamlessly saved and integrated.
