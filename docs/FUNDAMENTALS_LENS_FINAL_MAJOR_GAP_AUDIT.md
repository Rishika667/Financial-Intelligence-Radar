# Fundamentals Lens — Repository-Wide Requirements Traceability Matrix & Major Gap Audit
**Document ID:** `DOC-FL-GAP-AUDIT-001`  
**Author:** Rishika Dangayach  
**Product:** Fundamentals Lens — Evidence-First Financial Research Workbench  
**Repository:** `Rishika667/Financial-Intelligence-Radar`  
**Branch:** `pivot/fundamentals-lens-phase0`  
**Starting Commit:** `0436c63b8fda03a7522fb9ad94c386905782ba98`  
**Audit Date:** October 19, 2026  

---

## 1. Audit Scope & Methodology

This audit inspects all material requirements across the complete repository specification, including:
- Architecture, data foundation, and discrepancy ledger specifications (`docs/FUNDAMENTALS_LENS_DATA_FOUNDATION.md`, `docs/FUNDAMENTALS_LENS_DISCREPANCY_LEDGER.md`, `docs/FUNDAMENTALS_LENS_EVIDENCE_AUDIT.md`)
- Technical analysis methodology and market data invariants (`docs/TECHNICAL_ANALYSIS_METHODOLOGY.md`, `docs/FUNDAMENTALS_LENS_PRICE_DATA_AUDIT.md`)
- Deployment readiness standards (`docs/FUNDAMENTALS_LENS_DEPLOYMENT_READINESS.md`)
- Implementation in `src/fundamentals_lens/`, `scripts/`, `datasets/fundamentals_lens/`, `fundamentals_lens_app.py`, and `tests/fundamentals_lens/`
- Clean-clone isolation, CI workflows (`.github/workflows/validate.yml`), and legacy platform integration (`app.py`, `src/financial_radar/`)

Every requirement is audited against actual source code and execution behavior, not inherited assertions or closeout claims.

---

## 2. Requirement Traceability Matrix

| Req ID | Requirement & Expected Behavior | Authoritative Implementation Location | Existing Test & Coverage | Actual Working Status | Severity | Required Correction | Acceptance Test |
| :--- | :--- | :--- | :--- | :---: | :---: | :--- | :--- |
| **REQ-DISC-01** | **Exact Discrepancy & Adjustment Matching:** Discrepancy notes must authorize only exact numerical differences matching approved ledger entries (`primary_reported_value`). Arbitrary mismatches must remain `DISCREPANT`. | `scripts/build_evidence_register_phase13.py` (lines 372–409), `src/fundamentals_lens/validator.py` | `test_validator_adversarial.py` (Test 39) | **VULNERABLE** | **P0** | Establish single reconciliation function checking exact ledger values (`primary_reported_value` & canonical delta); arbitrary amounts must fail as `UNEXPLAINED_DISCREPANCY`. | Adversarial test: arbitrary reported value fails validation even when matching discrepancy note exists. |
| **REQ-SRC-01** | **Source Register Status Derivation:** Source-level reconciliation status in `source_register.json` must be derived from its metric observations, not pre-initialized on document identity alone. | `scripts/build_evidence_register_phase13.py` (lines 331), `datasets/fundamentals_lens/source_register.json` | `test_phase13_scenarios.py` (Test 8) | **DEFECTIVE** | **P0** | Aggregate metric reconciliation tiers: if any metric is discrepant or unverified, source register cannot be `INDEPENDENTLY_RECONCILED`. | Adversarial test: setting metric observation to unverified forces source register status to non-reconciled. |
| **REQ-PROV-01** | **Distinct Semantic Verification Statuses:** Explicitly separate fields for document identity, document retrieval, period match, metric extraction, and numeric reconciliation. | `scripts/build_evidence_register_phase13.py`, `src/fundamentals_lens/models.py`, `datasets/fundamentals_lens/evidence_register.json` | `test_validator_framework.py` | **PARTIAL** | **P0** | Introduce explicit schema fields: `document_identity_status`, `document_retrieval_status`, `period_match_status`, `metric_extraction_status`, `numeric_reconciliation_status`. | Schema & export tests asserting all 5 distinct status dimensions exist in evidence register. |
| **REQ-CLONE-01** | **Commit-Only Clean Clone Verification:** Clean-clone reproduction must test strictly the checked-out commit, without applying uncommitted local `git diff` patches. | `tests/fundamentals_lens/test_clean_clone_reproducibility.py` (lines 120–140) | `test_clean_clone_reproducibility.py` (Test 5) | **VULNERABLE** | **P0** | Remove `git diff HEAD` patch application from clean clone test; verify exact checked-out commit SHA in complete isolation. | Clean clone runs without diff patch; asserts tested commit SHA explicitly. |
| **REQ-MUT-01** | **Genuine Facts & Source Mutation Isolation:** Builder must accept explicit input paths / fixtures; mutating canonical facts fixture must leave observations unchanged; mutating source extract must change observations deterministically. | `scripts/build_source_observations_phase13.py`, `tests/fundamentals_lens/test_clean_clone_reproducibility.py` (lines 63–85) | `test_clean_clone_reproducibility.py` (Test 3) | **WEAK** | **P0** | Parameterize observation builder to accept explicit input file paths; pass genuinely mutated facts and source inputs to verify input isolation and output determinism. | Test passing mutated facts fixture leaves outputs identical; test passing mutated source extract changes observation. |
| **REQ-META-01** | **Authoritative Dynamic Metadata:** All metadata counts must be dynamically computed from underlying records. No duplicate keys or hardcoded numbers. | `src/fundamentals_lens/validator.py` (`validate_dataset_metadata`), `scripts/build_evidence_register_phase13.py` | `test_validator_adversarial.py` (Test 41) | **FUNCTIONAL** | **P0** | Add observation uniqueness validation; ensure sum of status counts equals total primary observations; ensure exports strictly agree. | Adversarial metadata tests with altered totals and contradictory legacy fields. |
| **REQ-UX-01** | **Technical Analysis Layout & Chart Visibility:** Primary candlestick & volume chart must be fully visible and unclipped on 1280x900 viewports on first load. | `fundamentals_lens_app.py` (lines 1130–1415), `src/fundamentals_lens/technical.py` | Visual QA scripts | **DEFECTIVE (CLIPPED)** | **P0** | Tighten layout hierarchy: integrate compact KPI strip, move checkboxes inline, adjust chart height (500px) and margins to eliminate vertical clipping. | CDP screenshot capture verifying full chart and volume subplot render above viewport fold. |
| **REQ-UX-02** | **Technical Analysis Functional Automation:** End-to-end UI automation testing chart traces, demo asset switching, benchmark comparison, and CSV invariant validation diagnostics. | `tests/fundamentals_lens/test_app_integration.py` | `test_app_integration.py` | **PARTIAL** | **P0** | Extend integration test to verify Plotly chart trace structure, asset switching, moving average toggles, and invalid CSV violation reporting. | Automated test suite exercising all 8 interactive technical analysis flows. |
| **REQ-FIN-01** | **Fundamental Metrics Mathematical Contract:** CAGR handles non-positive values; cash conversion handles zero/negative denominators; FCF preserves input confidence. | `src/fundamentals_lens/metrics.py`, `models.py` | `test_metrics_engine.py`, `test_deeper_fundamentals.py` | **FUNCTIONAL** | **P1** | Add regression tests covering non-positive start/end CAGR, near-zero net income conversion, and FCF input confidence propagation. | Adversarial tests for mathematical edge cases in `metrics.py`. |
| **REQ-PEER-01** | **Peer Incomparable Proxy Suppression:** TCS PBEI and Bajaj Auto EBITDA proxies suppressed from nominal rankings and plots with visible reasons; indexing handles non-positive base values. | `src/fundamentals_lens/peers.py` | `test_peer_comparison.py`, `test_phase13_scenarios.py` (Test 16) | **FUNCTIONAL** | **P1** | Verify that suppressed values are None in matrix data and cannot be plotted nominally in UI; verify export format. | Test verifying TCS and Bajaj Auto nominal values are None in comparison matrix. |
| **REQ-CI-01** | **Deterministic CI Workflow & Clean Imports:** Remote GitHub Actions workflow executes clean clone, builders, validator, and test suite with zero module import failures. | `.github/workflows/validate.yml`, Phase 12/13 script wrappers | GitHub Actions CI | **FUNCTIONAL** | **P0 (Resolved)** | Maintain path bootstrapping in all scripts; ensure clean clone step executes without error. | Remote GitHub Actions run status: green. |
| **REQ-SEC-01** | **Offline vs Online Regulatory Sourcing:** Distinguish reproducible offline extracted records from live SEC EDGAR online checks. Offline mode must never claim online verification. | `scripts/build_source_observations_phase13.py`, `datasets/fundamentals_lens/source_check_report.json` | `test_phase13_scenarios.py` (Test 8), `test_validator_adversarial.py` (Test 40) | **FUNCTIONAL** | **P0 (Resolved)** | Ensure `verification_mode: OFFLINE` and `check_status: OFFLINE_SOURCE_RECORDED` are recorded consistently. | Invariant test rejecting `ONLINE_VERIFIED` when run offline. |

---

## 3. Prioritized P0 Defect Backlog for Immediate Implementation

From the audit above, the following P0 defect areas require immediate architectural repair and regression verification:

1. **P0.1 — Exact Discrepancy & Reconciliation Validation (`REQ-DISC-01`, `REQ-SRC-01`):**
   - Eliminate loose discrepancy note matching; require exact numerical equality against `primary_reported_value` for approved adjustments.
   - Tie `source_register.json` reconciliation status directly to aggregate metric observations.
2. **P0.2 — Multi-Dimensional Verification Status Model (`REQ-PROV-01`):**
   - Implement explicit status fields: `document_identity_status`, `document_retrieval_status`, `period_match_status`, `metric_extraction_status`, `numeric_reconciliation_status`.
3. **P0.3 — Strict Commit-Only Clean Clone & Genuine Mutation Tests (`REQ-CLONE-01`, `REQ-MUT-01`):**
   - Refactor `build_source_observations_phase13.py` to accept explicit input file paths / fixtures.
   - Remove `git diff` patch application from clean clone testing to test committed state only.
   - Genuinely feed mutated canonical facts fixture to builder to prove mutation isolation.
4. **P0.4 — Authoritative Record-Derived Metadata & Release Gates (`REQ-META-01`):**
   - Enforce dynamic calculation of all count fields from evidence records.
   - Add uniqueness and total sum validations.
5. **P0.5 — Technical Analysis Chart Visibility & UI Automation (`REQ-UX-01`, `REQ-UX-02`):**
   - Redesign Technical Analysis page layout so the candlestick & volume chart is fully visible without clipping on 1280x900 viewports.
   - Expand `test_app_integration.py` to verify chart trace structure and interactive controls.
