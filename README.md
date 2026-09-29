# Financial Intelligence Radar
Zero-cost, evidence-first SEC disclosure intelligence for analyst attention.

## Quick start
- Supported Python: **3.11**.
- Create an environment: python -m venv .venv, then activate it.
- Install: python -m pip install -e '.[dev]'.
- Run validation: python -m pytest -q.
- Launch: streamlit run app.py.

## SEC Access
SEC EDGAR requires operator identification. Set the SEC_USER_AGENT environment variable before launching the application:
`
export SEC_USER_AGENT="YourAppName your-email@example.com"
`
The application Setup tab contains an explicit SEC Preflight Check to verify connectivity and configuration.

## Workflow: Analyst Intelligence
1. **Company Selection:** Select companies to monitor from the curated S&P 500 representative universe.
2. **SEC Refresh:** Click "Refresh Selected Data" to deterministically extract XBRL facts and 8-K filings directly from SEC EDGAR.
3. **Attention Queue:** Triage actionable signals across monitored companies. The queue surfaces severity, metric impact, and clear investigation priorities.
4. **Research Mode:** A structured analyst workspace featuring:
   - Executive Snapshot (KPIs)
   - Cross-Metric Synthesis (Growth, Profitability, Cash Generation)
   - Actionable Signals with exact XBRL provenance
   - Filing/Event Context (Recent 8-Ks)
   - Peer Context (Deterministic groups via sp500_representative_50_2026.json)

## Signals & Synthesis
The synthesis engine evaluates empirical financial patterns without hallucinated causal claims. Core signals include margin compression, cash conversion deterioration, and multi-factor clusters. 

Sectors are explicitly handled: Financials (e.g., JPM) natively suppress generic debt/leverage signals that are fundamentally inapplicable to their business models.

## Provenance
Every financial observation and generated signal is traced explicitly to its source:
- SEC Accession Number
- XBRL Concept Tag
- Filing Date
- SEC Source URL
- Retrieval Timestamp

## Intentional limitations
- **Dynamic XBRL Mapping:** Curated US-GAAP tags only. IFRS taxonomies are unsupported.
- **Period Inference:** Fiscal periods are inferred heuristically from date intervals.
- **Peer Context:** Tightly bounded to the predefined sp500_representative_50_2026.json universe.
- **Text Parsing:** 8-K extraction relies on conservative regex rules (precision over recall), not LLMs.
- **No investment recommendations or predictions.**
