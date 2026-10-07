# Financial Intelligence Radar

An evidence-first, zero-cost SEC disclosure intelligence and analyst-triage system.

## Status: FINAL RELEASE
**Final Code SHA**: Verified on the final phase-branch HEAD with a successful GitHub Actions validation run.
**Test Suite**: Measured across deterministic pipelines, SEC preflight, analytical metrics, portfolio constraints, and golden SEC fixtures.

## Quick Start (Runnable Locally)

This project requires **NO paid APIs** and stores all data in a **local SQLite database**.

```bash
git clone https://github.com/Rishika667/Financial-Intelligence-Radar.git
cd Financial-Intelligence-Radar
python -m venv .venv
# On Windows: .venv\Scripts\activate
# On Mac/Linux: source .venv/bin/activate
pip install -e ".[dev]"

# Required for live SEC EDGAR fetching:
# Windows: set SEC_USER_AGENT="Your Name your.email@example.com"
# Mac/Linux: export SEC_USER_AGENT="Your Name your.email@example.com"

streamlit run app.py
```

*Note: For testing, deterministic golden SEC fixtures are included in the repository so tests run instantly without network access.*

## Features
- **100% SEC Authoritative Ingestion**: Fetches directly from EDGAR. No third-party data APIs.
- **Deterministic Derivation**: Exact provenance preservation from SEC payload to analytical metric to UI.
- **Strict Data Quality Hierarchy**: AMENDED/RESTATED > REPORTED > DERIVED.
- **Type-Safe Comparisons**: Period relationships enforced via fiscal semantics, never unsafe heuristics.
- **Research Mode**: Transparent narrative extraction with quantitative evidence.

## Known Limitations
1. **SEC Rate Limiting**: Max 10 requests/second enforced. Heavy concurrent portfolios may take time.
2. **Banking Metrics**: Lacks exhaustive semantic metrics for complex financial institutions (e.g. specialized loan loss provisions).
3. **No LLM/AI Narrative Parser**: Relies on deterministic thresholds; does not "read" management discussion paragraphs contextually.

*Disclaimer: This tool is for analyst triage and evidence surfacing. It provides no investment advice, prediction, or recommendation.*
