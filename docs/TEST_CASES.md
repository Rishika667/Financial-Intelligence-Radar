# Test cases
CI runs Python 3.11 compilation and the local pytest suite. Deterministic tests cover:

- Signal directionality and controls for all 10 signals
- YTD standalone quarter derivation validation
- SQLite watchlist and observation persistence
- Observation idempotence (repeated saves with different provenance timestamps)
- Observation round-trip with period_start preservation
- Event extraction idempotence and metadata
- Event false-positive suppression (negative/terminated/abandoned acquisitions)
- Normalizer missing-data handling
- Strict unit/currency compatibility in calculations and signals
- Misaligned period detection in divergence, ratio, and FCF signals
- Dimensional suppression
- Amendment/later filing handling
- Filing persistence idempotence (INSERT OR REPLACE)
- Derived lineage (derived_from) survival through SQLite
- Cluster component signal lineage
- Production peer pipeline (mock SEC client → ingest → persist → reload → peer context)
- Safe peer context failure handling (no unbound variables)
- Signal evidence provenance chain survival through SQLite

The real SEC smoke test is opt-in through `RUN_SEC_SMOKE=1` and is skipped in CI. It uses AAPL only, with the existing rate-limited SEC client, and validates retrieval → raw persistence → normalizer. It requires network access and a compliant User-Agent.

Manual Streamlit visual testing remains required; CI verifies imports indirectly through compileall but does not render a browser.
