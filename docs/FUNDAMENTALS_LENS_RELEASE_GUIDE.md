# Fundamentals Lens — Release & Operational Guide
## Production Deployment & Operational Runbook (Phase 20 Final Release)

**Product:** Fundamentals Lens — Evidence-First Financial Research Workbench
**Repository:** `Rishika667/Financial-Intelligence-Radar`
**Entry Point:** `fundamentals_lens_app.py`
**Architecture:** Zero-Cost, Pure-Python Static Financial Research Application
**Target Operating Budget:** ₹0 ($0) — No paid APIs, no databases, no external credentials required
**Creator Attribution:** Created by Rishika Dangayach
**Filing Verification Cutoff:** October 19, 2026
**Final Release Milestone:** Phase 20 (Final Milestone; No Phase 21)

---

## 1. Product Overview

**Fundamentals Lens** is an evidence-first financial research application created by **Rishika Dangayach** for fundamental equity analysts, finance students, and portfolio evaluators. It enables transparent five-year financial performance exploration, rule-based inquiry ("What changed, why it matters, and what to investigate"), guarded peer comparisons, pure-Python technical analysis, and one-click research exports.

Unlike black-box financial platforms or live market-data feeds, Fundamentals Lens is built on a simple foundation:
- **100% Primary Sources:** Every financial fact traces to official audited annual statements filed with the US SEC (Form 10-K) or Indian stock exchanges BSE/NSE (audited consolidated annual reports).
- **Multi-Tier Evidence Assurance:** Enforces an 8-state assurance taxonomy distinguishing 353 Tracked Offline Extracts from 22 Independently Reconciled Audited Discrepancies.
- **Zero Coercion Policy:** Missing or unavailable disclosures are preserved as `None` / `null` rather than silently coerced into synthetic zeroes (`0.0`).
- **Normalized Currencies & Magnvariants:** US companies are normalized in $ Millions ($M); Indian companies in ₹ Crores (₹ Cr). Capital expenditures are uniformly stored as positive cash outflows, making Free Cash Flow deterministically $OCF - Capex$.

---

## 2. Quick Start & Local Execution

### Prerequisites
- Python 3.10+ (tested on Python 3.11.9)
- Git

### Running Locally (or in GitHub Codespaces)
```bash
# 1. Clone repository & navigate to directory
git clone -b pivot/fundamentals-lens-phase0 https://github.com/Rishika667/Financial-Intelligence-Radar.git
cd Financial-Intelligence-Radar

# 2. Activate virtual environment (if using one)
# On Windows:
.venv\Scripts\Activate.ps1
# On Linux/macOS:
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Launch Fundamentals Lens
streamlit run fundamentals_lens_app.py
```
The application will launch immediately at `http://localhost:8501`. No API keys, database initialization, or login credentials are required.

---

## 3. Five-Page User Journey

### Page 1 — Overview
- **Landing Dashboard:** Introduces product purpose and highlights the ₹0 operating architecture.
- **2x2 Multi-Year Financial Trajectory:**
  1. *Revenue Trajectory:* 5-year bar chart with hovertemplate and Maruti Suzuki DISC-017 like-for-like callout (+14.7% reported vs +20.2% like-for-like).
  2. *Operating Profitability:* Dedicated scale for Operating Income avoiding visual compression.
  3. *Margin Dynamics (%):* Operating Margin % and Net Margin % lines with percentage axis.
  4. *Cash Flow Generation & Reinvestment:* OCF vs Capex bars with FCF markers and outflow convention notice.
- **Quick Explorer:** Top-level KPI cards and a 3-item rule-based narrative insights preview.

### Page 2 — Company Analysis (4-Tab Layout)
- **Tab 1: Trajectory:** 6 core KPI cards (including dual CAGR and YoY metrics for Maruti Suzuki), scope caveat banner, full multi-year financial statements table, and annotated columns.
- **Tab 2: Profitability & Margins:** Interactive margin shift lines and operating leverage metrics.
- **Tab 3: Cash Flow Dynamics:** Cash conversion ratio, cumulative reinvestment rate, and FCF reconciliation.
- **Tab 4: Evidence & Provenance:** Master primary source drawer linking each period to SEC EDGAR accessions and BSE/NSE annual reports.
- **Rule-Based Research Commentary:** "What changed, why it matters, and what to investigate" across 5 analytical dimensions.
- **Export Center:** Downloadable company CSV and comprehensive 7-section Markdown research brief.

### Page 3 — Peer Comparison
- **Intuitive Peer Group Selector:** Switch between Global Tech, Indian IT, Indian Consumer Brands, Indian Auto, and US Retailers.
- **Structural Caveats & Comparability Banner:** Explains business model nuances:
  - *Indian Auto:* Maruti Suzuki (passenger cars) vs. Bajaj Auto / Hero MotoCorp (2/3-wheelers).
  - *US Retail:* Costco (membership warehouse with negative working capital) vs. Walmart (omni-channel supercenter) vs. Target (discretionary).
  - *Global Tech:* Hyperscaler cloud capex vs. consumer hardware/services; non-aligned fiscal year-ends.
- **Currency & Proxy Safeguards:** Strict separation ensuring USD is never mixed with INR, and proxy metrics (TCS PBEI, Bajaj Auto EBITDA) are suppressed from charts.
- **Export:** Downloadable peer group comparison CSV.

### Page 4 — Technical Analysis (Pure-Python Engine)
- **Zero External Dependencies:** Built without `ta-lib` or heavy technical analysis packages.
- **4 Tab Layout:**
  - *Tab 1: Overview & Trend:* Interactive daily candlestick chart, volume bars, and SMA(20/50/200).
  - *Tab 2: Momentum & Volatility:* Wilder RSI(14) with initial SMA seeding, MACD(12,26,9) with signal line & histogram, Bollinger Bands (population std, `ddof=0`), and ATR(14).
  - *Tab 3: Benchmark Comparison:* Relative return comparison against SPY or Nifty 50 with normalized date windows.
  - *Tab 4: Technical Exports:* Downloadable indicator CSV and technical summary Markdown brief.
- **Custom CSV Upload:** Analysts can upload custom daily OHLCV CSVs with automatic validation and calendar coverage guards.

### Page 5 — Data Integrity & Methodology
- **Philosophy:** Core principles of zero-cost operation, primary provenance, non-coercion, and consolidated reporting.
- **Multi-Tier Evidence Breakdown:** Real-time metrics for 353 Tracked Offline Extracts (94.1%), 22 Independently Reconciled Audited Discrepancies (5.9%), 0 Live Retrievals, and 0 Unverified.
- **Coverage Audit Table:** Target reporting horizon status across all 15 companies.
- **Discrepancy Ledger:** Full audit trail for all 17 documented accounting items (`DISC-001` through `DISC-017`).
- **Interactive Validation Dashboard:** Live execution of `FundamentalsValidator` (258/258 checks passing at 100% pass rate).

---

## 4. Deploying to Streamlit Community Cloud

Deploying Fundamentals Lens to Streamlit Community Cloud is 100% free and requires zero external database or secret configuration:

1. Push your branch to GitHub (`Rishika667/Financial-Intelligence-Radar`).
2. Log in to [Streamlit Community Cloud](https://share.streamlit.io/).
3. Click **"New App"** and select:
   - **Repository:** `Rishika667/Financial-Intelligence-Radar`
   - **Branch:** `pivot/fundamentals-lens-phase0`
   - **Main file path:** `fundamentals_lens_app.py`
4. Click **"Deploy!"**.
5. Within 60 seconds, the app will build and serve traffic globally. Visitors do not need to configure anything.

---

## 5. Verification & Testing Instructions

To verify data integrity and software quality:

```bash
# 1. Run the Deterministic Data Integrity CLI Validator (258 checks)
python scripts/validate_fundamentals_data.py

# 2. Run the Full Test Suite (488 tests)
pytest -v

# 3. Run the Clean-Clone Reproducibility Tests
pytest tests/fundamentals_lens/test_clean_clone_reproducibility.py -v

# 4. Run the Visual QA Screenshot Capture Pipeline (13 screenshots)
python scripts/capture_screenshots.py
```

All 488 tests run offline and pass deterministically.
