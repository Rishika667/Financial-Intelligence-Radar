# Fundamentals Lens — Phase 7 Gap Register & Post-MVP Backlog

This document records deferred capabilities, technical debt, and future enhancement candidates following the completion of Phase 7 (Expanded-Scope Milestone).

---

## 1. High-Priority Engineering Backlog

| Gap ID | Dimension | Current State (Phase 7) | Target Future State | Priority |
|:---|:---|:---|:---|:---:|
| **GAP-001** | Financial Reporting Granularity | Annual (10-K / Annual Report) disclosures only (75 annual periods). | Standalone and YTD quarterly (10-Q / BSE quarterly) ingestion with quarterly seasonal margin decomposition. | High |
| **GAP-002** | Automated PDF Extraction | Primary statement locations, page ranges, and table rows are manually catalogued and reconciled. | Automated open-source PDF table extraction with bounding box OCR locators for Indian annual reports. | Medium |
| **GAP-003** | Corporate Action Price Adjustments | OHLCV price series assume split-adjusted close prices. Uploaded unadjusted series require manual pre-processing. | Automatic stock split and dividend adjustment engine with SEC Form 8-K / corporate action ledger cross-checks. | High |
| **GAP-004** | Intraday OHLCV Resolution | Technical Analysis MVP supports daily bars only. | Support for intraday bars (1H, 15M, 5M) with in-memory aggregation and VWAP (Volume Weighted Average Price) computation. | Medium |
| **GAP-005** | Additional Technical Oscillators | Core suite includes SMA(20/50/200), RSI(14), MACD(12,26,9), Bollinger Bands(20,2), ATR(14). | Supplementary indicators: Stochastic Oscillator (%K, %D), Ichimoku Kinko Hyo, On-Balance Volume (OBV). | Low |

---

## 2. Analytical & Coverage Enhancements

| Gap ID | Area | Current Status | Future Target |
|:---|:---|:---|:---|
| **GAP-006** | Extended Universe Coverage | 15 companies across 5 peer groups (US Tech, India IT, US Retail, India FMCG, India Auto). | Expand universe to 25+ companies, adding European luxury, global energy, and healthcare peer groups. |
| **GAP-007** | Target Horizon Pending Filings | 3 US companies (AAPL, GOOGL, TGT) have FY2026 pending due to fiscal calendar cutoff. | Automatically ingest Form 10-K upon regulatory filing in late 2026/early 2027 to transition status code 1 -> 0. |
| **GAP-008** | Automated Segment Decomposition | Narrative engine provides segment commentary pointers; segment breakdown tables are not yet parsed as structured JSON. | Structured multi-year geographic and product line segment revenue tables in canonical dataset. |
| **GAP-009** | Valuation Multiple Integrations | Intentionally excluded from Fundamentals Lens scope to preserve pure disclosure intelligence without price forecasting. | Optional historical valuation context: Historical Enterprise Value / EBITDA and P/FCF ranges calculated deterministically from verified data. |

---

## 3. Maintenance & Integrity Review
All items in this register are non-blocking for Phase 7 release readiness. Zero synthetic zeroes exist in canonical datasets, all mathematical invariants hold, and tests pass 100%.
