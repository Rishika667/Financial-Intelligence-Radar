# Financial Intelligence Radar

An evidence-first, zero-cost SEC disclosure intelligence and analyst-triage system.

## Status: FINAL RELEASE
**Final Code SHA**: `ed4c36ad4103804a1161ca1cc71a766f7a138298`  
**Test Suite**: 117 passed, 1 skipped  
**Coverage**: Measured across deterministic pipelines, SEC preflight, analytical metrics, portfolio constraints, and golden SEC fixtures.  

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
