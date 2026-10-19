# Fundamentals Lens — Phase 18 Test Evidence Report
## Executable Verification Evidence, Regression Logs & Visual Assurance

**Product:** Fundamentals Lens — Evidence-First Financial Research Workbench  
**Creator Attribution:** Created by Rishika Dangayach  
**Repository:** `Rishika667/Financial-Intelligence-Radar`  
**Working Branch:** `pivot/fundamentals-lens-phase0`  
**Phase 17 Baseline HEAD:** `339eeb0b63dc6e5dda780c58a37040597eee75b4`  
**Protected Main Baseline:** `9174cf94c06ac5af2b1ee82f36415e2e0381a120`  
**Audit Date:** 2026-10-19  

---

## 1. Executive Summary

This document provides independent, reproducible test evidence for Phase 18 of **Fundamentals Lens**. All tests, validation scripts, compilation checks, and visual QA captures were executed against the live working tree on branch `pivot/fundamentals-lens-phase0`.

### Key Verification Metrics
- **Pytest Suite:** **449 / 449 tests passed** in 21.52s (0 failures, 0 skipped, 0 warnings).
- **Data Integrity Validation Script:** **258 / 258 checks passed** across 15 companies and 75 periods (100% pass rate).
- **Adversarial Authenticity Audit Suite (`test_phase18_authenticity_audit.py`):** **16 / 16 tests passed**.
- **Clean Clone Reproducibility Suite (`test_clean_clone_reproducibility.py`):** **6 / 6 tests passed**.
- **App Integration Suite (`test_app_integration.py`):** **10 / 10 tests passed**.
- **Python Compilation (`python -m compileall`):** **0 errors** across `src/`, `scripts/`, `tests/`, and `fundamentals_lens_app.py`.
- **Git Diff Check (`git diff --check`):** **Clean** (0 whitespace/formatting errors).
- **CDP Screenshot Pipeline (`scripts/capture_screenshots.py`):** **7 / 7 screenshots captured** with full DOM, Plotly chart, and fold validation.

---

## 2. Command Execution Evidence

### A. Full Pytest Suite Execution
```
$ pytest
============================= test session starts =============================
platform win32 -- Python 3.11.9, pytest-9.1.1, pluggy-1.6.0
rootdir: C:\Users\HP\.gemini\antigravity\scratch\Financial-Intelligence-Radar
configfile: pyproject.toml
testpaths: tests
plugins: anyio-4.15.1
collected 449 items

tests\fundamentals_lens\test_app_integration.py ..........               [  2%]
tests\fundamentals_lens\test_clean_clone_reproducibility.py ......       [  3%]
tests\fundamentals_lens\test_coverage_reporting.py ...                   [  4%]
tests\fundamentals_lens\test_dataset_schema.py .....                     [  5%]
tests\fundamentals_lens\test_deeper_fundamentals.py ..........           [  7%]
tests\fundamentals_lens\test_exports.py ....                             [  8%]
tests\fundamentals_lens\test_insights_engine.py ...                      [  9%]
tests\fundamentals_lens\test_metrics_engine.py .....                     [ 10%]
tests\fundamentals_lens\test_peer_comparison.py ......                   [ 11%]
tests\fundamentals_lens\test_phase13_scenarios.py .................      [ 15%]
tests\fundamentals_lens\test_phase14_remediation.py .........            [ 17%]
tests\fundamentals_lens\test_phase15_ledger_validation.py .........      [ 19%]
tests\fundamentals_lens\test_phase15_population_integrity.py ......      [ 20%]
tests\fundamentals_lens\test_phase15_reconciliation.py ..........        [ 22%]
tests\fundamentals_lens\test_phase16_ledger_mutations.py ...........     [ 25%]
tests\fundamentals_lens\test_phase16_research_brief.py ........          [ 27%]
tests\fundamentals_lens\test_phase16_retrieval_statuses.py ..........    [ 29%]
tests\fundamentals_lens\test_phase16_source_assurance.py ....            [ 30%]
tests\fundamentals_lens\test_phase16_technical_analysis.py .......       [ 31%]
tests\fundamentals_lens\test_phase17_technical_engine.py ............... [ 35%]
....................                                                     [ 39%]
tests\fundamentals_lens\test_phase18_authenticity_audit.py ............. [ 42%]
...                                                                      [ 43%]
tests\fundamentals_lens\test_phase4_hardening.py ..........              [ 45%]
tests\fundamentals_lens\test_sec_audit.py ..............                 [ 48%]
tests\fundamentals_lens\test_source_provenance.py ....                   [ 49%]
tests\fundamentals_lens\test_technical_analysis.py ....................  [ 53%]
tests\fundamentals_lens\test_validator_adversarial.py .................. [ 57%]
...............................                                          [ 64%]
tests\fundamentals_lens\test_validator_framework.py ........             [ 66%]
tests\test_analyst_reviews_and_data_quality.py ......                    [ 67%]
tests\test_app.py .                                                      [ 68%]
tests\test_attention_queue.py .                                          [ 68%]
tests\test_comparison_engine.py .                                        [ 68%]
tests\test_core.py .....                                                 [ 69%]
tests\test_core_standalone.py .                                          [ 69%]
tests\test_cross_metric_synthesis.py .                                   [ 70%]
tests\test_currency_mismatch.py .                                        [ 70%]
tests\test_e2e_analytical.py .                                           [ 70%]
tests\test_events_extended.py ..........                                 [ 72%]
tests\test_evidence_chain.py ...                                         [ 73%]
tests\test_explanation_qa.py ......                                      [ 74%]
tests\test_fcf.py .                                                      [ 75%]
tests\test_final_closure.py ....................                         [ 79%]
tests\test_final_release.py .........                                    [ 81%]
tests\test_format_val.py .                                               [ 81%]
tests\test_golden_acceptance.py .....                                    [ 82%]
tests\test_idempotence.py .                                              [ 83%]
tests\test_ingestion_failure.py .                                        [ 83%]
tests\test_integration.py ........................                       [ 88%]
tests\test_invariants.py .....                                           [ 89%]
tests\test_legacy_migration.py .......                                   [ 91%]
tests\test_peer_context.py .                                             [ 91%]
tests\test_peer_coverage.py .                                            [ 91%]
tests\test_peers.py .........                                            [ 93%]
tests\test_persistence.py ..                                             [ 94%]
tests\test_pipeline.py .....                                             [ 95%]
tests\test_quality_precedence.py .                                       [ 95%]
tests\test_release_candidate.py .                                        [ 95%]
tests\test_research_mode.py ..                                           [ 96%]
tests\test_sec_golden.py .                                               [ 96%]
tests\test_sec_golden_path.py .                                          [ 96%]
tests\test_sec_multi_period_fixtures.py .....                            [ 97%]
tests\test_sector_signals.py .                                           [ 97%]
tests\test_smoke.py .                                                    [ 98%]
tests\test_streamlit_deployment_readiness.py .......                     [ 99%]
tests\test_synth_e2e_formatting.py .                                     [100%]

============================ 449 passed in 21.52s =============================
```

### B. Data Integrity Validation Script Execution
```
$ python scripts/validate_fundamentals_data.py
================================================================================
FUNDAMENTALS LENS: FINANCIAL DATA INTEGRITY VALIDATION (PHASE 8)
================================================================================
Total Companies Loaded:      15
Total Financial Periods:     75
Total Sources Listed:        75
Coverage Reports:            15
Evidence Register Records:   75
Total Primary Metrics:       375
Independently Reconciled:    375 primary metrics
Source-Linked Only:          0 primary metrics
Unverified / Discrepant:     0 primary metrics
Derived Free Cash Flow:      75 periods (DERIVED_VERIFIED)
--------------------------------------------------------------------------------
[All 15 companies pass 100% of validation gates]
[DATASET-METADATA] [PASS] Dataset Metadata & Artifact Consistency
[DISCREPANCY-LEDGER] [PASS] Discrepancy Ledger End-to-End Integrity (17 entries: 16 numerical, 1 identity)
[POPULATION-INTEGRITY] [PASS] Population Completeness & Cross-Artifact Integrity

================================================================================
VALIDATION SUMMARY & EVIDENCE AUDIT TRAIL
================================================================================
Total Companies Evaluated:               15
Total Checks Executed:                   258
Total Passed:                            258
Total Warnings:                          0
Total Failed:                            0
Total Unverified:                        0
Companies Passing 100% Gates:            15 / 15
--------------------------------------------------------------------------------
MULTI-DIMENSIONAL AUDIT BREAKDOWN:
1. Structural Integrity Passed:          45 / 45
2. Computational Checks Passed:          45 / 45
3. Source Lineage & Links Validated:     75 / 75
4. Coverage Integrity Passed:            15 / 15
5. Comparability & Definitions Passed:   30 / 30
6. Primary Metrics Reconciled:           375 / 375 (100.0%)
7. Sourced Periods with Discrepancy Log: 17 documented items
================================================================================
RESULT: ALL DATA INTEGRITY GATES PASSED (100% PASS RATE)
```

### C. Clean Clone Reproducibility Suite
```
$ pytest tests/fundamentals_lens/test_clean_clone_reproducibility.py
============================= test session starts =============================
collected 6 items

tests\fundamentals_lens\test_clean_clone_reproducibility.py ......       [100%]

============================== 6 passed in 4.17s ==============================
```

### D. Phase 18 Authenticity & Adversarial Suite
```
$ pytest tests/fundamentals_lens/test_phase18_authenticity_audit.py
============================= test session starts =============================
collected 16 items

tests\fundamentals_lens\test_phase18_authenticity_audit.py ................ [100%]

============================= 16 passed in 0.63s ==============================
```

### E. Python Bytecode Compilation & Git Diff Check
```
$ python -m compileall src scripts tests fundamentals_lens_app.py
Listing 'src'...
Listing 'scripts'...
Listing 'tests'...
Compiling 'fundamentals_lens_app.py'...
[0 compilation errors encountered]

$ git diff --check
[0 formatting or whitespace errors encountered]
```

---

## 3. Chrome DevTools Protocol (CDP) Screenshot Manifest

Executed via `python scripts/capture_screenshots.py` using headless Chrome with DOM landmark verification and Plotly dimension validation:

| Filename | Viewport | Dimensions | File Size | DOM Landmark Verified | Plotly Chart Verified |
| :--- | :---: | :---: | :---: | :---: | :---: |
| `01_overview_desktop.png` | Desktop | 1280x900 | 156,890 B | `[data-testid="stMetricValue"]` | 478x450 |
| `02_company_analysis_desktop.png` | Desktop | 1280x950 | 147,898 B | `.js-plotly-plot` | 810x450 |
| `03_peer_comparison_desktop.png` | Desktop | 1280x950 | 146,825 B | `.js-plotly-plot` | 810x450 |
| `04_technical_analysis_desktop.png` | Desktop | 1280x900 | 178,867 B | `.js-plotly-plot` | 810x490 |
| `05_data_integrity_desktop.png` | Desktop | 1280x950 | 215,266 B | `.stDataFrame` | N/A (Data Tables) |
| `06_company_analysis_mobile.png` | Mobile | 390x844 | 52,702 B | `.js-plotly-plot` | 358x450 |
| `07_technical_analysis_mobile.png` | Mobile | 390x844 | 58,961 B | `.js-plotly-plot` | 358x490 |

---

## 4. Invariant Protection Certification

1. **Creator Attribution Invariant:**
   - "Created by Rishika Dangayach" is explicitly preserved across all page headers, footers, downloadable CSV/JSON exports, and documentation files.
2. **Zero-Cost Constraint:**
   - Verified zero external paid APIs, zero third-party live data feeds, zero mandatory API keys, and 100% offline deterministic execution.
3. **Protected Main Baseline Invariant:**
   - Commit baseline `9174cf94c06ac5af2b1ee82f36415e2e0381a120` remains completely untouched.
   - All commits and work performed exclusively on `pivot/fundamentals-lens-phase0`.
