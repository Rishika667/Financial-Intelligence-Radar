# Fundamentals Lens — Phase 18 Gap Register
## Independent Evidence Audit, Defect Remediation & Verification Ledger

**Product:** Fundamentals Lens — Evidence-First Financial Research Workbench  
**Creator Attribution:** Created by Rishika Dangayach  
**Repository:** `Rishika667/Financial-Intelligence-Radar`  
**Working Branch:** `pivot/fundamentals-lens-phase0`  
**Protected Main Baseline:** `9174cf94c06ac5af2b1ee82f36415e2e0381a120`  
**Audit Date:** 2026-10-19  

---

## 1. Defect & Gap Resolution Summary

| Gap ID | Priority | Category | Description | Phase 18 Remediation | Status |
| :--- | :---: | :--- | :--- | :--- | :---: |
| **GAP-P18-001** | **P0** | Evidence Integrity | Hardcoded `LIVE_VERIFIED_SAMPLE` allowlist in `scripts/build_source_review_inventory.py` stamped 20 records as `LIVE_SAMPLED_CONFIRMED` without actual network retrieval. | Completely removed hardcoded set. Derived `retrieval_check_status` and `verification_depth` dynamically from `source_check_report.json`. In canonical offline build, all 75 sources are honestly labeled `OFFLINE_RECORDED_EXTRACT` with explicit limitations. | **CLOSED** |
| **GAP-P18-002** | **P0** | Test Assurance | `tests/fundamentals_lens/test_phase16_source_assurance.py` asserted hardcoded `len(sampled) == 20` and `len(offline) == 55`. | Updated test to assert truthful, data-driven derivation. Verified that in offline build, 75/75 sources are offline-recorded with explicit disclosures and 0 false live claims. | **CLOSED** |
| **GAP-P18-003** | **P0** | Source Reconciliation | Maruti Suzuki FY 2024–25 canonical revenue (₹152,000 Cr) vs press release Net Sales (₹145,115.2 Cr) and FY 2025–26 Net Sales (₹174,370 Cr with 20.2% growth) was uncatalogued in the discrepancy ledger. | Reconciled Ind AS 115 Total Revenue from Operations (Net Sales ₹145,115.2 Cr + Other Operating Revenue ₹6,884.8 Cr = ₹152,000 Cr) and registered `DISC-017` in `discrepancy_ledger.json`. Updated observations and metadata. | **CLOSED** |
| **GAP-P18-004** | **P0** | Validation Framework | Lack of comprehensive adversarial test suite probing tampered timestamps, domain spoofing, fake online statuses, and duration bounds. | Authored `tests/fundamentals_lens/test_phase18_authenticity_audit.py` with 16 comprehensive tests verifying telemetry validation, URL/accession tampering rejection, duration guards, and arithmetic invariants. | **CLOSED** |
| **GAP-P18-005** | **P1** | Analyst UI & Transparency | Streamlit Data Integrity view did not expose source-level assurance inventory, retrieval modes, or explicit offline reproducibility disclosures. | Enhanced "Data Integrity & Methodology" page with interactive Source-Level Assurance & Retrieval Telemetry Breakdown, inventory table (75 sources), and clear offline verification transparency. | **CLOSED** |

---

## 2. Detailed Gap Analysis & Remediation Evidence

### GAP-P18-001: Elimination of Hardcoded Live-Verification Assignment
- **Root Cause:** Phase 16 introduced `scripts/build_source_review_inventory.py` containing a static dictionary `LIVE_VERIFIED_SAMPLE = { ("AAPL", 2021)... }`. This artificially stamped 20 sources as `LIVE_SAMPLED_CONFIRMED` and `FULL_DOCUMENT_AND_STATEMENT_LIVE_VERIFIED`, despite `source_check_report.json` recording all sources with `verification_mode: "OFFLINE"`.
- **Remediation:**
  - Removed `LIVE_VERIFIED_SAMPLE` dictionary.
  - Linked status evaluation directly to `source_check_report.json` telemetry (`verification_mode`, `check_status`, `document_identity_verified`).
  - Stamped sources with `is_live_sampled = True` ONLY when `verification_mode in ("ONLINE", "LIVE")` and `check_status in ("ONLINE_VERIFIED", "RETRIEVED_ONLINE_EDGAR", "RETRIEVED_ONLINE_BSE")`.
  - Stamped canonical offline sources with `is_live_sampled = False`, `retrieval_check_status: "OFFLINE_RECORDED_EXTRACT"`, and `remaining_source_limitations: "Validated against repository-tracked audited extract; live remote network re-fetch not executed during offline build."`.
- **Verification Evidence:** `scripts/build_source_review_inventory.py` outputs:
  `Generated source review inventory: 75 sources (0 live-sampled, 75 offline-recorded)`.

### GAP-P18-002: Hardened Source Assurance Test Suite
- **Root Cause:** `test_honest_sample_scoping_no_false_100_percent_live_claim` in `test_phase16_source_assurance.py` previously asserted `len(sampled) == 20` and `len(offline) == 55`, encoding the false hardcoded split into CI acceptance.
- **Remediation:**
  - Updated test to assert `len(offline) == 75` and `len(sampled) == 0` for canonical offline builds.
  - Verified that every offline record states explicit limitations and that no record falsely claims live verification.
- **Verification Evidence:** `pytest tests/fundamentals_lens/test_phase16_source_assurance.py` passed 4/4.

### GAP-P18-003: Maruti Suzuki Revenue Taxonomy Reconciliation (`DISC-017`)
- **Root Cause:** Maruti Suzuki FY25 canonical revenue of ₹152,000 Cr matched Total Revenue from Operations, but official results releases cited Net Sales of ₹1,451,152 million, and FY26 Net Sales of ₹1,743,695 million (20.2% growth). This line-item taxonomy nuance was not formally logged in the discrepancy ledger.
- **Remediation:**
  - Audited Maruti Suzuki Annual Integrated Reports for FY25 and FY26.
  - Verified Ind AS 115 breakdown: Net Sales (₹145,115.2 Cr) + Other Operating Revenue (₹6,884.8 Cr) = ₹152,000.0 Cr.
  - Added entry `DISC-017` to `datasets/fundamentals_lens/discrepancy_ledger.json` under `ACCOUNTING_PROXY_CLASSIFICATION`.
  - Updated `source_observations.json` and `dataset_metadata.json` (discrepancy count updated to 17).
- **Verification Evidence:** `validate_discrepancy_ledger` passed 17/17 resolved; `scripts/validate_fundamentals_data.py` passed 258/258 checks.

### GAP-P18-004: Adversarial Authenticity Audit Suite
- **Root Cause:** Previous test suites did not systematically test rejection of falsified live statuses, corrupted timestamps, or domain spoofing attacks.
- **Remediation:** Created `tests/fundamentals_lens/test_phase18_authenticity_audit.py` with 16 tests:
  - Telemetry validation: OFFLINE mode with online retrieval status rejected.
  - Identity validation: UNVERIFIED identity earning INDEPENDENTLY_RECONCILED rejected.
  - Timestamp validation: blank verification timestamp rejected.
  - URL validation: spoofed host (`sec.attacker.com` / unapproved Indian domains) rejected.
  - Accession format: malformed 20-digit pattern rejected.
  - Duration bounds: duration <300 days rejected.
  - Statement basis: standalone statements for consolidated facts rejected.
  - Arithmetic invariants: Free Cash Flow and Operating Margins strictly verified.
- **Verification Evidence:** `pytest tests/fundamentals_lens/test_phase18_authenticity_audit.py` passed 16/16 in 0.63s.

### GAP-P18-005: Analyst UI & Retrieval Transparency
- **Root Cause:** Streamlit Data Integrity view lacked source-level breakdown and did not disclose that offline execution validates against tracked audited extracts.
- **Remediation:** Added Source Assurance & Retrieval Telemetry Breakdown panel to "Data Integrity & Methodology" page, including total tracked sources (75), offline extracts (75), fresh live retrievals (0), approved discrepancies (17), and an interactive expander table displaying verification depth and limitations for every source.
- **Verification Evidence:** `test_streamlit_app_data_integrity_page` passed; CDP screenshot `05_data_integrity_desktop.png` captured (215,266 bytes).

---

## 3. Residual Limitations & Operational Truth

1. **Zero Runtime Network Dependency:** Fundamentals Lens runs 100% offline with zero operational cost, zero token dependencies, and no external API reliance.
2. **Honest Source Representation:** 75/75 sources are tracked offline audited extracts; zero records claim unverified live retrieval.
3. **No Unresolved Discrepancies:** All 17 documented accounting nuances are fully catalogued, verified, and resolved in the discrepancy ledger.
