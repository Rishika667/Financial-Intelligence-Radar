# Fundamentals Lens — Discrepancy Ledger & Source Audit Trail (Phase 11)

**Product:** Fundamentals Lens  
**Repository:** `Rishika667/Financial-Intelligence-Radar`  
**Branch:** `pivot/fundamentals-lens-phase0`  
**Author & Lead Engineer:** **Rishika Dangayach**  
**Audit Cutoff:** October 18, 2026  
**Audit Standard:** Zero-Synthetic Fabrication, Primary Statement Citation, Documented Accounting Nuance  

---

## Executive Summary

During Phase 6 through Phase 11 adversarial auditing and reconciliation against official regulatory filings (SEC EDGAR Form 10-K and BSE/NSE Ind AS Annual Reports), fifteen specific financial discrepancies and definition divergences were identified and reconciled (DISC-001 through DISC-015).

In accordance with the project's zero-synthetic-fabrication and primary-source-truth mandate, all fifteen discrepancies were investigated against official Item 8 consolidated financial statements, official SEC EDGAR submissions APIs, and Integrated Annual Reports, documented in `datasets/fundamentals_lens/discrepancy_ledger.json`, corrected in `financial_facts_5yr.json`, and cross-verified in `evidence_register.json` and `source_observations.json`.

---

## Discrepancy Investigation Ledger

### 1. DISC-001: Alphabet Inc. (GOOGL) — FY2025 Capital Expenditure
- **Metric:** `capital_expenditure`
- **Fiscal Period:** `FY2025` (Year Ended December 31, 2025)
- **Initial Dataset Value:** `$91,400.0M`
- **Audited Primary Value:** `$91,447.0M`
- **Filing Reference:** SEC Form 10-K Accession `0001652044-26-000018` (Filed February 5, 2026)
- **Statement Location:** Item 8 — Consolidated Statements of Cash Flows, Line: *"Purchases of property and equipment"*
- **Investigation Finding:** Preliminary earnings presentation slides cited a rounded figure (~$91.4B capex). The official audited Form 10-K Consolidated Statements of Cash Flows reports exact cash payments for property and equipment of $91,447M.
- **Resolution:** Updated canonical dataset and evidence register to `$91,447.0M` with exact accession ID `0001652044-26-000018`. Derived Free Cash Flow updated deterministically to `$33,025.0M` ($124,472M OCF − $91,447M Capex).

---

### 2. DISC-002: Target Corporation (TGT) — FY2023 Operating Income
- **Metric:** `operating_income`
- **Fiscal Period:** `FY2023` (53-Week Fiscal Year Ended February 3, 2024)
- **Initial Dataset Value:** `$5,711.0M`
- **Audited Primary Value:** `$5,707.0M`
- **Filing Reference:** SEC Form 10-K Accession `0000027419-24-000032` (Filed March 13, 2024)
- **Statement Location:** Item 8 — Consolidated Statements of Operations, Line: *"Operating income"*
- **Investigation Finding:** Preliminary press release tables reported $5,711M before final audit close. The official Form 10-K Item 8 Consolidated Statements of Operations reports Operating Income of $5,707M.
- **Resolution:** Corrected canonical dataset and evidence register to `$5,707.0M`.

---

### 3. DISC-003: Bajaj Auto Limited (BAJAJ-AUTO) — FY 2023–24 Revenue
- **Metric:** `revenue`
- **Fiscal Period:** `FY 2023–24` (Year Ended March 31, 2024)
- **Initial Dataset Value:** `₹44,870.0 Cr`
- **Audited Primary Value:** `₹44,685.2 Cr` (₹44,685.23 Crores)
- **Filing Reference:** Internal Document Key `BSE-SCRIP-532977-AR-2023-24`
- **Statement Location:** Consolidated Statement of Profit and Loss, Line: *"Revenue from operations"*
- **Investigation Finding:** Standalone revenue from operations was ₹44,870.43 Cr; consolidated revenue from operations was ₹44,685.23 Cr. To preserve the strict Consolidated basis mandate across the entire platform, the consolidated figure of ₹44,685.2 Cr is registered.
- **Resolution:** Canonical dataset value aligned to Consolidated Statement of Profit and Loss at `₹44,685.2 Cr` with explicit note documenting standalone vs consolidated delta.

---

### 4. DISC-004: Infosys Limited (INFY) — FY 2021–22 Operating Profit
- **Metric:** `operating_income`
- **Fiscal Period:** `FY 2021–22` (Year Ended March 31, 2022)
- **Initial Dataset Value:** `₹28,010.0 Cr`
- **Audited Primary Value:** `₹28,015.0 Cr`
- **Filing Reference:** Internal Document Key `BSE-SCRIP-500209-AR-2021-22`
- **Statement Location:** Ind AS Consolidated Statement of Profit and Loss, Line: *"Operating profit"*
- **Investigation Finding:** IFRS presentation tables in investor presentations cited ₹28,010 Cr. The official Ind AS audited Consolidated Statement of Profit and Loss reports Operating profit of ₹28,015 Cr.
- **Resolution:** Reconciled canonical dataset to official Ind AS Consolidated Statement of Profit and Loss at `₹28,015.0 Cr`.

---

### 5. DISC-005: Walmart Inc. (WMT) — FY2025 Operating Income
- **Metric:** `operating_income`
- **Fiscal Period:** `FY2025` (Year Ended January 31, 2025)
- **Initial Dataset Value:** `$27,011.0M`
- **Audited Primary Value:** `$29,348.0M`
- **Filing Reference:** SEC Form 10-K Accession `0000104169-25-000021` (Filed March 14, 2025)
- **Statement Location:** Item 8 — Consolidated Statements of Income, Line: *"Operating income"*
- **Investigation Finding:** Initial dataset recorded adjusted non-GAAP operating income ($27,011M). Official Form 10-K Item 8 Consolidated Statements of Income reports GAAP Operating Income of $29,348M.
- **Resolution:** Updated canonical value to `$29,348.0M` to conform strictly to GAAP audited statement reporting standards.

---

### 6. DISC-006: Walmart Inc. (WMT) — FY2026 Total Revenues
- **Metric:** `revenue`
- **Fiscal Period:** `FY2026` (Year Ended January 31, 2026)
- **Initial Dataset Value:** `$713,158.0M`
- **Audited Primary Value:** `$713,163.0M`
- **Filing Reference:** SEC Form 10-K Accession `0000104169-26-000055` (Filed March 13, 2026)
- **Statement Location:** Item 8 — Consolidated Statements of Income, Line: *"Total revenues"*
- **Investigation Finding:** Preliminary segment disclosure reported $713,158M (excluding certain membership adjustments). Official Form 10-K Consolidated Statements of Income reports Total Revenues of $713,163M (Net sales $706,413M + Membership and other income $6,750M).
- **Resolution:** Updated canonical dataset and evidence register to `$713,163.0M`.

---

### 7. DISC-007: Tata Consultancy Services (TCS) — FY 2025–26 Operating Income
- **Metric:** `operating_income`
- **Fiscal Period:** `FY 2025–26` (Year Ended March 31, 2026)
- **Initial Dataset Value:** `₹66,755.0 Cr`
- **Audited Primary Value:** `₹66,755.0 Cr`
- **Filing Reference:** Internal Document Key `BSE-SCRIP-532540-AR-2025-26`
- **Statement Location:** Consolidated Statement of Profit and Loss, Operating profit before exceptional items and other income
- **Investigation Finding:** The dataset stores ₹66,755 Cr, which reflects Operating profit before exceptional items and other income (PBEI). In the 5-Year Performance Trend of the Integrated Annual Report, EBIT is cited as ₹66,838 Cr (including other operating items).
- **Resolution:** Documented canonical line item as Operating Profit before Other Income/Exceptional Items (PBEI Proxy) at `66,755.0 Cr` with `PROXY` comparability flag and noted EBIT delta of ₹83 Cr in ledger.

---

### 8. DISC-008: Bajaj Auto Limited (BAJAJ-AUTO) — FY 2025–26 Operating Income
- **Metric:** `operating_income`
- **Fiscal Period:** `FY 2025–26` (Year Ended March 31, 2026)
- **Initial Dataset Value:** `₹12,019.0 Cr`
- **Audited Primary Value:** `₹12,019.0 Cr`
- **Filing Reference:** Internal Document Key `BSE-SCRIP-532977-AR-2025-26`
- **Statement Location:** Consolidated Statement of Profit and Loss / Annual Report Highlights, Operating Profit before Depreciation
- **Investigation Finding:** The stored value of ₹12,019 Cr represents EBITDA (Operating Profit before Depreciation & Amortisation) as highlighted in Bajaj Auto's Annual Report. Standalone depreciation is ₹448.2 Cr, giving operating profit (EBIT) of ~₹11,570.8 Cr.
- **Resolution:** Documented canonical line item as EBITDA (Operating Profit Proxy) at `12,019.0 Cr` with `PROXY` comparability flag, noting EBIT of ~₹11,570.8 Cr in ledger.

---

### 9. DISC-009: Infosys Limited (INFY) — FY 2025–26 Net Income
- **Metric:** `net_income`
- **Fiscal Period:** `FY 2025–26` (Year Ended March 31, 2026)
- **Initial Dataset Value:** `₹29,440.0 Cr`
- **Audited Primary Value:** `₹29,440.0 Cr`
- **Filing Reference:** Internal Document Key `BSE-SCRIP-500209-AR-2025-26`
- **Statement Location:** Consolidated Statement of Profit and Loss, Profit for the period attributable to owners of the Company
- **Investigation Finding:** In Infosys Consolidated Financial Results for FY26, total profit for the period is ₹29,474 Cr. Net profit attributable to owners of the Company (after non-controlling interests of ₹34 Cr) is ₹29,440 Cr.
- **Resolution:** Documented attribution basis as `ATTRIBUTABLE_TO_OWNERS` at `29,440.0 Cr`, confirming canonical figure aligns with common equity shareholder net income.

---

### 10. DISC-010: Costco Wholesale Corporation (COST) — FY2022 Operating Income & Net Income
- **Metric:** `operating_income`, `net_income`
- **Fiscal Period:** `FY2022` (Year Ended August 28, 2022)
- **Initial Dataset Value:** `$7,795.0M` (Op Income), `$5,841.0M` (Net Income)
- **Audited Primary Value:** `$7,793.0M` (Op Income), `$5,844.0M` (Net Income)
- **Filing Reference:** SEC Form 10-K Accession `0000909832-22-000021` (Filed October 5, 2022)
- **Statement Location:** Item 8 — Consolidated Statements of Operations, Line: *"Operating income"* and *"Net income"*
- **Investigation Finding:** Initial dataset had $7,795.0M operating income and $5,841.0M net income; official Form 10-K Item 8 Consolidated Statements of Operations reports Operating Income of $7,793.0M and Net Income of $5,844.0M.
- **Resolution:** Updated canonical operating income to $7,793.0M and net income to $5,844.0M to conform to audited Form 10-K statement.

---

### 11. DISC-011: Costco Wholesale Corporation (COST) — FY2024 Accession Alignment
- **Metric:** `accession_alignment`
- **Fiscal Period:** `FY2024` (Year Ended September 1, 2024)
- **Initial Dataset Value:** Accession `0000909832-24-000084`
- **Audited Primary Value:** Accession `0000909832-24-000049`
- **Filing Reference:** SEC Form 10-K Accession `0000909832-24-000049` (Filed October 9, 2024)
- **Statement Location:** SEC EDGAR Submissions Master API
- **Investigation Finding:** Previous dataset recorded accession 0000909832-24-000084 for Form 10-K filed October 9, 2024; official SEC EDGAR submissions API confirms accession is 0000909832-24-000049.
- **Resolution:** Updated accession_id to 0000909832-24-000049 and aligned source_url accordingly.

---

### 12. DISC-012: Costco Wholesale Corporation (COST) — FY2025 Operating Cash Flow & Capex
- **Metric:** `operating_cash_flow`, `capital_expenditure`
- **Fiscal Period:** `FY2025` (Year Ended August 31, 2025)
- **Initial Dataset Value:** `$14,100.0M` (OCF), `$5,200.0M` (Capex)
- **Audited Primary Value:** `$13,335.0M` (OCF), `$5,498.0M` (Capex)
- **Filing Reference:** SEC Form 10-K Accession `0000909832-25-000084` (Filed October 8, 2025)
- **Statement Location:** Item 8 — Consolidated Statements of Cash Flows, Line: *"Cash provided by operating activities"* and *"Property additions (Capex)"*
- **Investigation Finding:** Preliminary estimate recorded $14,100M OCF and $5,200M capex; official Form 10-K Item 8 Consolidated Statements of Cash Flows reports Cash Provided by Operating Activities of $13,335M and Property Additions (Capex) of $5,498M.
- **Resolution:** Updated canonical OCF to $13,335.0M, capex to $5,498.0M, and recomputed FCF as $7,837.0M ($13,335M − $5,498M).

---

### 13. DISC-013: Costco Wholesale Corporation (COST) — FY2026 Operating Income
- **Metric:** `operating_income`
- **Fiscal Period:** `FY2026` (Year Ended August 30, 2026)
- **Initial Dataset Value:** `$11,700.0M`
- **Audited Primary Value:** `$11,685.0M`
- **Filing Reference:** SEC Form 10-K Accession `0000909832-26-000093` (Filed October 7, 2026)
- **Statement Location:** Item 8 — Consolidated Statements of Operations, Line: *"Operating income"*
- **Investigation Finding:** Initial dataset had $11,700M rounded operating income; official Form 10-K Item 8 Consolidated Statements of Operations reports Operating Income of $11,685.0M under accession 0000909832-26-000093.
- **Resolution:** Updated canonical operating income to $11,685.0M to match official 10-K statement.

---

### 14. DISC-014: Microsoft Corporation (MSFT) — FY2025 Revenue & Operating Income
- **Metric:** `revenue`, `operating_income`
- **Fiscal Period:** `FY2025` (Year Ended June 30, 2025)
- **Initial Dataset Value:** `$281,654.0M` (Revenue), `$128,450.0M` (Op Income)
- **Audited Primary Value:** `$281,724.0M` (Revenue), `$128,528.0M` (Op Income)
- **Filing Reference:** SEC Form 10-K Accession `0000950170-25-100235` (Filed July 30, 2025)
- **Statement Location:** Item 8 — Consolidated Statements of Income, Line: *"Total revenue"* and *"Operating income"*
- **Investigation Finding:** Subsequent segment reclassifications in Microsoft Form 10-K report Revenue of $281,724M and Operating Income of $128,528M.
- **Resolution:** Updated canonical revenue to $281,724.0M and operating income to $128,528.0M to align with audited Form 10-K.

---

### 15. DISC-015: Microsoft Corporation (MSFT) — FY2026 Net Income & Operating Cash Flow
- **Metric:** `net_income`, `operating_cash_flow`
- **Fiscal Period:** `FY2026` (Year Ended June 30, 2026)
- **Initial Dataset Value:** `$133,768.0M` (Net Income), `$182,933.0M` (OCF)
- **Audited Primary Value:** `$133,749.0M` (Net Income), `$182,935.0M` (OCF)
- **Filing Reference:** SEC Form 10-K Accession `0001193125-26-323660` (Filed July 29, 2026)
- **Statement Location:** Item 8 — Consolidated Statements of Income & Cash Flows, Line: *"Net income"* and *"Operations"*
- **Investigation Finding:** Initial dataset had $133,768M net income and $182,933M OCF; official Form 10-K Item 8 reports Net Income of $133,749M and Cash from Operations of $182,935M under accession 0001193125-26-323660.
- **Resolution:** Updated canonical net income to $133,749.0M, OCF to $182,935.0M, and recomputed FCF as $66,987.0M ($182,935M − $115,948M).

### 16. DISC-016: Walmart Inc. (WMT) — FY2025 & FY2026 GAAP Net Income Reconciliation
- **Metric:** `net_income`
- **Fiscal Period:** `FY2025` & `FY2026` (Years Ended January 31, 2025 and January 31, 2026)
- **Initial Dataset Value:** `$19,549.0M` (FY2025), `$22,279.0M` (FY2026)
- **Audited Primary Value:** `$19,436.0M` (FY2025), `$21,893.0M` (FY2026)
- **Filing Reference:** SEC Form 10-K Accessions `0000104169-25-000021` (FY2025) and `0000104169-26-000055` (FY2026)
- **Statement Location:** Item 8 — Consolidated Statements of Income, Line: *"Consolidated net income attributable to Walmart"*, Concept: `us-gaap:NetIncomeLoss`
- **Investigation Finding:** Previous dataset recorded preliminary non-GAAP / press release net income of $19,549M for FY2025 and $22,279M for FY2026. Official audited Form 10-K Item 8 Consolidated Statements of Income reports GAAP Consolidated net income attributable to Walmart of $19,436M for FY2025 and $21,893M for FY2026 under concept us-gaap:NetIncomeLoss.
- **Resolution:** Updated canonical net income to $19,436.0M for FY2025 and $21,893.0M for FY2026, eliminating silent hardcoded script overrides and strictly adhering to audited Form 10-K GAAP reporting.

---

## Reconciliation Summary Table

| ID | Ticker | Fiscal Period | Metric | Initial Value | Corrected Canonical | Difference | Official Filing Citation |
|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---|
| **DISC-001** | GOOGL | FY2025 | Capex | $91,400.0M | $91,447.0M | +$47.0M | SEC 10-K `0001652044-26-000018` |
| **DISC-002** | TGT | FY2023 | Operating Income | $5,711.0M | $5,707.0M | -$4.0M | SEC 10-K `0000027419-24-000032` |
| **DISC-003** | BAJAJ-AUTO | FY 2023–24 | Revenue | ₹44,870.0 Cr | ₹44,685.2 Cr | -₹184.8 Cr | BSE Scrip `532977` Consolidated |
| **DISC-004** | INFY | FY 2021–22 | Operating Income | ₹28,010.0 Cr | ₹28,015.0 Cr | +₹5.0 Cr | BSE Scrip `500209` Ind AS |
| **DISC-005** | WMT | FY2025 | Operating Income | $27,011.0M | $29,348.0M | +$2,337.0M | SEC 10-K `0000104169-25-000021` (GAAP) |
| **DISC-006** | WMT | FY2026 | Revenue | $713,158.0M | $713,163.0M | +$5.0M | SEC 10-K `0000104169-26-000055` |
| **DISC-007** | TCS | FY 2025–26 | Operating Income | ₹66,755.0 Cr | ₹66,755.0 Cr | 0 (EBIT +₹83 Cr) | BSE Scrip `532540` PBEI Proxy |
| **DISC-008** | BAJAJ-AUTO | FY 2025–26 | Operating Income | ₹12,019.0 Cr | ₹12,019.0 Cr | 0 (EBIT ~₹11,570.8 Cr) | BSE Scrip `532977` EBITDA Proxy |
| **DISC-009** | INFY | FY 2025–26 | Net Income | ₹29,440.0 Cr | ₹29,440.0 Cr | 0 (Consol +₹34 Cr) | BSE Scrip `500209` Attributable to Owners |
| **DISC-010** | COST | FY2022 | Op & Net Income | $7,795.0M / $5,841M | $7,793.0M / $5,844M | -$2.0M / +$3.0M | SEC 10-K `0000909832-22-000021` |
| **DISC-011** | COST | FY2024 | Accession Alignment | ...-000084 | ...-000049 | Accession fixed | SEC EDGAR API `0000909832-24-000049` |
| **DISC-012** | COST | FY2025 | OCF & Capex | $14,100M / $5,200M | $13,335.0M / $5,498M | -$765M / +$298M | SEC 10-K `0000909832-25-000084` |
| **DISC-013** | COST | FY2026 | Operating Income | $11,700.0M | $11,685.0M | -$15.0M | SEC 10-K `0000909832-26-000093` |
| **DISC-014** | MSFT | FY2025 | Revenue & Op Inc | $281,654M / $128,450M | $281,724.0M / $128,528M | +$70.0M / +$78.0M | SEC 10-K `0000950170-25-100235` |
| **DISC-015** | MSFT | FY2026 | Net Income & OCF | $133,768M / $182,933M | $133,749.0M / $182,935M | -$19.0M / +$2.0M | SEC 10-K `0001193125-26-323660` |
| **DISC-016** | WMT | FY2025/26 | GAAP Net Income | $19,549M / $22,279M | $19,436.0M / $21,893M | -$113M / -$386M | SEC 10-K `0000104169-25-000021` / `...-26-000055` |

---

*Discrepancy ledger verified and integrated into automated validation pipeline via `scripts/validate_fundamentals_data.py`.*
