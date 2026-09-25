# Financial Intelligence Radar
Zero-cost, evidence-first SEC disclosure intelligence for analyst attention—not investment advice.

## Quick start
- Supported Python: **3.11**.
- Create an environment: `python -m venv .venv`, then activate it.
- Install: `python -m pip install -e '.[dev]'`.
- Run validation: `python -m pytest -q`.
- Launch: `streamlit run app.py`.

## SEC Access
SEC EDGAR requires operator identification. Before refreshing data, set the `SEC_USER_AGENT` environment variable:
```
export SEC_USER_AGENT="YourAppName your-email@example.com"
```
The application will not use a fake/generic fallback. A genuine contact email is required.

The application creates `data/radar.sqlite` locally and preserves SEC JSON under `data/raw/`. Select companies in the Portfolio watchlist, save, then click **Refresh SEC Data for Active Portfolio**.

## Primary Workflow: Portfolio Intelligence
1. **Watchlist Management:** Select companies to monitor via the Portfolio tab watchlist editor. Save the watchlist explicitly.
2. **SEC Refresh:** Click "Refresh SEC Data for Active Portfolio" to fetch XBRL facts and 8-K filings from SEC EDGAR. Refresh is manual and explicit.
3. **Signal Triage:** Active signals are shown only for watched companies. Each signal has severity (analyst attention priority), confidence, and evidence.
4. **Signal Drill-Down:** In Research Mode, expand any signal to see the full evidence chain: current/prior observations, derived_from lineage, XBRL concepts, accession numbers, filing dates, and SEC source URLs.
5. **Filing Events:** 8-K events are extracted deterministically and presented separately from financial signals. The analyst determines causation.
6. **Peer Context:** Peer comparisons are computed within explicitly configured peer groups with strict compatibility requirements.

## Research Mode
Drill into any company's financial observations, signals (with evidence drill-down), filing events, peer context, and full XBRL provenance.

## Signals
Ten deterministic financial signals, each with severity (analyst attention priority), confidence, evidence provenance, and suppression rationale:

| Signal | Type |
|--------|------|
| RECEIVABLES_REVENUE_DIVERGENCE | Monetary divergence |
| INVENTORY_SALES_DIVERGENCE | Monetary divergence |
| GROSS_MARGIN_COMPRESSION | Ratio decline |
| OPERATING_MARGIN_DETERIORATION | Ratio decline |
| EARNINGS_CASH_CONVERSION_DETERIORATION | Ratio decline |
| FREE_CASH_FLOW_DETERIORATION | Monetary decline |
| LEVERAGE_INTEREST_BURDEN | Ratio increase |
| LIQUIDITY_COMPRESSION | Ratio decline |
| SHARE_COUNT_DILUTION | Percentage increase |
| MULTI_FACTOR_DETERIORATION_CLUSTER | 3+ simultaneous signals |

Signal severity is determined by fixed deterministic thresholds and indicates analyst attention priority, not formal accounting materiality judgments.

## Validation
GitHub Actions uses Python 3.11, compiles source and app.py, then runs pytest on pushes and pull requests. The real SEC smoke test is intentionally network-gated: run `RUN_SEC_SMOKE=1 python -m pytest tests/test_smoke.py -q`. It is not run in CI.

No paid API, API key, or cloud service is required.

## Intentional limitations
- **Historical Coverage Bound.** Ingestion uses the SEC’s ‘recent’ submissions index. This bounds historical context to approximately the most recent 1,000 filings per company. The system does not claim guaranteed 7–10 year coverage; actual depth depends on filing frequency.
- **US-GAAP scope only.** XBRL concept mapping covers a curated set of US-GAAP tags. IFRS taxonomies are not supported.
- **No runtime FX conversion.** All monetary comparisons require matching units; USD vs EUR observations are suppressed, not converted.
- **Heuristic fiscal-period classification.** Quarter/YTD/annual periods are inferred from date ranges (80–100 days = quarter, etc.). Non-standard fiscal calendars may misclassify.
- **Amendment/later-filing precedence, not semantic restatement detection.** Later filings for the same period supersede earlier ones deterministically. The system does not semantically parse whether a value change constitutes a “restatement.”
- **Dimensional-fact suppression.** Facts with segment/axis/member dimensions are excluded to prevent treating dimensional breakdowns as consolidated totals.
- **Deterministic 8-K event extraction.** Events are extracted via conservative regex patterns (precision over recall). No LLM/NLP is used. Coverage is limited to the 5 most recent 8-K filings per company.
- **Bounded peer groups.** Peer groups are explicitly configured (24-company universe). The system does not automatically discover or expand peers.
- **Manual SEC refresh.** Data refresh is operator-initiated, not scheduled.
- **No investment recommendations, valuation, or prediction.**
