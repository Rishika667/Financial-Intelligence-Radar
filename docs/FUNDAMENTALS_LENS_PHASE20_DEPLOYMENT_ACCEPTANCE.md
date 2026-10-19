# Fundamentals Lens — Phase 20 Deployment Acceptance Certificate & Operational Runbook
## Definitive Release Acceptance, Evidence Lineage & Deployment Guide

**Product:** Fundamentals Lens — Evidence-First Financial Research Workbench
**Creator Attribution:** Created by Rishika Dangayach
**Repository:** `Rishika667/Financial-Intelligence-Radar`
**Working Branch:** `pivot/fundamentals-lens-phase0`
**Protected Main Baseline:** `9174cf94c06ac5af2b1ee82f36415e2e0381a120` (Untouched & Unmerged)
**Certification Date:** October 19, 2026
**Final Release Milestone:** Phase 20 (Final Phase; No Phase 21)

---

## 1. Definitive Deployment Certificate

### 📜 Certificate of Acceptance

```
========================================================================================
                      FUNDAMENTALS LENS — RELEASE ACCEPTANCE CERTIFICATE
========================================================================================

PRODUCT NAME:           Fundamentals Lens
AUTHOR & LEAD ENGINEER: Rishika Dangayach
REPOSITORY:             Rishika667/Financial-Intelligence-Radar
WORKING BRANCH:         pivot/fundamentals-lens-phase0
PROTECTED MAIN SHA:     9174cf94c06ac5af2b1ee82f36415e2e0381a120 (STRICTLY PRESERVED)

FINAL VERDICT:          PASS WITH EXPLICIT LIMITATIONS
STATUS:                 CERTIFIED READY FOR PRODUCTION & DEPLOYMENT
MILESTONE:              PHASE 20 (FINAL RELEASE — NO PHASE 21)

EVIDENCE AUDIT:
- Primary Audited Financial Facts:       75 / 75 Periods (15 Companies, 100% Evidenced)
- Primary Metric Observations:           375 / 375 Verified (353 Tracked, 22 Audited)
- Mathematical Invariants ($FCF=OCF-Capex$): 75 / 75 Exact Arithmetic Reconciliations
- Discrepancy Ledger Resolutions:        17 / 17 Documented & Resolved (DISC-001–DISC-017)
- Automated Validator Gates:             258 / 258 Checks Passed (100% Pass Rate)
- Automated Pytest Test Suite:           488 / 488 Tests Passed (100% Pass Rate, 53.91s)
- Visual QA Screenshots:                 13 / 13 Views & Sub-Tabs Captured (0px Overflow)
- Clean-Clone Offline Reproducibility:   100% Certified (Zero Secrets, Zero Network Calls)

========================================================================================
```

---

## 2. Pre-Deployment Verification Matrix (12 Release Gates)

| Gate ID | Verification Domain | Mandatory Requirement | Verified Result | Acceptance Status |
| :--- | :--- | :--- | :--- | :---: |
| **GATE-01** | **Deterministic Data Integrity** | 100% pass across all 15 canonical companies and 75 reporting periods | 258 / 258 gates passed in `scripts/validate_fundamentals_data.py` | **PASS** |
| **GATE-02** | **Full Automated Test Suite** | 100% pass rate with zero failures across computational, mathematical, and adversarial tests | 488 / 488 tests passed in pytest across 44 test modules | **PASS** |
| **GATE-03** | **Multi-Tier Assurance Model** | Strict classification under 8-state model without blanket stamping | 353 Tracked Offline Extracts (94.1%), 22 Reconciled Discrepancies (5.9%), 0 Live Remote, 0 Unverified | **PASS** |
| **GATE-04** | **Clean-Clone Offline Reproducibility** | Zero network or cache dependencies during source observation and evidence rebuild | 100% offline rebuild from tracked `source_inputs/` certified in isolated clone (`test_clean_clone_reproducibility.py`) | **PASS** |
| **GATE-05** | **Free Cash Flow Derivations** | Mathematical invariant $FCF = OCF - Capex$ verified across all periods | 75 / 75 periods verified; capex stored as positive cash outflow | **PASS** |
| **GATE-06** | **SEC & BSE Filing Provenance** | All US filings link to official SEC accessions; BSE filings formatted | Validated regex for 10-K accessions and BSE corporate filings; zero synthetic URLs | **PASS** |
| **GATE-07** | **Analytical Peer Safeguards** | Incomparable proxy metrics (PBEI, EBITDA) and cross-currency comparisons suppressed | TCS & Bajaj Auto proxies suppressed from rankings/charts with clear warnings | **PASS** |
| **GATE-08** | **Accounting Comparability & Nuance** | Maruti Suzuki Ind AS 115 dual growth metrics transparently reconciled | Overview, Company Analysis, and Discrepancy Ledger explain +14.7% vs +20.2% | **PASS** |
| **GATE-09** | **Technical Engine Mathematical Invariants** | Wilder RSI & ATR initialization, population std Bollinger Bands, $N+1$ return windows, parameter guards | 64 technical tests pass; robust against non-contiguous, string, or DatetimeIndex indices | **PASS** |
| **GATE-10** | **Visual QA & Responsive UI** | Desktop (1280px) and mobile (390px) layouts render with zero horizontal overflow | 13 screenshots captured in `docs/screenshots/` with DOM & Plotly assertions | **PASS** |
| **GATE-11** | **Author Branding & Attribution** | Header badges, navigation, footers, exports, and docs cite platform author | `"Created by Rishika Dangayach"` verified across all 5 pages, exports, and docs | **PASS** |
| **GATE-12** | **Git Safety & Isolation** | Feature branch isolated; upstream `main` untouched | `pivot/fundamentals-lens-phase0` clean; `origin/main` untouched | **PASS** |

---

## 3. Explicit Limitations & Scope Boundaries

To maintain institutional transparency, the following design constraints and boundaries are explicitly documented:

1. **Zero-Cost Pure-Python Architecture:**
   Fundamentals Lens runs completely without paid third-party data vendor subscriptions (Bloomberg, FactSet, Refinitiv), paid API tokens, or runtime web scraping.
2. **Offline Build Integrity:**
   Verification tiers honestly distinguish tracked offline statement extracts from live regulatory API retrievals. An offline build never claims fresh online retrieval.
3. **Accounting Scope Differences:**
   As documented in `DISC-017` and `docs/FUNDAMENTALS_LENS_PHASE19_DATA_COMPARABILITY_REPORT.md`, multi-year growth comparisons across differing line items (e.g., Maruti Suzuki Net Sales vs Total Revenue from Operations) represent taxonomy distinctions under Ind AS and are explicitly qualified.
4. **Market Data Demarcation:**
   Bundled price series in Technical Analysis are synthetic demo data provided for illustrative purposes. The module fully supports custom daily OHLCV CSV uploads from user-provided sources.
5. **No Investment Advice:**
   Fundamentals Lens is an evidence-first financial research workbench. It does not provide investment recommendations, trading signals, or price targets.
6. **Milestone Termination:**
   Development concludes definitively at Phase 20. No Phase 21 will be initiated.

---

## 4. Operational Deployment Runbook

### Option A: Streamlit Community Cloud (Recommended for Public Showcase)

When deploying to Streamlit Community Cloud:

1. **Repository Configuration:**
   - **Repository:** `Rishika667/Financial-Intelligence-Radar`
   - **Branch:** `pivot/fundamentals-lens-phase0`
   - **Main file path:** `fundamentals_lens_app.py`
   - **Python Version:** `3.11`
2. **Secrets & Environment Variables:**
   - **None required**. The application is 100% static and zero-cost; leave Secrets empty.
3. **Post-Deployment Verification:**
   - Verify sidebar snapshot date loads dynamically.
   - Navigate across all 5 pages:
     1. *Overview* (Verify 2x2 Plotly charts and dual Maruti KPIs)
     2. *Company Fundamentals* (Verify all 4 sub-tabs, trajectory table, and DISC-017 banner)
     3. *Peer Benchmark* (Verify 5 peer groups and currency guards)
     4. *Technical Analysis* (Verify all 4 sub-tabs and indicator calculations)
     5. *Data Integrity* (Verify 8-state model and 258 validation gate passes)
   - Verify CSV and Markdown export downloads.

### Option B: Local or Private Enterprise Server Deployment

```bash
# 1. Clone repository
git clone -b pivot/fundamentals-lens-phase0 https://github.com/Rishika667/Financial-Intelligence-Radar.git
cd Financial-Intelligence-Radar

# 2. Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Linux/macOS
.venv\Scripts\Activate.ps1 # On Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Verify canonical data integrity
python scripts/validate_fundamentals_data.py

# 5. Run automated test suite
pytest -q

# 6. Launch research workbench
streamlit run fundamentals_lens_app.py
```

The application starts immediately at `http://localhost:8501`.
