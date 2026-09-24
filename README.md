# Financial Intelligence Radar
Zero-cost, evidence-first SEC disclosure intelligence for analyst attention—not investment advice.

## Quick start
- Supported Python: **3.11**.
- Create an environment: `python -m venv .venv`, then activate it.
- Install: `python -m pip install -e '.[dev]'`.
- Run validation: `python -m pytest -q`.
- Launch: `streamlit run app.py`.

The application creates `data/radar.sqlite` locally and preserves SEC JSON under `data/raw/`. Select companies, save the watchlist, open **Refresh SEC data**, and enter a genuine contact email for the SEC User-Agent. Refresh is explicit, local, and uses only SEC public endpoints.

## Signals
Ten deterministic financial signals, each with severity, confidence, evidence provenance, and suppression rationale:

| Signal | Type |
|--------|------|
| RECEIVABLES_REVENUE_DIVERGENCE | Monetary divergence |
| INVENTORY_SALES_DIVERGENCE | Monetary divergence |
| GROSS_MARGIN_COMPRESSION | Ratio decline |
| OPERATING_DELEVERAGE | Ratio decline |
| EARNINGS_CASH_CONVERSION_DETERIORATION | Ratio decline |
| FREE_CASH_FLOW_DETERIORATION | Monetary decline |
| LEVERAGE_INTEREST_BURDEN | Ratio increase |
| LIQUIDITY_COMPRESSION | Ratio decline |
| SHARE_COUNT_DILUTION | Percentage increase |
| MULTI_FACTOR_DETERIORATION_CLUSTER | 3+ simultaneous signals |

## Validation
GitHub Actions uses Python 3.11, compiles source and app.py, then runs pytest on pushes and pull requests. The real SEC smoke test is intentionally network-gated: run `RUN_SEC_SMOKE=1 python -m pytest tests/test_smoke.py -q`. It retrieves AAPL submissions/companyfacts, preserves raw JSON, normalizes observations, and asserts a reported revenue fact. It is not run in CI.

No paid API, API key, or cloud service is required.

## Intentional limitations
- **US-GAAP scope only.** XBRL concept mapping covers a curated set of US-GAAP tags. IFRS taxonomies are not supported.
- **No runtime FX conversion.** All monetary comparisons require matching units; USD vs EUR observations are suppressed, not converted.
- **Heuristic fiscal-period classification.** Quarter/YTD/annual periods are inferred from date ranges (80–100 days = quarter, etc.). Non-standard fiscal calendars may misclassify.
- **Amendment/later-filing precedence, not semantic restatement detection.** Later filings for the same period supersede earlier ones deterministically. The system does not semantically parse whether a value change constitutes a "restatement."
- **Deterministic 8-K event extraction.** Events are extracted via conservative regex patterns (precision over recall). No LLM/NLP is used. Coverage is limited to the 5 most recent 8-K filings per company.
- **No investment recommendations, valuation, or prediction.**
