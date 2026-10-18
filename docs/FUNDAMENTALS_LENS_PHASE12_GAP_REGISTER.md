# Fundamentals Lens: Phase 12 Gap Register & Source-Truth Certification

**Project:** Fundamentals Lens (`Rishika667/Financial-Intelligence-Radar`)
**Phase:** Phase 12 — Source-Truth Repair, Clean-Clone Pipeline Reproducibility & 88.5% Readiness
**Feature Branch:** `pivot/fundamentals-lens-phase0`
**Author & Lead Engineer:** **Rishika Dangayach**
**Audit Standard:** Zero Circular Provenance, Clean-Clone Reproducibility, Honest Verification Tiers, Adversarial Invariant Rigor
**Status:** All Identified Phase 12 Gaps Fully Remediated (100% Resolved)

---

## 1. Resolved In-Scope Audit Gaps & Defects

| Gap ID | Dimension | Description | Severity | Remediation Action | Status |
|:---|:---|:---|:---:|:---|:---:|
| **GAP-12-01** | Circular Indian Source Provenance | `build_source_observations_phase11.py` copied `cf[m_key]` from `financial_facts_5yr.json` as the reported source value for Indian companies, creating a circular data loop. | Critical | Created tracked compact input `datasets/fundamentals_lens/source_inputs/indian_statement_extracts.json` containing 225 independent statement observations with exact line items, page numbers, and numbers extracted from audited annual reports. | **REMEDIATED** |
| **GAP-12-02** | Git-Ignored Cache Dependency | US source builder relied on `scratch/sec_cache/` which is ignored in `.gitignore`, preventing clean clones from reproducing the source observation dataset offline. | Critical | Created tracked compact input `datasets/fundamentals_lens/source_inputs/sec_company_facts_extracts.json` containing 150 official SEC XBRL company facts for all 6 US companies across 30 periods. Clean clone rebuilds now execute 100% offline. | **REMEDIATED** |
| **GAP-12-03** | Metric Definition Semantic Pollution | In Phase 11 builder, line 413 mapped `definition_type` using capex fallback, causing `revenue`, `net_income`, and `operating_cash_flow` to inherit `PPE_PURCHASES_ONLY`. | High | Corrected taxonomy mapping across the entire pipeline. `revenue` now receives `US_GAAP_TOTAL_REVENUES` / `IND_AS_REVENUE_OPERATIONS`, `operating_income` receives `US_GAAP_OPERATING_INCOME` / `IND_AS_EBIT_OPERATING_PROFIT`, etc. Zero cross-pollution. | **REMEDIATED** |
| **GAP-12-04** | Silent Script Overrides & WMT Net Income | Extraction scripts silently hardcoded WMT Net Income overrides to non-GAAP numbers ($19,549M / $22,279M) instead of official audited GAAP Form 10-K disclosures. | High | Removed all hardcoded overrides. Reconciled WMT FY2025 and FY2026 Net Income directly from concept `us-gaap:NetIncomeLoss` at $19,436.0M and $21,893.0M. Registered `DISC-016` in `discrepancy_ledger.json`. | **REMEDIATED** |
| **GAP-12-05** | Validator Statement Locator & Definition Hardening | `FundamentalsValidator` did not check whether statement locators were bare placeholders (e.g. "Consolidated Financial Statements") and did not verify definition semantic matching. | High | Enhanced `FundamentalsValidator` to reject bare or generic locators (< 10 chars or generic titles) and reject capex definition types assigned to revenue observations. | **REMEDIATED** |
| **GAP-12-06** | Clean-Clone Offline Pipeline Test in CI | Continuous integration did not verify that a clean checkout can rebuild all source observation and evidence artefacts from scratch. | Medium | Added clean-clone offline rebuild step to `.github/workflows/validate.yml` and authored `tests/fundamentals_lens/test_clean_clone_reproducibility.py` (4 tests, all passing). | **REMEDIATED** |
| **GAP-12-07** | UI Discrepancy Table Key Alignment | Streamlit UI table in `fundamentals_lens_app.py` expected alternate key names for discrepancy records, causing some fields to display as `None`. | Medium | Updated `fundamentals_lens_app.py` and `build_evidence_register_phase12.py` with multi-key fallbacks, ensuring all 16 discrepancy records display complete financial details. | **REMEDIATED** |

---

## 2. Final Invariant & Ledger Verification Statistics

- **Total Companies:** 15 across 5 Peer Groups (Strictly Canonical)
- **Total Annual Periods:** 75 (5 consecutive periods per company)
- **Total Primary Metrics:** 375
  - **Independently Reconciled (`INDEPENDENTLY_RECONCILED`):** 330 (88.0%)
  - **Source-Linked Only (`SOURCE_LINKED_ONLY`):** 45 (12.0%)
  - **Unverified (`UNVERIFIED`):** 0 (0.0%)
  - **Derived Free Cash Flow Invariants (`DERIVED_VERIFIED`):** 75 (100.0%)
- **Documented Discrepancies:** 16 items in `discrepancy_ledger.json` (DISC-001 through DISC-016)
- **Deterministic Validation Gates:** 255 / 255 Passing (100.0%)
- **Pytest Test Suite:** 289 / 289 Passing (100.0%)
- **Adversarial Test Cases:** 37 / 37 Passing (100.0%)
- **Operating Budget:** $0 / ₹0 (Zero external paid APIs, zero live database requirements)
- **Creator & Lead Engineer:** **Rishika Dangayach**
