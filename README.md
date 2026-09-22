# Financial Intelligence Radar
Zero-cost, evidence-first SEC disclosure intelligence for analyst attention—not investment advice.

## Quick start
- Supported Python: **3.11**.
- Create an environment: `python -m venv .venv`, then activate it.
- Install: `python -m pip install -e '.[dev]'`.
- Run validation: `python -m pytest -q`.
- Launch: `streamlit run app.py`.

The application creates `data/radar.sqlite` locally and preserves SEC JSON under `data/raw/`. Select companies, save the watchlist, open **Refresh SEC data**, and enter a genuine contact email for the SEC User-Agent. Refresh is explicit, local, and uses only SEC public endpoints.

## Validation
GitHub Actions uses Python 3.11, compiles source and app.py, then runs pytest on pushes and pull requests. The real SEC smoke test is intentionally network-gated: run `RUN_SEC_SMOKE=1 python -m pytest tests/test_smoke.py -q`. It retrieves AAPL submissions/companyfacts, preserves raw JSON, normalizes observations, and asserts a reported revenue fact. It is not run in CI.

No paid API, API key, or cloud service is required.