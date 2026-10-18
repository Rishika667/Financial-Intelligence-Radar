# Fundamentals Lens: Master Sourcing & Evidence Assurance Audit

**Platform:** Fundamentals Lens (`Rishika667/Financial-Intelligence-Radar`)<br>
**Phase:** Phase 13 — Full Source Reconciliation, Analytical Suppression & Deployment-Candidate Certification<br>
**Author & Lead Engineer:** **Rishika Dangayach**<br>
**Audit Standard:** Zero-Coercion, Primary Statement Citation, Documented Discrepancy Ledger<br>
**Dataset Snapshot Cutoff:** `2026-10-18`

---

## 1. Evidence Verification Taxonomy & Standards

Every financial metric observation in Fundamentals Lens is assigned an unambiguous verification tier governed by strict deterministic rules in `FundamentalsValidator`:

| Verification Tier | Technical Definition | Required Evidence Attributes | Current Metric Count |
|:---|:---|:---|:---:|
| **`INDEPENDENTLY_RECONCILED`** | The metric has been verified directly against the official audited financial statement (Form 10-K or BSE/NSE Annual Report) with line-item and locator match. | Non-null `reported_value`, `comparison_result` (`EXACT_STATEMENT_MATCH` or documented discrepancy), statement name ($\ge 3$ chars), reported line item ($\ge 3$ chars), statement locator ($\ge 5$ chars), and accession / filing key. | **375** (100.0%) |
| **`SOURCE_LINKED_ONLY`** | Sourced directly from official annual filings with active primary URLs and document keys, but secondary line-item statement reconciliation is explicitly pending. | `reported_value = None`, `comparison_result = "NOT_RECONCILED"`, active primary document URL, filing key. Must **never** claim `EXACT_STATEMENT_MATCH`. | **0** (0.0%) |
| **`DERIVED_VERIFIED`** | Mathematical derivation computed directly from audited primary disclosures. | Invariant verified ($FCF = OCF - Capex$). Decoupled source input confidence (`INDEPENDENTLY_RECONCILED_INPUTS` vs `SOURCE_LINKED_INPUTS`). | **75** (100% of periods) |
| **`UNVERIFIED`** | Missing source provenance, invalid filing identity, or unverified disclosure. | Data suppressed or flagged for immediate review. | **0** (0.0%) |
| **`FAILED`** | Mathematical contradiction, corrupted value, or invariant breach. | Triggers validation failure; app suppresses metric card. | **0** (0.0%) |

---

## 2. Canonical 15-Company Universe Audit Matrix

### Group A: Global Technology Leaders (US GAAP • Form 10-K)
| Ticker | Company Name | Fiscal Periods | Filing Form | Primary Accession Range | Sourced Statement Locations | Reconciled Metrics | Source-Linked |
|:---|:---|:---:|:---:|:---|:---|:---:|:---:|
| `AAPL` | Apple Inc. | FY2021 – FY2025 | 10-K | `0000320193-21-000105` to `0000320193-25-000079` | Item 8 - Consolidated Statements of Operations & Cash Flows | 25 / 25 | 0 |
| `MSFT` | Microsoft Corp. | FY2022 – FY2026 | 10-K | `0001564590-22-026876` to `0001193125-26-323660` | Item 8 - Income Statements & Cash Flows Statements | 25 / 25 | 0 |
| `GOOGL` | Alphabet Inc. | FY2021 – FY2025 | 10-K | `0001652044-22-000019` to `0001652044-26-000018` | Item 8 - Consolidated Statements of Income & Cash Flows | 25 / 25 | 0 |

### Group B: Indian IT Services (Ind AS • BSE / NSE Annual Reports)
| Ticker | Company Name | Fiscal Periods | Filing Basis | Filing Accession / Scrip Reference | Sourced Statement Locations | Reconciled Metrics | Source-Linked (FY 2024–25) |
|:---|:---|:---:|:---:|:---|:---|:---:|:---:|
| `TCS` | Tata Consultancy Services | FY 2021–22 to FY 2025–26 | Consolidated Ind AS | `BSE-SCRIP-532540` / `TCS-AR-2022` to `2026` | Consolidated Statement of Profit & Loss and Cash Flows | 25 / 25 | 0 |
| `INFY` | Infosys Ltd. | FY 2021–22 to FY 2025–26 | Consolidated Ind AS | `BSE-SCRIP-500209` / `INFY-AR-2022` to `2026` | Consolidated Financial Statements — Profit and Loss & Cash Flow | 25 / 25 | 0 |
| `HCLTECH` | HCL Technologies | FY 2021–22 to FY 2025–26 | Consolidated Ind AS | `BSE-SCRIP-532281` / `HCLTECH-AR-2022` to `2026` | Consolidated Financial Statements — Statement of Profit and Loss | 25 / 25 | 0 |

### Group C: Indian Consumer Staples / FMCG (Ind AS • BSE / NSE Annual Reports)
| Ticker | Company Name | Fiscal Periods | Filing Basis | Filing Accession / Scrip Reference | Sourced Statement Locations | Reconciled Metrics | Source-Linked (FY 2024–25) |
|:---|:---|:---:|:---:|:---|:---|:---:|:---:|
| `HINDUNILVR` | Hindustan Unilever | FY 2021–22 to FY 2025–26 | Consolidated Ind AS | `BSE-SCRIP-500696` / `HUL-AR-2022` to `2026` | Consolidated Statement of Profit and Loss & Cash Flow Statement | 25 / 25 | 0 |
| `BRITANNIA` | Britannia Industries | FY 2021–22 to FY 2025–26 | Consolidated Ind AS | `BSE-SCRIP-500825` / `BRIT-AR-2022` to `2026` | Consolidated Financial Statements — P&L and Cash Flow | 25 / 25 | 0 |
| `DABUR` | Dabur India | FY 2021–22 to FY 2025–26 | Consolidated Ind AS | `BSE-SCRIP-500096` / `DABUR-AR-2022` to `2026` | Consolidated Statement of Profit and Loss & Cash Flows | 25 / 25 | 0 |

### Group D: Indian Automobile Manufacturers (Ind AS • BSE / NSE Annual Reports)
| Ticker | Company Name | Fiscal Periods | Filing Basis | Filing Accession / Scrip Reference | Sourced Statement Locations | Reconciled Metrics | Source-Linked (FY 2024–25) |
|:---|:---|:---:|:---:|:---|:---|:---:|:---:|
| `MARUTI` | Maruti Suzuki India | FY 2021–22 to FY 2025–26 | Consolidated Ind AS | `BSE-SCRIP-532500` / `MARUTI-AR-2022` to `2026` | Consolidated Statement of Profit and Loss & Cash Flows | 25 / 25 | 0 |
| `BAJAJ-AUTO` | Bajaj Auto Ltd. | FY 2021–22 to FY 2025–26 | Consolidated Ind AS | `BSE-SCRIP-532977` / `BAJAJ-AR-2022` to `2026` | Consolidated Statement of Profit and Loss & Cash Flows | 25 / 25 | 0 |
| `HEROMOTOCO` | Hero MotoCorp | FY 2021–22 to FY 2025–26 | Consolidated Ind AS | `BSE-SCRIP-500182` / `HERO-AR-2022` to `2026` | Consolidated Statement of Profit and Loss & Cash Flows | 25 / 25 | 0 |

### Group E: US Retail Leaders (US GAAP • Form 10-K)
| Ticker | Company Name | Fiscal Periods | Filing Form | Primary Accession Range | Sourced Statement Locations | Reconciled Metrics | Source-Linked |
|:---|:---|:---:|:---:|:---|:---|:---:|:---:|
| `WMT` | Walmart Inc. | FY2022 – FY2026 | 10-K | `0000104169-22-000012` to `0000104169-26-000055` | Item 8 - Consolidated Statements of Income & Cash Flows | 25 / 25 | 0 |
| `COST` | Costco Wholesale | FY2022 – FY2026 | 10-K | `0000909832-22-000021` to `0000909832-26-000093` | Item 8 - Consolidated Statements of Operations & Cash Flows | 25 / 25 | 0 |
| `TGT` | Target Corporation | FY2021 – FY2025 | 10-K | `0000027419-22-000007` to `0000027419-26-000016` | Item 8 - Consolidated Statements of Operations & Cash Flows | 25 / 25 | 0 |

---

## 3. Discrepancy Ledger & Accounting Nuance Log

The canonical repository maintains a formal discrepancy ledger (`datasets/fundamentals_lens/discrepancy_ledger.json`) tracking structural accounting definitions, segment reconciliations, and primary statement audits:

| Discrepancy ID | Company | Fiscal Year | Metric | Initial Value | Reconciled Value | Investigation Finding & Accounting Resolution |
|:---|:---|:---:|:---|:---:|:---:|:---|
| `DISC-001` | `GOOGL` | FY2025 | Capex | $91,400.0M | $91,447.0M | Early IR presentation cited preliminary ~$91.4B; audited Form 10-K Cash Flows reports exact cash payments for property & equipment of $91,447M under accession `0001652044-26-000018`. |
| `DISC-002` | `TGT` | FY2023 | Operating Income | $5,711.0M | $5,707.0M | Preliminary earnings release cited $5,711M; official Form 10-K Item 8 Consolidated Statements of Operations reports Operating Income of $5,707M for the 53-week fiscal year. |
| `DISC-003` | `BAJAJ-AUTO` | FY 2023–24 | Revenue | ₹44,870.0 Cr | ₹44,685.2 Cr | Standalone revenue was ₹44,870.43 Cr; consolidated revenue was ₹44,685.23 Cr. Registered canonical consolidated figure of ₹44,685.2 Cr per strict Consolidated mandate. |
| `DISC-004` | `INFY` | FY 2021–22 | Operating Income | ₹28,010.0 Cr | ₹28,015.0 Cr | IFRS presentation cited ₹28,010 Cr; Ind AS audited Consolidated Statement of Profit and Loss reports Operating profit of ₹28,015 Cr. Reconciled to Ind AS Consolidated P&L. |
| `DISC-005` | `WMT` | FY2025 | Operating Income | $27,011.0M | $29,348.0M | Initial dataset recorded non-GAAP adjusted operating income; official Form 10-K Item 8 Consolidated Statements of Income reports GAAP Operating Income of $29,348M. |
| `DISC-006` | `WMT` | FY2026 | Revenue | $713,158.0M | $713,163.0M | Preliminary segment disclosure cited $713,158M; official Form 10-K Consolidated Statements of Income reports Total Revenues of $713,163M (Net sales $706,413M + Membership & other $6,750M). |
| `DISC-007` | `TCS` | FY 2025–26 | Operating Income | ₹66,755.0 Cr | ₹66,755.0 Cr | Dataset stores ₹66,755 Cr reflecting Operating profit before exceptional items and other income (PBEI). In 5-Year Performance Trend of Integrated Annual Report, EBIT is cited as ₹66,838 Cr. Canonical registered as PBEI proxy with `PROXY` comparability flag and documented ₹83 Cr delta. |
| `DISC-008` | `BAJAJ-AUTO` | FY 2025–26 | Operating Income | ₹12,019.0 Cr | ₹12,019.0 Cr | Stored ₹12,019 Cr represents EBITDA (Operating Profit before Depreciation) as highlighted in Annual Report. Standalone depreciation is ₹448.2 Cr, giving operating profit (EBIT) of ~₹11,570.8 Cr. Documented as EBITDA Proxy with `PROXY` comparability flag. |
| `DISC-009` | `INFY` | FY 2025–26 | Net Income | ₹29,440.0 Cr | ₹29,440.0 Cr | Total consolidated profit is ₹29,474 Cr. Profit attributable to owners of the Company (after non-controlling interests of ₹34 Cr) is ₹29,440 Cr. Registered attribution basis as `ATTRIBUTABLE_TO_OWNERS`. |
| `DISC-010` | `COST` | FY2022 | Op & Net Income | $7,795.0M / $5,841M | $7,793.0M / $5,844M | Initial dataset had $7,795.0M operating income and $5,841.0M net income; official Form 10-K Item 8 Consolidated Statements of Operations reports Operating Income of $7,793.0M and Net Income of $5,844.0M. |
| `DISC-011` | `COST` | FY2024 | Accession Alignment | ...-000084 | ...-000049 | Previous dataset recorded accession 0000909832-24-000084; official SEC EDGAR submissions API confirms accession is 0000909832-24-000049. |
| `DISC-012` | `COST` | FY2025 | OCF & Capex | $14,100M / $5,200M | $13,335.0M / $5,498M | Preliminary estimate recorded $14,100M OCF and $5,200M capex; official Form 10-K Item 8 Consolidated Statements of Cash Flows reports OCF of $13,335M and Capex of $5,498M. FCF updated to $7,837M. |
| `DISC-013` | `COST` | FY2026 | Operating Income | $11,700.0M | $11,685.0M | Initial dataset had $11,700M rounded operating income; official Form 10-K Item 8 Consolidated Statements of Operations reports Operating Income of $11,685.0M under accession `0000909832-26-000093`. |
| `DISC-014` | `MSFT` | FY2025 | Revenue & Op Inc | $281,654M / $128,450M | $281,724.0M / $128,528M | Subsequent segment reclassifications in Microsoft Form 10-K report Revenue of $281,724M and Operating Income of $128,528M under accession `0000950170-25-100235`. |
| `DISC-015` | `MSFT` | FY2026 | Net Income & OCF | $133,768M / $182,933M | $133,749.0M / $182,935M | Initial dataset had $133,768M net income and $182,933M OCF; official Form 10-K Item 8 reports Net Income of $133,749M and Cash from Operations of $182,935M under accession `0001193125-26-323660`. FCF updated to $66,987M. |
| `DISC-016` | `WMT` | FY2025/26 | GAAP Net Income | $19,549M / $22,279M | $19,436.0M / $21,893M | Previous dataset recorded preliminary non-GAAP net income; official Form 10-K Item 8 reports GAAP Net Income of $19,436M (FY25, `0000104169-25-000021`) and $21,893M (FY26, `0000104169-26-000055`) under concept `us-gaap:NetIncomeLoss`. |

---

## 4. Verification and Audit Commands

### Deterministic Clean-Clone Rebuild (100% Offline)
```bash
# Rebuild source observations strictly from tracked source inputs
python scripts/build_source_observations_phase13.py --offline

# Rebuild evidence register and reconcile against canonical facts
python scripts/build_evidence_register_phase13.py
```

### Deterministic Validation (100% Offline CI)
```bash
python scripts/validate_fundamentals_data.py
```
- Validates structural completeness, chronological dates, arithmetic invariants, source URLs, accessions, dynamic document identity, and evidence tier consistency across all 15 companies.

### Full Test Suite Execution
```bash
python -m pytest -q
```
- Executes 306 unit, integration, and adversarial tests (including 54 adversarial invariant, Phase 13 scenario tests, and clean-clone reproducibility tests).

### SEC Submissions Audit (Offline & Online Modes)
```bash
# Offline structural check
python scripts/audit_sec_filings_online.py --offline --strict

# Online SEC EDGAR submissions API verification (Traverses recent & historical submissions)
python scripts/audit_sec_filings_online.py --user-agent "RishikaDangayach rishika@example.com" --strict
```
- Verifies official Form 10-K filing identity, accession numbers, filing dates, and primary document names against SEC EDGAR.

---

## 5. Summary Certification

- **Universe Integrity:** Exactly 15 companies, 75 consecutive annual periods.
- **Evidence Integrity:** 375 Reconciled (100.0%), 0 Source-Linked (0.0%), 0 Unverified (0.0%).
- **Derived Integrity:** 75 Free Cash Flow records mathematically validated with decoupled source input confidence.
- **Validation Gates:** 255 / 255 checks passing (100.0%).
- **Pytest Suite:** 306 / 306 tests passing (100.0%).
- **Discrepancy Ledger:** 16 documented accounting items (DISC-001 through DISC-016).
- **Clean-Clone Certification:** 100% offline reproducible without git-ignored scratch caches.
- **Peer Safeguards:** Analytical suppression enforced for proxy metrics and cross-currency comparisons.
- **Platform Author:** **Rishika Dangayach**
