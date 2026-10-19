# Fundamentals Lens — Phase 19 Gap Register
## Analytical Integrity, Evidence-State Correction, Financial Comparability & Overview Visualization Redesign

**Product:** Fundamentals Lens — Evidence-First Financial Research Workbench  
**Creator Attribution:** Created by Rishika Dangayach  
**Repository:** `Rishika667/Financial-Intelligence-Radar`  
**Working Branch:** `pivot/fundamentals-lens-phase0`  
**Protected Main Baseline:** `9174cf94c06ac5af2b1ee82f36415e2e0381a120`  
**Audit Date:** 2026-10-19  

---

## 1. Defect & Gap Resolution Summary

| Gap ID | Priority | Category | Description | Phase 19 Remediation | Status |
| :--- | :---: | :--- | :--- | :--- | :---: |
| **GAP-P19-001** | **P0** | Evidence Integrity | Blanket assignment of `INDEPENDENTLY_RECONCILED` to all 375 primary metrics solely because offline extracts matched canonical facts. | Formulated 8-state `AssuranceState` model. Separated 353 Tracked Offline Extracts (94.1%) from 22 Independently Reconciled Audited Discrepancies (5.9%), 0 Live Retrievals, and 0 Unverified. Authored `test_phase19_evidence_assurance.py` (12 tests). | **CLOSED** |
| **GAP-P19-002** | **P0** | Comparability | Maruti Suzuki revenue comparison had potential for misleading CAGR due to differing line-item definitions (Net Sales vs Total Revenue from Operations). | Updated `DISC-017` with `disposition: "TREND_ANALYSIS_QUALIFIED"` and explicit like-for-like YoY guidance (+20.2% Net Sales vs +14.72% nominal). Embedded into `insights.py`, Overview chart callout, and created `FUNDAMENTALS_LENS_PHASE19_DATA_COMPARABILITY_REPORT.md`. | **CLOSED** |
| **GAP-P19-003** | **P0** | Technical Math | Wilder RSI & ATR initialization lacked initial SMA seed; Bollinger Bands used sample std (`ddof=1`); return windows lacked $N+1$ observation guard; genuine 0.0 values masked as missing. | Implemented Wilder SMA seeding; standardized on $N+1$ return windows; aligned Bollinger Bands to population std (`ddof=0`); preserved genuine 0.0 values in cards; guarded benchmark date normalization. Authored `test_phase19_technical_math.py` (9 tests). | **CLOSED** |
| **GAP-P19-004** | **P1** | UI / Visualization | Overview page suffered from card proliferation and a single shared-axis Revenue/Operating Income chart that compressed operating income scale. | Replaced single chart with responsive 2x2 dashboard: dedicated `plot_revenue_trajectory`, dedicated `plot_operating_income_trajectory`, `plot_margins`, and `plot_cash_generation_reinvestment`. Streamlined snapshot KPIs and added 3-item insights preview. Authored `test_phase19_overview_charts.py` (2 tests). | **CLOSED** |
| **GAP-P19-005** | **P1** | Exports & Reports | Research Brief Section 7 and Streamlit Data Integrity tab did not clearly explain the multi-state assurance model or separate tracked extracts from audited discrepancies. | Updated Research Brief Section 7.2 with explicit assurance taxonomy note and updated Streamlit Data Integrity view with the 8-state assurance breakdown and truthful metric counters. | **CLOSED** |

---

## 2. Detailed Gap Analysis & Technical Remediation

### GAP-P19-001: Distinct Multi-Tier Evidence Assurance Model
- **Root Cause:** Prior phases treated "Offline extract matches canonical fact" as equivalent to an independent primary-source statement audit, stamping all 375 metrics as `INDEPENDENTLY_RECONCILED`.
- **Technical Fix:**
  - Added `AssuranceState` enum in `src/fundamentals_lens/models.py` with 8 distinct states.
  - Added `TRACKED_OFFLINE_EXTRACT` to `VerificationTier` and updated `normalize_verification_tier`.
  - In `src/fundamentals_lens/reconciliation.py`: assigned `INDEPENDENTLY_RECONCILED` (`APPROVED_ADJUSTMENT_RESOLVED`) only to approved discrepancy resolutions, verified live regulatory retrievals (`LIVE_RETRIEVAL_SUCCEEDED`), or hashed document snapshots. Assigned `TRACKED_OFFLINE_EXTRACT` (`OFFLINE_EXTRACT_RECORDED`) to offline extracts matching canonical facts.
  - Updated `validator.py`, `scripts/build_source_observations_phase13.py`, and `scripts/build_evidence_register_phase13.py`.
- **Evidence:** Rebuilt evidence pipeline results:
  - Total primary metrics: 375
  - Tracked offline extracts: 353 (94.1%)
  - Independently reconciled (Audited discrepancies): 22 (5.9%)
  - Live remote retrievals: 0 (offline build transparency)
  - Unverified / Discrepant: 0
  - Passed 12/12 tests in `test_phase19_evidence_assurance.py`.

### GAP-P19-002: Maruti Suzuki & 15-Company Comparability
- **Root Cause:** Maruti Suzuki FY25 revenue (₹152,000 Cr) represents Consolidated Total Revenue from Operations (Ind AS 115), while FY26 revenue (₹174,370 Cr) represents Net Sales. Directly dividing the two gives +14.72%, whereas like-for-like Net Sales growth is +20.2% (FY26 ₹174,370 Cr vs FY25 ₹145,115.2 Cr).
- **Technical Fix:**
  - Updated `datasets/fundamentals_lens/discrepancy_ledger.json` (`DISC-017`):
    `"disposition": "TREND_ANALYSIS_QUALIFIED"` with explicit instructions for analysts.
  - Updated `src/fundamentals_lens/insights.py` to highlight like-for-like Net Sales growth and note CAGR qualification.
  - Added subtitle callout to `plot_revenue_trajectory` in `fundamentals_lens_app.py`.
  - Authored `docs/FUNDAMENTALS_LENS_PHASE19_DATA_COMPARABILITY_REPORT.md` auditing all 15 companies across accounting standards, revenue definitions, operating income proxies (EBIT vs PBEI), capex, and cash flows.
- **Evidence:** `test_maruti_suzuki_analytical_guidance_present_in_insights_and_discrepancy` passed.

### GAP-P19-003: Technical Analysis Mathematical Correctness
- **Root Cause:**
  - Wilder's Smoothing for RSI and ATR was initialized with the first single value rather than an initial 14-period SMA seed.
  - Bollinger Bands calculated sample standard deviation (`ddof=1`), while John Bollinger's specification and documentation prescribe population standard deviation (`ddof=0`).
  - Period return windows did not require $N+1$ observations for an exact $N$-interval return.
  - Technical summary cards displayed "Insufficient data" when measured volatility or max drawdown was genuine `0.0%`.
- **Technical Fix:**
  - In `src/fundamentals_lens/technical.py`: initialized Wilder RSI & ATR by computing the mean of the first 14 values, followed by `(prior * 13 + current) / 14`.
  - Changed Bollinger Band calculation to `clean['Close'].rolling(period).std(ddof=0)`.
  - Standardized on $N+1$ daily bars required for an exact $N$-period return.
  - In `fundamentals_lens_app.py`: checked `val is not None and not np.isnan(val)` instead of truthiness, preserving genuine `0.0%`.
  - Updated `docs/TECHNICAL_ANALYSIS_METHODOLOGY.md`.
- **Evidence:** 64/64 technical tests passed (`test_phase17_technical_engine.py` 35, `test_technical_analysis.py` 20, `test_phase19_technical_math.py` 9).

### GAP-P19-004: Overview Page Visualization Redesign
- **Root Cause:** Single shared-axis chart for Revenue and Operating Income compressed operating income to a flat bar and lacked margin or cash generation visibility on the landing page.
- **Technical Fix:**
  - Designed and implemented 4 dedicated Plotly chart functions:
    1. `plot_revenue_trajectory`: 5-year bar chart with hovertemplate and Maruti callout.
    2. `plot_operating_income_trajectory`: dedicated scale for operating income.
    3. `plot_margins`: Operating Margin % and Net Margin % lines+markers with `%` tick suffix.
    4. `plot_cash_generation_reinvestment`: OCF and Capex bars with FCF line/markers and subtitle formula.
  - Laid out charts in a 2x2 responsive grid on the Overview page.
  - Replaced crowded card layout with 4 compact snapshot KPIs and an analytical narrative preview.
- **Evidence:** Tested with `test_phase19_overview_charts.py` (2 passed) and verified via CDP desktop screenshot `01_overview_desktop.png`.

---

## 3. Regression & Acceptance Verification

- **Full Pytest Suite:** 472 passed in 27.63s (zero failures, zero warnings).
- **Automated Data Validation:** 258 passed / 0 failed in `scripts/validate_fundamentals_data.py`.
- **Clean-Clone Reproducibility:** 6/6 scenarios passed without cache or network dependencies.
- **CDP Screenshot QA:** 7/7 desktop and mobile viewports verified with DOM landmarks and non-zero chart dimensions.
