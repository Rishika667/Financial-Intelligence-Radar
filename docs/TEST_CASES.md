# Test cases
CI runs Python 3.11 compilation and the local pytest suite. Deterministic tests cover signal directionality/controls, YTD validation, SQLite watchlist and observations, event extraction, normalizer missing-data handling, and evidence-chain provenance.

The real SEC smoke test is opt-in through RUN_SEC_SMOKE=1 and is skipped in CI. It uses AAPL only, with the existing rate-limited SEC client, and validates retrieval → raw persistence → normalizer. It requires network access and a compliant User-Agent.

Manual Streamlit visual testing remains required; CI verifies imports indirectly through compileall but does not render a browser.