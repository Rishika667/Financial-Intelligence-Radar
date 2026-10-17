# Fundamentals Lens — Release & Operational Guide

**Product:** Fundamentals Lens  
**Repository:** `Rishika667/Financial-Intelligence-Radar`  
**Entry Point:** `fundamentals_lens_app.py`  
**Architecture:** Zero-Cost, Pure-Python Static Financial Research Application  
**Target Operating Budget:** ₹0 ($0) — No paid APIs, no databases, no external credentials required  
**Filing Verification Cutoff:** October 18, 2026  

---

## 1. Product Overview

**Fundamentals Lens** is an evidence-first financial research application designed for fundamental equity analysts, finance students, and portfolio evaluators. It enables transparent five-year financial performance exploration, rule-based inquiry ("What changed, why it matters, and what to investigate"), guarded peer comparisons, and one-click research exports.

Unlike black-box financial platforms or live market-data feeds, Fundamentals Lens is built on a simple foundation:
- **100% Primary Sources:** Every number traces to official audited annual statements filed with the US SEC (10-K) or Indian stock exchanges BSE/NSE (audited consolidated annual reports).
- **Zero Coercion Policy:** Missing or unavailable disclosures are preserved as `None` / `null` rather than silently coerced into synthetic zeroes (`0.0`).
- **Normalized Currencies & Magnitudes:** US companies are normalized in $ Millions ($M); Indian companies in ₹ Crores (₹ Cr). Capital expenditures are uniformly stored as positive cash outflows, making Free Cash Flow deterministically $OCF - Capex$.

---

## 2. Quick Start & Local Execution

### Prerequisites
- Python 3.10+ (tested on Python 3.11.9)
- Git

### Running Locally (or in GitHub Codespaces)
```bash
# 1. Clone repository & navigate to directory
git clone https://github.com/Rishika667/Financial-Intelligence-Radar.git
cd Financial-Intelligence-Radar

# 2. Activate virtual environment (if using one)
# On Windows:
.venv\Scripts\Activate.ps1
# On Linux/macOS:
source .venv/bin/activate

# 3. Launch Fundamentals Lens
streamlit run fundamentals_lens_app.py
```
The application will launch immediately at `http://localhost:8501`. No API keys, database initialization, or login credentials are required.

---

## 3. Four-Page User Journey

### Page 1 — Overview
- **Landing Dashboard:** Introduces the product purpose and highlights the ₹0 operating architecture.
- **Universe Summary:** 15 companies across 5 peer groups with 75 consecutive annual audited periods.
- **Quick Explorer:** Select any company to view top-level KPIs (Latest Revenue, Operating Margin, Free Cash Flow, Cash Conversion) and preview rule-based narrative insights.

### Page 2 — Company Analysis
- **Full Operational Profile:** Detailed company business descriptions and peer context notes.
- **6 KPI Cards:** Top-line revenue & YoY growth %, Operating Income & EBIT margin %, Net Income & net margin %, Operating Cash Flow, Capex, and Free Cash Flow & cash conversion ratio.
- **Visual Analytics:** Three interactive Plotly charts:
  1. *5-Year Revenue & Operating Profitability*
  2. *Operating & Net Margin Trends (%)*
  3. *Cash Flow Generation & Free Cash Flow*
- **Audited Disclosures Table:** Multi-year table of all 5 primary financial items and derived metrics.
- **What Changed, Why It Matters, and What to Investigate:** Rule-based analytical cards explaining top-line growth, margin shifts, cash generation, earnings quality, and capital intensity.
- **Primary Source Drawer:** Direct links to SEC EDGAR and BSE filings, accession numbers, and statement locations.
- **Export Center:** Downloadable company CSV and comprehensive Markdown research brief.

### Page 3 — Peer Comparison
- **Intuitive Peer Group Selector:** Switch between Global Tech, Indian IT, Indian Consumer Brands, Indian Auto, and US Retailers.
- **Structural Caveats & Comparability Banner:** Explains business model nuances:
  - *Indian Auto:* Maruti Suzuki (passenger cars) vs. Bajaj Auto / Hero MotoCorp (2/3-wheelers).
  - *US Retail:* Costco (membership warehouse with negative working capital) vs. Walmart (omni-channel supercenter) vs. Target (discretionary).
  - *Global Tech:* Hyperscaler cloud capex vs. consumer hardware/services; non-aligned fiscal year-ends.
- **Currency Guards:** Strict separation ensuring USD is never mixed or cross-charted against INR.
- **Comparative Line Charts & Pivoted Tables:** Side-by-side benchmarking across YoY Growth, Margins, Cash Flow, and Cash Conversion.
- **Export:** Downloadable peer group comparison CSV.

### Page 4 — Data Integrity & Methodology
- **Philosophy:** Core principles of zero-cost operation, primary provenance, non-coercion, and consolidated reporting.
- **Coverage Audit Table:** Status of target reporting horizons across all 15 companies:
  - *Code 0 (VERIFIED INCLUDED):* Audited target period completed, published, and included (all 9 Indian companies for FY 2025–26; MSFT, WMT, COST, TGT for FY2026).
  - *Code 1 (PERIOD ONGOING / 10-K PENDING):* Period ongoing or filing due post-cutoff date (AAPL ending late September; GOOGL ending December 31).
- **Interactive 7-Gate Validation Dashboard:** Live execution of `FundamentalsValidator` (120/120 checks passing at 100.0% pass rate).
- **Master Source Register:** Complete searchable register of all 75 filings, accession IDs, and filing dates.

---

## 4. Deploying to Streamlit Community Cloud

Deploying Fundamentals Lens to Streamlit Community Cloud is 100% free and requires zero external database or secret configuration:

1. Push your branch to GitHub (`Rishika667/Financial-Intelligence-Radar`).
2. Log in to [Streamlit Community Cloud](https://share.streamlit.io/).
3. Click **"New App"** and select:
   - **Repository:** `Rishika667/Financial-Intelligence-Radar`
   - **Branch:** `main` (or your feature branch)
   - **Main file path:** `fundamentals_lens_app.py`
4. Click **"Deploy!"**.
5. Within 60 seconds, the app will build and serve traffic globally. Visitors do not need to configure anything.

---

## 5. Verification & Testing Instructions

To verify data integrity and software quality:

```bash
# 1. Run the 7-Gate Data Integrity CLI Validator
python scripts/validate_fundamentals_data.py

# 2. Run Fundamentals Lens Unit & Integration Tests (37 tests)
pytest tests/fundamentals_lens/ -q

# 3. Run the Full Project Regression Suite (187 tests)
pytest -q
```

All 187 tests run offline and pass deterministically.
