# Fundamentals Lens — Phase 16 Test Evidence & Acceptance Log
## Multi-Dimensional Deterministic Validation and Test Suite Execution Record

**Product:** Fundamentals Lens — Evidence-First Financial Research Workbench  
**Creator & Lead Engineer:** **Rishika Dangayach**  
**Repository:** `Rishika667/Financial-Intelligence-Radar`  
**Working Branch:** `pivot/fundamentals-lens-phase0`  
**Protected Main Baseline:** `9174cf94c06ac5af2b1ee82f36415e2e0381a120`  
**Date:** October 19, 2026  

---

### Phase 16 Specialized Test Suites

#### 1. Retrieval & Telemetry Statuses (`test_phase16_retrieval_statuses.py`)
- **10/10 Tests Passed:**
  - `test_fiscal_calendar_mapping_covers_all_universe_companies`: Validates fiscal month mapping for all 15 universe companies.
  - `test_document_identity_verified_guard_wrong_company`: Asserts wrong-company filings are rejected.
  - `test_substantive_period_matching_fiscal_calendar_alignment`: Verifies fiscal calendar month matching.
  - `test_substantive_period_matching_duration_bounds`: Asserts non-annual durations (< 300 or > 400 days) are rejected.
  - `test_online_mode_requires_recorded_network_call_for_retrieved_status`: Proves unverified online calls emit `SOURCE_LINKED_ONLY`.
  - `test_online_mode_failure_demotes_tier`: Asserts failed HTTP calls demote tier.
  - `test_offline_mode_cannot_emit_retrieved_online`: Asserts offline mode emits `OFFLINE_AUDITED`.
  - `test_reconciliation_telemetry_validator_rejects_contradictions`: Invariant validation on contradictory telemetry.
  - `test_reconciliation_telemetry_validator_accepts_valid_records`: Confirms valid records pass validation.
  - `test_reconcile_metric_observation_end_to_end`: Full end-to-end telemetry pipeline check.

#### 2. Discrepancy Ledger & Mutation Assurance (`test_phase16_ledger_mutations.py`)
- **11/11 Tests Passed:**
  - Detects duplicate facts in canonical dataset.
  - Detects duplicate source observations.
  - Detects duplicate discrepancy ledger composite keys.
  - Detects mutated final values.
  - Detects mutated reported values.
  - Detects corrupted fiscal years.
  - Detects unapproved delta changes.
  - Detects corrupted FCF arithmetic ($FCF \neq OCF - Capex$).
  - Detects missing source observations.
  - Detects duplicate source references.
  - Detects metadata count discrepancies.

#### 3. Source-Level Assurance Inventory (`test_phase16_source_assurance.py`)
- **4/4 Tests Passed:**
  - Verifies full coverage across 75 company-periods (15 companies x 5 periods).
  - Confirms honest accounting: 20 periods live-sampled and 55 periods tracked offline.
  - Asserts all required inventory fields are populated (sample status, filing date, statement location, accession ID, verification depth).
  - Asserts all 15 universe companies are fully accounted for.

#### 4. Company Research Brief & Narrative Scenarios (`test_phase16_research_brief.py`)
- **8/8 Tests Passed:**
  - Structure test: Validates generation of all 7 explicit analytical sections.
  - Scenario 1: Revenue growth + falling margins (margin compression detection).
  - Scenario 2: Revenue contraction + improving cash (counter-cyclical cash resilience).
  - Scenario 3: Profits up + cash flow down (accrual divergence detection).
  - Scenario 4: Strong FCF + capex decline (capital harvesting vs reinvestment).
  - Scenario 5: Negative earnings / non-positive growth baseline handling.
  - Scenario 6: Missing periods / truncated history data limitation.
  - Scenario 7: Proxy metric suppression in peer contexts (TCS PBEI and Bajaj Auto EBITDA).

#### 5. Technical Analysis MVP Integrity (`test_phase16_technical_analysis.py`)
- **7/7 Tests Passed:**
  - Known mathematical fixtures: RSI neutral 50.0 for flat series, 100.0 for all gains, 0.0 for all losses, BB ddof=1 invariant.
  - Short history (<20 bars) graceful handling without crashing.
  - Duration guards: Strict suppression of 1-year returns and 52-week labels under 252 bars.
  - Benchmark alignment and duration-guarded relative returns.
  - Invalid prices and bounding invariants (negative prices, High < Low, negative volume).
  - Malformed upload diagnostics (missing headers, non-ISO dates, non-numeric values, duplicate dates).
  - Segregated export truthfulness (prominent synthetic demo warnings vs recorded market data).

#### 6. Clean-Clone Reproducibility (`test_clean_clone_reproducibility.py`)
- **6/6 Tests Passed:**
  - Tracked source inputs exist and valid.
  - Offline observations build executes deterministically without scratch cache.
  - Genuine source independence with fact and extract mutations.
  - CLI script execution.
  - Bit-for-bit determinism.
  - Isolated clean-clone rebuild with explicit SHA validation.
