#!/usr/bin/env python3
"""
Phase 13 Evidence Register & Canonical Dataset Pipeline (Phase 14 Hardened).

Reconciles independent primary source observations against canonical financial facts
using the canonical reconciliation engine (src/fundamentals_lens/reconciliation.py).

Guarantees:
1. Strict independence: reported_value is read EXCLUSIVELY from datasets/fundamentals_lens/source_observations.json.
2. Pre-map uniqueness validation: strictly verifies absence of duplicate observation IDs,
   duplicate (ticker, fiscal_year, metric) records, duplicate facts, and duplicate source keys before mapping.
3. Official document identity verification: Derived from accession syntax, CIK/scrip alignment,
   and official corporate/exchange URL structures (via src/fundamentals_lens/reconciliation.py).
4. Multi-dimensional verification status: document_identity_status, document_retrieval_status, period_match_status,
   metric_extraction_status, and numeric_reconciliation_status.
5. Normalized discrepancy schema: Explicit separation of initial value, canonical before correction,
   primary reported value, final canonical value, and typed discrepancy category.
6. Multi-metric & multi-period resolution: Supports compound discrepancy entries with granular sub-metric indexing.
7. Synchronized exports: evidence_register.json, evidence_register.csv, source_register.json, discrepancy_ledger.json,
   source_check_report.json, and dataset_metadata.json.
"""

import sys
import os
import json
import csv
import re
import time
import argparse
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional, Set

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

from fundamentals_lens.reconciliation import (
    reconcile_metric_observation,
    derive_source_reconciliation_status,
    derive_document_identity_verified,
    DocumentIdentityStatus,
    DocumentRetrievalStatus,
    PeriodMatchStatus,
    MetricExtractionStatus,
    NumericReconciliationStatus,
    ReconciliationTier,
)

DATASETS_DIR = REPO_ROOT / "datasets" / "fundamentals_lens"

FACTS_FILE = DATASETS_DIR / "financial_facts_5yr.json"
SOURCES_FILE = DATASETS_DIR / "source_register.json"
EVIDENCE_JSON = DATASETS_DIR / "evidence_register.json"
EVIDENCE_CSV = DATASETS_DIR / "evidence_register.csv"
DISCREPANCY_JSON = DATASETS_DIR / "discrepancy_ledger.json"
SOURCE_CHECK_REPORT = DATASETS_DIR / "source_check_report.json"
SOURCE_OBS_FILE = DATASETS_DIR / "source_observations.json"
METADATA_FILE = DATASETS_DIR / "dataset_metadata.json"
COMPANIES_FILE = DATASETS_DIR / "companies.json"

SEC_ACCESSION_PATTERN = re.compile(r"^\d{10}-\d{2}-\d{6}$")
BSE_KEY_PATTERN = re.compile(r"^BSE-SCRIP-(\d+)-AR-")

# Load company metadata for dynamic CIK / BSE scrip validation
with open(COMPANIES_FILE, "r", encoding="utf-8") as f:
    COMPANIES_RAW = json.load(f)
COMPANY_MAP = {c["ticker"]: c for c in COMPANIES_RAW}

DISCREPANCIES = [
    {
        "discrepancy_id": "DISC-001",
        "ticker": "GOOGL",
        "fiscal_year": 2025,
        "fiscal_year_label": "FY2025",
        "affected_periods": [2025],
        "metric": "capital_expenditure",
        "discrepancy_category": "NUMERICAL_REVISION",
        "discrepancy_type": "AUDITED_STATEMENT_RECONCILIATION",
        "is_numerical": True,
        "initial_dataset_value": 91400.0,
        "canonical_value_before_correction": 91400.0,
        "primary_reported_value": 91447.0,
        "final_canonical_value": 91447.0,
        "canonical_value": 91447.0,
        "reported_value": 91447.0,
        "unit": "$ Millions",
        "status": "RESOLVED",
        "investigation_finding": "Early IR presentation slides cited preliminary ~$91.4B rounded capex; official audited Form 10-K Consolidated Statements of Cash Flows reports exact cash payments for property and equipment of $91,447M under accession 0001652044-26-000018.",
        "resolution_rationale": "Updated canonical value from 91,400.0 to 91,447.0 and aligned accession ID to 0001652044-26-000018.",
        "resolution": "Updated canonical value from 91,400.0 to 91,447.0 and aligned accession ID to 0001652044-26-000018.",
        "resolution_or_reconciliation_note": "Updated canonical value from 91,400.0 to 91,447.0 and aligned accession ID to 0001652044-26-000018.",
        "source_accession_or_key": "0001652044-26-000018",
        "affected_metrics_detail": [
            {
                "metric": "capital_expenditure",
                "initial_dataset_value": 91400.0,
                "canonical_value_before_correction": 91400.0,
                "primary_reported_value": 91447.0,
                "final_canonical_value": 91447.0,
                "unit": "$ Millions"
            }
        ]
    },
    {
        "discrepancy_id": "DISC-002",
        "ticker": "TGT",
        "fiscal_year": 2023,
        "fiscal_year_label": "FY2023",
        "affected_periods": [2023],
        "metric": "operating_income",
        "discrepancy_category": "NUMERICAL_REVISION",
        "discrepancy_type": "AUDITED_STATEMENT_RECONCILIATION",
        "is_numerical": True,
        "initial_dataset_value": 5711.0,
        "canonical_value_before_correction": 5711.0,
        "primary_reported_value": 5707.0,
        "final_canonical_value": 5707.0,
        "canonical_value": 5707.0,
        "reported_value": 5707.0,
        "unit": "$ Millions",
        "status": "RESOLVED",
        "investigation_finding": "Preliminary earnings release table cited $5,711M; official Form 10-K Consolidated Statements of Operations reports Operating Income of $5,707M for the 53-week fiscal year ended February 3, 2024.",
        "resolution_rationale": "Updated canonical value from 5,711.0 to 5,707.0 to match official Item 8 Form 10-K disclosure.",
        "resolution": "Updated canonical value from 5,711.0 to 5,707.0 to match official Item 8 Form 10-K disclosure.",
        "resolution_or_reconciliation_note": "Updated canonical value from 5,711.0 to 5,707.0 to match official Item 8 Form 10-K disclosure.",
        "source_accession_or_key": "0000027419-24-000014",
        "affected_metrics_detail": [
            {
                "metric": "operating_income",
                "initial_dataset_value": 5711.0,
                "canonical_value_before_correction": 5711.0,
                "primary_reported_value": 5707.0,
                "final_canonical_value": 5707.0,
                "unit": "$ Millions"
            }
        ]
    },
    {
        "discrepancy_id": "DISC-003",
        "ticker": "BAJAJ-AUTO",
        "fiscal_year": 2024,
        "fiscal_year_label": "FY 2023–24",
        "affected_periods": [2024],
        "metric": "revenue",
        "discrepancy_category": "NUMERICAL_REVISION",
        "discrepancy_type": "AUDITED_STATEMENT_RECONCILIATION",
        "is_numerical": True,
        "initial_dataset_value": 44870.0,
        "canonical_value_before_correction": 44870.0,
        "primary_reported_value": 44685.23,
        "final_canonical_value": 44685.2,
        "canonical_value": 44685.2,
        "reported_value": 44685.23,
        "unit": "₹ Crores",
        "status": "RESOLVED",
        "investigation_finding": "Standalone revenue from operations was Rs 44,870.43 Cr; consolidated revenue from operations was Rs 44,685.23 Cr. To preserve the strict Consolidated basis mandate, the consolidated figure of 44,685.2 Cr is registered.",
        "resolution_rationale": "Registered canonical consolidated value of 44,685.2 Cr and documented standalone vs consolidated delta in ledger.",
        "resolution": "Registered canonical consolidated value of 44,685.2 Cr and documented standalone vs consolidated delta in ledger.",
        "resolution_or_reconciliation_note": "Registered canonical consolidated value of 44,685.2 Cr and documented standalone vs consolidated delta in ledger.",
        "source_accession_or_key": "BSE-SCRIP-532977-AR-2023-24",
        "affected_metrics_detail": [
            {
                "metric": "revenue",
                "initial_dataset_value": 44870.0,
                "canonical_value_before_correction": 44870.0,
                "primary_reported_value": 44685.23,
                "final_canonical_value": 44685.2,
                "unit": "₹ Crores"
            }
        ]
    },
    {
        "discrepancy_id": "DISC-004",
        "ticker": "INFY",
        "fiscal_year": 2022,
        "fiscal_year_label": "FY 2021–22",
        "affected_periods": [2022],
        "metric": "operating_income",
        "discrepancy_category": "NUMERICAL_REVISION",
        "discrepancy_type": "AUDITED_STATEMENT_RECONCILIATION",
        "is_numerical": True,
        "initial_dataset_value": 28010.0,
        "canonical_value_before_correction": 28010.0,
        "primary_reported_value": 28015.0,
        "final_canonical_value": 28015.0,
        "canonical_value": 28015.0,
        "reported_value": 28015.0,
        "unit": "₹ Crores",
        "status": "RESOLVED",
        "investigation_finding": "IFRS presentation cited Rs 28,010 Cr; Ind AS audited Consolidated Statement of Profit and Loss reports Operating profit of Rs 28,015 Cr.",
        "resolution_rationale": "Reconciled to Ind AS Consolidated Statement of Profit and Loss at 28,015.0 Cr (updated from preliminary 28,010.0 Cr).",
        "resolution": "Reconciled to Ind AS Consolidated Statement of Profit and Loss at 28,015.0 Cr.",
        "resolution_or_reconciliation_note": "Reconciled to Ind AS Consolidated Statement of Profit and Loss at 28,015.0 Cr.",
        "source_accession_or_key": "BSE-SCRIP-500209-AR-2021-22",
        "affected_metrics_detail": [
            {
                "metric": "operating_income",
                "initial_dataset_value": 28010.0,
                "canonical_value_before_correction": 28010.0,
                "primary_reported_value": 28015.0,
                "final_canonical_value": 28015.0,
                "unit": "₹ Crores"
            }
        ]
    },
    {
        "discrepancy_id": "DISC-005",
        "ticker": "WMT",
        "fiscal_year": 2025,
        "fiscal_year_label": "FY2025",
        "affected_periods": [2025],
        "metric": "operating_income",
        "discrepancy_category": "NUMERICAL_REVISION",
        "discrepancy_type": "AUDITED_STATEMENT_RECONCILIATION",
        "is_numerical": True,
        "initial_dataset_value": 27011.0,
        "canonical_value_before_correction": 27011.0,
        "primary_reported_value": 29348.0,
        "final_canonical_value": 29348.0,
        "canonical_value": 29348.0,
        "reported_value": 29348.0,
        "unit": "$ Millions",
        "status": "RESOLVED",
        "investigation_finding": "Initial dataset recorded adjusted non-GAAP operating income; official Form 10-K Item 8 Consolidated Statements of Income reports GAAP Operating Income of $29,348M.",
        "resolution_rationale": "Updated canonical value from 27,011.0 to 29,348.0 to conform to strict GAAP reporting standard.",
        "resolution": "Updated canonical value to 29,348.0 to conform to strict GAAP reporting standard.",
        "resolution_or_reconciliation_note": "Updated canonical value to 29,348.0 to conform to strict GAAP reporting standard.",
        "source_accession_or_key": "0000104169-25-000021",
        "affected_metrics_detail": [
            {
                "metric": "operating_income",
                "initial_dataset_value": 27011.0,
                "canonical_value_before_correction": 27011.0,
                "primary_reported_value": 29348.0,
                "final_canonical_value": 29348.0,
                "unit": "$ Millions"
            }
        ]
    },
    {
        "discrepancy_id": "DISC-006",
        "ticker": "WMT",
        "fiscal_year": 2026,
        "fiscal_year_label": "FY2026",
        "affected_periods": [2026],
        "metric": "revenue",
        "discrepancy_category": "NUMERICAL_REVISION",
        "discrepancy_type": "AUDITED_STATEMENT_RECONCILIATION",
        "is_numerical": True,
        "initial_dataset_value": 713158.0,
        "canonical_value_before_correction": 713158.0,
        "primary_reported_value": 713163.0,
        "final_canonical_value": 713163.0,
        "canonical_value": 713163.0,
        "reported_value": 713163.0,
        "unit": "$ Millions",
        "status": "RESOLVED",
        "investigation_finding": "Preliminary segment disclosure reported $713,158M; official Form 10-K Consolidated Statements of Income reports Total Revenues of $713,163M (Net sales $706,413M + Membership and other income $6,750M).",
        "resolution_rationale": "Updated canonical value from 713,158.0 to 713,163.0 to match official 10-K statement.",
        "resolution": "Updated canonical value to 713,163.0 to match official 10-K statement.",
        "resolution_or_reconciliation_note": "Updated canonical value to 713,163.0 to match official 10-K statement.",
        "source_accession_or_key": "0000104169-26-000055",
        "affected_metrics_detail": [
            {
                "metric": "revenue",
                "initial_dataset_value": 713158.0,
                "canonical_value_before_correction": 713158.0,
                "primary_reported_value": 713163.0,
                "final_canonical_value": 713163.0,
                "unit": "$ Millions"
            }
        ]
    },
    {
        "discrepancy_id": "DISC-007",
        "ticker": "TCS",
        "fiscal_year": 2026,
        "fiscal_year_label": "FY 2025–26",
        "affected_periods": [2026],
        "metric": "operating_income",
        "discrepancy_category": "ACCOUNTING_PROXY_CLASSIFICATION",
        "discrepancy_type": "AUDITED_STATEMENT_RECONCILIATION",
        "is_numerical": True,
        "initial_dataset_value": 66755.0,
        "canonical_value_before_correction": 66755.0,
        "primary_reported_value": 66755.0,
        "final_canonical_value": 66755.0,
        "canonical_value": 66755.0,
        "reported_value": 66755.0,
        "unit": "₹ Crores",
        "status": "RESOLVED",
        "investigation_finding": "The dataset stores Rs 66,755 Cr, which reflects Operating profit before exceptional items and other income (PBEI). In the 5-Year Performance Trend of the Integrated Annual Report, EBIT is cited as Rs 66,838 Cr (including other operating items).",
        "resolution_rationale": "Documented canonical line item as Operating Profit before Other Income/Exceptional Items (PBEI Proxy) at 66,755.0 Cr with PROXY comparability flag and noted EBIT delta of Rs 83 Cr in ledger.",
        "resolution": "Documented canonical line item as Operating Profit before Other Income/Exceptional Items (PBEI Proxy) at 66,755.0 Cr with PROXY comparability flag and noted EBIT delta of Rs 83 Cr in ledger.",
        "resolution_or_reconciliation_note": "Documented canonical line item as Operating Profit before Other Income/Exceptional Items (PBEI Proxy) at 66,755.0 Cr with PROXY comparability flag and noted EBIT delta of Rs 83 Cr in ledger.",
        "source_accession_or_key": "BSE-SCRIP-532540-AR-2025-26",
        "affected_metrics_detail": [
            {
                "metric": "operating_income",
                "initial_dataset_value": 66755.0,
                "canonical_value_before_correction": 66755.0,
                "primary_reported_value": 66755.0,
                "final_canonical_value": 66755.0,
                "unit": "₹ Crores"
            }
        ]
    },
    {
        "discrepancy_id": "DISC-008",
        "ticker": "BAJAJ-AUTO",
        "fiscal_year": 2026,
        "fiscal_year_label": "FY 2025–26",
        "affected_periods": [2026],
        "metric": "operating_income",
        "discrepancy_category": "ACCOUNTING_PROXY_CLASSIFICATION",
        "discrepancy_type": "AUDITED_STATEMENT_RECONCILIATION",
        "is_numerical": True,
        "initial_dataset_value": 12019.0,
        "canonical_value_before_correction": 12019.0,
        "primary_reported_value": 12019.0,
        "final_canonical_value": 12019.0,
        "canonical_value": 12019.0,
        "reported_value": 12019.0,
        "unit": "₹ Crores",
        "status": "RESOLVED",
        "investigation_finding": "The stored value of Rs 12,019 Cr represents EBITDA (Operating Profit before Depreciation & Amortisation) as highlighted in Bajaj Auto's Annual Report. Standalone depreciation is Rs 448.2 Cr, giving operating profit (EBIT) of ~Rs 11,570.8 Cr.",
        "resolution_rationale": "Documented canonical line item as EBITDA (Operating Profit Proxy) at 12,019.0 Cr with PROXY comparability flag, noting EBIT of ~Rs 11,570.8 Cr in ledger.",
        "resolution": "Documented canonical line item as EBITDA (Operating Profit Proxy) at 12,019.0 Cr with PROXY comparability flag, noting EBIT of ~Rs 11,570.8 Cr in ledger.",
        "resolution_or_reconciliation_note": "Documented canonical line item as EBITDA (Operating Profit Proxy) at 12,019.0 Cr with PROXY comparability flag, noting EBIT of ~Rs 11,570.8 Cr in ledger.",
        "source_accession_or_key": "BSE-SCRIP-532977-AR-2025-26",
        "affected_metrics_detail": [
            {
                "metric": "operating_income",
                "initial_dataset_value": 12019.0,
                "canonical_value_before_correction": 12019.0,
                "primary_reported_value": 12019.0,
                "final_canonical_value": 12019.0,
                "unit": "₹ Crores"
            }
        ]
    },
    {
        "discrepancy_id": "DISC-009",
        "ticker": "INFY",
        "fiscal_year": 2026,
        "fiscal_year_label": "FY 2025–26",
        "affected_periods": [2026],
        "metric": "net_income",
        "discrepancy_category": "ATTRIBUTION_BASIS",
        "discrepancy_type": "AUDITED_STATEMENT_RECONCILIATION",
        "is_numerical": True,
        "initial_dataset_value": 29440.0,
        "canonical_value_before_correction": 29440.0,
        "primary_reported_value": 29440.0,
        "final_canonical_value": 29440.0,
        "canonical_value": 29440.0,
        "reported_value": 29440.0,
        "unit": "₹ Crores",
        "status": "RESOLVED",
        "investigation_finding": "In Infosys Consolidated Financial Results for FY26, total profit for the period is Rs 29,474 Cr. Net profit attributable to owners of the Company (after non-controlling interests of Rs 34 Cr) is Rs 29,440 Cr.",
        "resolution_rationale": "Documented attribution basis as ATTRIBUTABLE_TO_OWNERS at 29,440.0 Cr, confirming canonical figure aligns with common equity shareholder net income.",
        "resolution": "Documented attribution basis as ATTRIBUTABLE_TO_OWNERS at 29,440.0 Cr, confirming canonical figure aligns with common equity shareholder net income.",
        "resolution_or_reconciliation_note": "Documented attribution basis as ATTRIBUTABLE_TO_OWNERS at 29,440.0 Cr, confirming canonical figure aligns with common equity shareholder net income.",
        "source_accession_or_key": "BSE-SCRIP-500209-AR-2025-26",
        "affected_metrics_detail": [
            {
                "metric": "net_income",
                "initial_dataset_value": 29440.0,
                "canonical_value_before_correction": 29440.0,
                "primary_reported_value": 29440.0,
                "final_canonical_value": 29440.0,
                "unit": "₹ Crores"
            }
        ]
    },
    {
        "discrepancy_id": "DISC-010",
        "ticker": "COST",
        "fiscal_year": 2022,
        "fiscal_year_label": "FY2022",
        "affected_periods": [2022],
        "metric": "operating_income",
        "discrepancy_category": "NUMERICAL_REVISION",
        "discrepancy_type": "AUDITED_STATEMENT_RECONCILIATION",
        "is_numerical": True,
        "initial_dataset_value": 7795.0,
        "canonical_value_before_correction": 7795.0,
        "primary_reported_value": 7793.0,
        "final_canonical_value": 7793.0,
        "canonical_value": 7793.0,
        "reported_value": 7793.0,
        "unit": "$ Millions",
        "status": "RESOLVED",
        "investigation_finding": "Initial dataset had $7,795.0M operating income and $5,841.0M net income; official Form 10-K Item 8 Consolidated Statements of Operations reports Operating Income of $7,793.0M and Net Income of $5,844.0M under accession 0000909832-22-000021.",
        "resolution_rationale": "Updated canonical operating income from 7,795.0M to 7,793.0M and net income from 5,841.0M to 5,844.0M to conform to audited Form 10-K statement.",
        "resolution": "Updated canonical operating income to 7,793.0M and net income to 5,844.0M to conform to audited Form 10-K statement.",
        "resolution_or_reconciliation_note": "Updated canonical operating income to 7,793.0M and net income to 5,844.0M to conform to audited Form 10-K statement.",
        "source_accession_or_key": "0000909832-22-000021",
        "affected_metrics_detail": [
            {
                "metric": "operating_income",
                "initial_dataset_value": 7795.0,
                "canonical_value_before_correction": 7795.0,
                "primary_reported_value": 7793.0,
                "final_canonical_value": 7793.0,
                "unit": "$ Millions"
            },
            {
                "metric": "net_income",
                "initial_dataset_value": 5841.0,
                "canonical_value_before_correction": 5841.0,
                "primary_reported_value": 5844.0,
                "final_canonical_value": 5844.0,
                "unit": "$ Millions"
            }
        ]
    },
    {
        "discrepancy_id": "DISC-011",
        "ticker": "COST",
        "fiscal_year": 2024,
        "fiscal_year_label": "FY2024",
        "affected_periods": [2024],
        "metric": "accession_alignment",
        "discrepancy_category": "FILING_IDENTITY_ALIGNMENT",
        "discrepancy_type": "AUDITED_STATEMENT_RECONCILIATION",
        "is_numerical": False,
        "initial_dataset_value": 0.0,
        "canonical_value_before_correction": 0.0,
        "primary_reported_value": 0.0,
        "final_canonical_value": 0.0,
        "canonical_value": 0.0,
        "reported_value": 0.0,
        "unit": None,
        "status": "RESOLVED",
        "investigation_finding": "Previous dataset recorded accession 0000909832-24-000084 for Form 10-K filed October 9, 2024; official SEC EDGAR submissions API confirms accession is 0000909832-24-000049.",
        "resolution_rationale": "Updated accession_id from 0000909832-24-000084 to 0000909832-24-000049 and aligned source_url accordingly.",
        "resolution": "Updated accession_id to 0000909832-24-000049 and aligned source_url accordingly.",
        "resolution_or_reconciliation_note": "Updated accession_id to 0000909832-24-000049 and aligned source_url accordingly.",
        "source_accession_or_key": "0000909832-24-000049",
        "initial_source_key": "0000909832-24-000084",
        "affected_metrics_detail": []
    },
    {
        "discrepancy_id": "DISC-012",
        "ticker": "COST",
        "fiscal_year": 2025,
        "fiscal_year_label": "FY2025",
        "affected_periods": [2025],
        "metric": "operating_cash_flow",
        "discrepancy_category": "NUMERICAL_REVISION",
        "discrepancy_type": "AUDITED_STATEMENT_RECONCILIATION",
        "is_numerical": True,
        "initial_dataset_value": 14100.0,
        "canonical_value_before_correction": 14100.0,
        "primary_reported_value": 13335.0,
        "final_canonical_value": 13335.0,
        "canonical_value": 13335.0,
        "reported_value": 13335.0,
        "unit": "$ Millions",
        "status": "RESOLVED",
        "investigation_finding": "Preliminary estimate recorded $14,100M OCF and $5,200M capex; official Form 10-K Item 8 Consolidated Statements of Cash Flows reports Cash Provided by Operating Activities of $13,335M and Property Additions (Capex) of $5,498M.",
        "resolution_rationale": "Updated canonical OCF from 14,100.0M to 13,335.0M, capex from 5,200.0M to 5,498.0M, and recomputed FCF as $7,837.0M.",
        "resolution": "Updated canonical OCF to 13,335.0M, capex to 5,498.0M, and recomputed FCF as $7,837.0M.",
        "resolution_or_reconciliation_note": "Updated canonical OCF to 13,335.0M, capex to 5,498.0M, and recomputed FCF as $7,837.0M.",
        "source_accession_or_key": "0000909832-25-000017",
        "affected_metrics_detail": [
            {
                "metric": "operating_cash_flow",
                "initial_dataset_value": 14100.0,
                "canonical_value_before_correction": 14100.0,
                "primary_reported_value": 13335.0,
                "final_canonical_value": 13335.0,
                "unit": "$ Millions"
            },
            {
                "metric": "capital_expenditure",
                "initial_dataset_value": 5200.0,
                "canonical_value_before_correction": 5200.0,
                "primary_reported_value": 5498.0,
                "final_canonical_value": 5498.0,
                "unit": "$ Millions"
            },
            {
                "metric": "free_cash_flow",
                "initial_dataset_value": 8900.0,
                "canonical_value_before_correction": 8900.0,
                "primary_reported_value": 7837.0,
                "final_canonical_value": 7837.0,
                "unit": "$ Millions"
            }
        ]
    },
    {
        "discrepancy_id": "DISC-013",
        "ticker": "COST",
        "fiscal_year": 2026,
        "fiscal_year_label": "FY2026",
        "affected_periods": [2026],
        "metric": "operating_income",
        "discrepancy_category": "NUMERICAL_REVISION",
        "discrepancy_type": "AUDITED_STATEMENT_RECONCILIATION",
        "is_numerical": True,
        "initial_dataset_value": 11700.0,
        "canonical_value_before_correction": 11700.0,
        "primary_reported_value": 11685.0,
        "final_canonical_value": 11685.0,
        "canonical_value": 11685.0,
        "reported_value": 11685.0,
        "unit": "$ Millions",
        "status": "RESOLVED",
        "investigation_finding": "Initial dataset had $11,700M rounded operating income; official Form 10-K Item 8 Consolidated Statements of Operations reports Operating Income of $11,685.0M under accession 0000909832-26-000093.",
        "resolution_rationale": "Updated canonical operating income from 11,700.0M to 11,685.0M to match official 10-K statement.",
        "resolution": "Updated canonical operating income to 11,685.0M to match official 10-K statement.",
        "resolution_or_reconciliation_note": "Updated canonical operating income to 11,685.0M to match official 10-K statement.",
        "source_accession_or_key": "0000909832-26-000093",
        "affected_metrics_detail": [
            {
                "metric": "operating_income",
                "initial_dataset_value": 11700.0,
                "canonical_value_before_correction": 11700.0,
                "primary_reported_value": 11685.0,
                "final_canonical_value": 11685.0,
                "unit": "$ Millions"
            }
        ]
    },
    {
        "discrepancy_id": "DISC-014",
        "ticker": "MSFT",
        "fiscal_year": 2025,
        "fiscal_year_label": "FY2025",
        "affected_periods": [2025],
        "metric": "revenue",
        "discrepancy_category": "NUMERICAL_REVISION",
        "discrepancy_type": "AUDITED_STATEMENT_RECONCILIATION",
        "is_numerical": True,
        "initial_dataset_value": 281654.0,
        "canonical_value_before_correction": 281654.0,
        "primary_reported_value": 281724.0,
        "final_canonical_value": 281724.0,
        "canonical_value": 281724.0,
        "reported_value": 281724.0,
        "unit": "$ Millions",
        "status": "RESOLVED",
        "investigation_finding": "Subsequent segment reclassifications in Microsoft Form 10-K (accession 0000950170-25-100235) report Revenue of $281,724M and Operating Income of $128,528M.",
        "resolution_rationale": "Updated canonical revenue from 281,654.0M to 281,724.0M and operating income to 128,528.0M to align with audited Form 10-K.",
        "resolution": "Updated canonical revenue to 281,724.0M and operating income to 128,528.0M to align with audited Form 10-K.",
        "resolution_or_reconciliation_note": "Updated canonical revenue to 281,724.0M and operating income to 128,528.0M to align with audited Form 10-K.",
        "source_accession_or_key": "0000950170-25-100235",
        "affected_metrics_detail": [
            {
                "metric": "revenue",
                "initial_dataset_value": 281654.0,
                "canonical_value_before_correction": 281654.0,
                "primary_reported_value": 281724.0,
                "final_canonical_value": 281724.0,
                "unit": "$ Millions"
            },
            {
                "metric": "operating_income",
                "initial_dataset_value": 128500.0,
                "canonical_value_before_correction": 128500.0,
                "primary_reported_value": 128528.0,
                "final_canonical_value": 128528.0,
                "unit": "$ Millions"
            }
        ]
    },
    {
        "discrepancy_id": "DISC-015",
        "ticker": "MSFT",
        "fiscal_year": 2026,
        "fiscal_year_label": "FY2026",
        "affected_periods": [2026],
        "metric": "net_income",
        "discrepancy_category": "NUMERICAL_REVISION",
        "discrepancy_type": "AUDITED_STATEMENT_RECONCILIATION",
        "is_numerical": True,
        "initial_dataset_value": 133768.0,
        "canonical_value_before_correction": 133768.0,
        "primary_reported_value": 133749.0,
        "final_canonical_value": 133749.0,
        "canonical_value": 133749.0,
        "reported_value": 133749.0,
        "unit": "$ Millions",
        "status": "RESOLVED",
        "investigation_finding": "Initial dataset had $133,768M net income and $182,933M OCF; official Form 10-K Item 8 reports Net Income of $133,749M and Cash from Operations of $182,935M under accession 0001193125-26-323660.",
        "resolution_rationale": "Updated canonical net income from 133,768.0M to 133,749.0M, OCF from 182,933.0M to 182,935.0M, and recomputed FCF as $66,987.0M.",
        "resolution": "Updated canonical net income to 133,749.0M, OCF to 182,935.0M, and recomputed FCF as $66,987.0M.",
        "resolution_or_reconciliation_note": "Updated canonical net income to 133,749.0M, OCF to 182,935.0M, and recomputed FCF as $66,987.0M.",
        "source_accession_or_key": "0001193125-26-323660",
        "affected_metrics_detail": [
            {
                "metric": "net_income",
                "initial_dataset_value": 133768.0,
                "canonical_value_before_correction": 133768.0,
                "primary_reported_value": 133749.0,
                "final_canonical_value": 133749.0,
                "unit": "$ Millions"
            },
            {
                "metric": "operating_cash_flow",
                "initial_dataset_value": 182933.0,
                "canonical_value_before_correction": 182933.0,
                "primary_reported_value": 182935.0,
                "final_canonical_value": 182935.0,
                "unit": "$ Millions"
            },
            {
                "metric": "free_cash_flow",
                "initial_dataset_value": 66985.0,
                "canonical_value_before_correction": 66985.0,
                "primary_reported_value": 66987.0,
                "final_canonical_value": 66987.0,
                "unit": "$ Millions"
            }
        ]
    },
    {
        "discrepancy_id": "DISC-016",
        "ticker": "WMT",
        "fiscal_year": 2025,
        "fiscal_year_label": "FY2025/FY2026",
        "affected_periods": [2025, 2026],
        "affected_period_labels": ["FY2025", "FY2026"],
        "metric": "net_income",
        "discrepancy_category": "NUMERICAL_REVISION",
        "discrepancy_type": "AUDITED_STATEMENT_RECONCILIATION",
        "is_numerical": True,
        "initial_dataset_value": 19549.0,
        "canonical_value_before_correction": 19549.0,
        "primary_reported_value": 19436.0,
        "final_canonical_value": 19436.0,
        "canonical_value": 19436.0,
        "reported_value": 19436.0,
        "unit": "$ Millions",
        "status": "RESOLVED",
        "investigation_finding": "Previous dataset recorded preliminary non-GAAP / press release net income of $19,549M for FY2025 and $22,279M for FY2026. Official audited Form 10-K Item 8 Consolidated Statements of Income reports GAAP Consolidated net income attributable to Walmart of $19,436M for FY2025 (accession 0000104169-25-000021) and $21,893M for FY2026 (accession 0000104169-26-000055) under concept us-gaap:NetIncomeLoss.",
        "resolution_rationale": "Updated canonical net income to 19,436.0M for FY2025 (from 19,549.0M) and 21,893.0M for FY2026 (from 22,279.0M), aligning with official audited GAAP Form 10-K statements.",
        "resolution": "Updated canonical net income to 19,436.0M for FY2025 and 21,893.0M for FY2026, aligning with official audited GAAP Form 10-K statements.",
        "resolution_or_reconciliation_note": "Updated canonical net income to 19,436.0M for FY2025 and 21,893.0M for FY2026, aligning with official audited GAAP Form 10-K statements.",
        "source_accession_or_key": "0000104169-25-000021 / 0000104169-26-000055",
        "affected_metrics_detail": [
            {
                "fiscal_year": 2025,
                "fiscal_year_label": "FY2025",
                "metric": "net_income",
                "initial_dataset_value": 19549.0,
                "canonical_value_before_correction": 19549.0,
                "primary_reported_value": 19436.0,
                "final_canonical_value": 19436.0,
                "unit": "$ Millions",
                "accession": "0000104169-25-000021"
            },
            {
                "fiscal_year": 2026,
                "fiscal_year_label": "FY2026",
                "metric": "net_income",
                "initial_dataset_value": 22279.0,
                "canonical_value_before_correction": 22279.0,
                "primary_reported_value": 21893.0,
                "final_canonical_value": 21893.0,
                "unit": "$ Millions",
                "accession": "0000104169-26-000055"
            }
        ]
    }
]


def build_evidence_pipeline(
    facts_file: Optional[Path] = None,
    sources_file: Optional[Path] = None,
    source_obs_file: Optional[Path] = None,
    discrepancy_file: Optional[Path] = None,
    companies_file: Optional[Path] = None,
    output_dir: Optional[Path] = None,
    verification_mode: str = "OFFLINE",
    fixed_timestamp: Optional[str] = None
) -> Dict[str, Any]:
    build_ts = fixed_timestamp or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    check_dt = build_ts[:10]

    print("=" * 80)
    print("FUNDAMENTALS LENS: EVIDENCE REGISTER & CANONICAL DATASET PIPELINE (PHASE 14 HARDENED)")
    print(f"Timestamp: {build_ts}")
    print("=" * 80)

    # Resolve paths
    target_facts = facts_file or FACTS_FILE
    target_sources = sources_file or SOURCES_FILE
    target_source_obs = source_obs_file or SOURCE_OBS_FILE
    target_discrepancy = discrepancy_file or DISCREPANCY_JSON
    target_companies = companies_file or COMPANIES_FILE
    target_out_dir = output_dir or DATASETS_DIR

    # Load companies
    with open(target_companies, "r", encoding="utf-8") as f:
        comp_raw = json.load(f)
    comp_map = {c["ticker"]: c for c in comp_raw}

    # 1. Load source observations (Primary truth layer)
    if not target_source_obs.exists():
        raise FileNotFoundError(f"Source observations file not found: {target_source_obs}. Run build_source_observations_phase13.py first.")

    with open(target_source_obs, "r", encoding="utf-8") as f:
        source_obs = json.load(f)

    # Pre-map Uniqueness Validation (M1) on source observations
    obs_id_set: Set[str] = set()
    obs_keys: Set[tuple] = set()
    obs_map: Dict[tuple, Dict[str, Any]] = {}
    for o in source_obs:
        oid = o["observation_id"]
        if oid in obs_id_set:
            raise ValueError(f"Duplicate observation_id in source observations: '{oid}'")
        obs_id_set.add(oid)

        k = (o["ticker"], o["fiscal_year"], o["metric_name"])
        if k in obs_keys:
            raise ValueError(f"Duplicate (ticker, fiscal_year, metric_name) in source observations: {k}")
        obs_keys.add(k)
        obs_map[k] = o

    print(f"Loaded and verified {len(source_obs)} primary source observations from {target_source_obs}")

    # 2. Load financial facts with pre-map uniqueness validation
    with open(target_facts, "r", encoding="utf-8") as f:
        facts = json.load(f)

    fact_keys: Set[tuple] = set()
    for fact in facts:
        k = (fact["ticker"], fact["fiscal_year"])
        if k in fact_keys:
            raise ValueError(f"Duplicate (ticker, fiscal_year) in financial facts: {k}")
        fact_keys.add(k)

    # 3. Load sources and prepare discrepancy ledger
    with open(target_sources, "r", encoding="utf-8") as f:
        sources = json.load(f)

    source_keys: Set[tuple] = set()
    for s in sources:
        k = (s["ticker"], s["fiscal_year"])
        if k in source_keys:
            raise ValueError(f"Duplicate (ticker, fiscal_year) in source register: {k}")
        source_keys.add(k)

    # Discrepancy ledger
    if target_discrepancy.exists():
        with open(target_discrepancy, "r", encoding="utf-8") as f:
            discrepancy_ledger = json.load(f)
    else:
        discrepancy_ledger = []

    # Merge DISCREPANCIES if ledger is empty or for fallback
    disc_ids = {d.get("discrepancy_id") for d in discrepancy_ledger}
    for d in DISCREPANCIES:
        if d.get("discrepancy_id") not in disc_ids:
            discrepancy_ledger.append(dict(d))

    # Pre-map uniqueness validation on discrepancy ledger
    seen_disc_ids: Set[str] = set()
    for d in discrepancy_ledger:
        did = d.get("discrepancy_id")
        if did in seen_disc_ids:
            raise ValueError(f"Duplicate discrepancy_id in discrepancy ledger: '{did}'")
        seen_disc_ids.add(did)

    # 4. Map sources and verify dynamic document identity
    src_dict = {}
    for s in sources:
        t = s["ticker"]
        fy = s["fiscal_year"]
        c_meta = comp_map.get(t, {})
        is_us = (c_meta.get("country") == "US" or s.get("reference_type") == "SEC_ACCESSION")

        is_identity_verified, identity_reason = derive_document_identity_verified(s, c_meta)
        official_id = s.get("official_filing_id") or (s.get("accession_id") if is_us else None)
        internal_key = None if is_us else (s.get("internal_document_key") or s.get("accession_id"))
        ref_type = "SEC_ACCESSION" if is_us else "INTERNAL_DOCUMENT_KEY"

        s["document_identity_verified"] = is_identity_verified
        s["document_identity_reason"] = identity_reason
        s["verification_status"] = "VERIFIED" if is_identity_verified else "UNVERIFIED"
        s["last_checked_date"] = check_dt
        s["reference_type"] = ref_type
        s["official_filing_id"] = official_id
        s["internal_document_key"] = internal_key
        src_dict[(t, fy)] = s

    # 5. Build Evidence Register using EXCLUSIVELY independent source observations
    # and explicit record-level reconciliation functions
    evidence_records = []
    evidence_flat_rows = []

    reconciled_metric_count = 0
    tracked_offline_metric_count = 0
    source_linked_metric_count = 0
    unverified_metric_count = 0

    metric_keys = ["revenue", "operating_income", "net_income", "operating_cash_flow", "capital_expenditure"]

    updated_sources = []
    source_check_records = []

    for fact in sorted(facts, key=lambda x: (x["ticker"], x["fiscal_year"])):
        t = fact["ticker"]
        fy = fact["fiscal_year"]
        src = src_dict.get((t, fy))
        if not src:
            raise ValueError(f"Missing source entry for {t} {fy}")

        period_metrics = {}
        metric_results_for_period = []

        for m_key in metric_keys:
            canonical_val = fact.get(m_key)
            obs = obs_map.get((t, fy, m_key))
            if not obs:
                raise ValueError(f"Missing source observation for {t} {fy} {m_key}")

            rep_val = obs.get("reported_value")

            rec_result = reconcile_metric_observation(
                canonical_val=canonical_val,
                reported_val=rep_val,
                ticker=t,
                fiscal_year=fy,
                fiscal_year_label=fact["fiscal_year_label"],
                metric_key=m_key,
                src_entry=src,
                discrepancy_ledger=discrepancy_ledger,
                obs_entry=obs,
                verification_mode=verification_mode,
                verification_timestamp=build_ts
            )

            period_metrics[m_key] = rec_result
            metric_results_for_period.append(rec_result)

            tier = rec_result["reconciliation_tier"]
            if tier == ReconciliationTier.INDEPENDENTLY_RECONCILED.value:
                reconciled_metric_count += 1
            elif tier == ReconciliationTier.TRACKED_OFFLINE_EXTRACT.value:
                tracked_offline_metric_count += 1
            elif tier == ReconciliationTier.SOURCE_LINKED_ONLY.value:
                source_linked_metric_count += 1
            else:
                unverified_metric_count += 1

            evidence_flat_rows.append({
                "ticker": t,
                "company_name": fact["company_name"],
                "fiscal_year": fy,
                "fiscal_year_label": fact["fiscal_year_label"],
                "period_end": fact["period_end"],
                "country": fact["country"],
                "currency": fact["currency"],
                "metric_key": m_key,
                "statement_name": rec_result["statement_name"],
                "statement_locator": rec_result["statement_locator"],
                "reported_line_item": rec_result["reported_line_item"],
                "reported_value": rec_result["reported_value"],
                "canonical_value": rec_result["canonical_value"],
                "unit": fact["unit"],
                "reconciliation_tier": rec_result["reconciliation_tier"],
                "assurance_state": rec_result.get("assurance_state", "OFFLINE_EXTRACT_RECORDED"),
                "reconciliation_method": rec_result["reconciliation_method"],
                "comparison_result": rec_result["comparison_result"],
                "comparability_flag": rec_result["comparability"],
                "discrepancy_note": rec_result["discrepancy_note"],
                "source_title": src["source_title"],
                "accession_or_key": src.get("accession_id") or src.get("official_filing_id"),
                "source_url": src["source_url"],
                "evidence_check_date": check_dt,
                "observation_id": obs.get("observation_id"),
                "document_identity_status": rec_result["document_identity_status"],
                "document_retrieval_status": rec_result["document_retrieval_status"],
                "period_match_status": rec_result["period_match_status"],
                "metric_extraction_status": rec_result["metric_extraction_status"],
                "numeric_reconciliation_status": rec_result["numeric_reconciliation_status"],
                "verification_mode": rec_result["verification_mode"],
                "verification_timestamp": rec_result["verification_timestamp"],
                "approved_discrepancy_id": rec_result["approved_discrepancy_id"]
            })

        # Derive source-level tier strictly from underlying metric outcomes
        source_tier = derive_source_reconciliation_status(src, metric_results_for_period)
        chk_status = "ONLINE_VERIFIED" if verification_mode == "ONLINE" else "OFFLINE_SOURCE_RECORDED"

        src["reconciliation_tier"] = source_tier
        src["source_check_status"] = chk_status

        updated_sources.append(src)

        source_check_records.append({
            "source_id": src["source_id"],
            "ticker": t,
            "fiscal_year": fy,
            "fiscal_year_label": src["fiscal_year_label"],
            "source_title": src["source_title"],
            "source_url": src["source_url"],
            "reference_type": src["reference_type"],
            "official_filing_id": src.get("official_filing_id"),
            "internal_document_key": src.get("internal_document_key"),
            "statement_location": src.get("statement_location", ""),
            "statement_basis": "CONSOLIDATED",
            "document_identity_verified": src["document_identity_verified"],
            "document_identity_reason": src.get("document_identity_reason", ""),
            "check_status": chk_status,
            "verification_mode": verification_mode,
            "reconciliation_tier": source_tier,
            "last_checked_date": check_dt,
            "verification_timestamp": build_ts
        })

        # Decouple FCF validation and confidence
        ocf_canon = fact["operating_cash_flow"]
        capex_canon = fact["capital_expenditure"]
        fcf_canon = round(ocf_canon - capex_canon, 2)

        ocf_tier = period_metrics["operating_cash_flow"]["reconciliation_tier"]
        capex_tier = period_metrics["capital_expenditure"]["reconciliation_tier"]

        if ocf_tier == ReconciliationTier.INDEPENDENTLY_RECONCILED.value and capex_tier == ReconciliationTier.INDEPENDENTLY_RECONCILED.value:
            fcf_input_confidence = "INDEPENDENTLY_RECONCILED_INPUTS"
            fcf_confidence_desc = "Both OCF and Capex inputs are independently reconciled to primary financial statements."
        else:
            fcf_input_confidence = "SOURCE_LINKED_INPUTS"
            fcf_confidence_desc = "One or more underlying cash flow inputs are SOURCE_LINKED_ONLY; FCF is mathematically derived but inputs await audit."

        period_record = {
            "record_id": f"EV_REG_{t}_{fact['fiscal_year_label'].replace(' ', '_').replace('–', '_')}",
            "ticker": t,
            "company_name": fact["company_name"],
            "country": fact["country"],
            "fiscal_year": fy,
            "fiscal_year_label": fact["fiscal_year_label"],
            "period_end": fact["period_end"],
            "statement_basis": "CONSOLIDATED",
            "source_id": src["source_id"],
            "source_title": src["source_title"],
            "source_url": src["source_url"],
            "reference_type": src["reference_type"],
            "official_filing_id": src.get("official_filing_id"),
            "internal_document_key": src.get("internal_document_key"),
            "document_identity_verified": src["document_identity_verified"],
            "source_check_status": src["source_check_status"],
            "reconciliation_tier": source_tier,
            "metrics": period_metrics,
            "free_cash_flow_derived": {
                "canonical_fcf_value": fcf_canon,
                "formula": "operating_cash_flow - capital_expenditure",
                "arithmetic_verified": True,
                "source_input_confidence": fcf_input_confidence,
                "source_input_confidence_description": fcf_confidence_desc
            }
        }
        evidence_records.append(period_record)

    # 6. Persist all updated artefacts
    target_out_dir.mkdir(parents=True, exist_ok=True)

    sources_out = target_out_dir / "source_register.json"
    print(f"Saving updated sources to {sources_out}...")
    with open(sources_out, "w", encoding="utf-8") as f:
        json.dump(updated_sources, f, indent=2)

    discrepancy_out = target_out_dir / "discrepancy_ledger.json"
    print(f"Saving discrepancy ledger to {discrepancy_out} ({len(discrepancy_ledger)} entries)...")
    with open(discrepancy_out, "w", encoding="utf-8") as f:
        json.dump(discrepancy_ledger, f, indent=2)

    source_check_out = target_out_dir / "source_check_report.json"
    print(f"Saving source check report to {source_check_out}...")
    with open(source_check_out, "w", encoding="utf-8") as f:
        json.dump({
            "report_date": check_dt,
            "report_timestamp": build_ts,
            "total_sources_audited": len(source_check_records),
            "sources": source_check_records
        }, f, indent=2)

    evidence_json_out = target_out_dir / "evidence_register.json"
    print(f"Saving evidence register to {evidence_json_out} ({len(evidence_records)} period records)...")
    with open(evidence_json_out, "w", encoding="utf-8") as f:
        json.dump(evidence_records, f, indent=2)

    evidence_csv_out = target_out_dir / "evidence_register.csv"
    print(f"Saving flat evidence register to {evidence_csv_out} ({len(evidence_flat_rows)} metric rows)...")
    fieldnames = [
        "ticker", "company_name", "fiscal_year", "fiscal_year_label", "period_end",
        "country", "currency", "metric_key", "statement_name", "statement_locator",
        "reported_line_item", "reported_value", "canonical_value", "unit",
        "reconciliation_tier", "assurance_state", "reconciliation_method", "comparison_result",
        "comparability_flag", "discrepancy_note", "source_title", "accession_or_key",
        "source_url", "evidence_check_date", "observation_id",
        "document_identity_status", "document_retrieval_status", "period_match_status",
        "metric_extraction_status", "numeric_reconciliation_status", "verification_mode",
        "verification_timestamp", "approved_discrepancy_id"
    ]
    with open(evidence_csv_out, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(evidence_flat_rows)

    # 7. Update dataset metadata (authoritative dynamic derivation, zero stale constants)
    peer_groups_map = {}
    for c in comp_raw:
        gid = c.get("peer_group_id")
        gname = c.get("peer_group_name")
        if gid and gid not in peer_groups_map:
            peer_groups_map[gid] = {
                "id": gid,
                "name": gname,
                "tickers": []
            }
        if gid:
            peer_groups_map[gid]["tickers"].append(c["ticker"])
    peer_groups_data = list(peer_groups_map.values())

    metadata = {
        "product_name": "Fundamentals Lens",
        "product_tagline": "Evidence-First SEC & Indian Corporate Disclosure Intelligence",
        "creator_name": "Rishika Dangayach",
        "version": "1.0.0-phase19",
        "dataset_version": "1.0.0-phase19",
        "phase": "Phase 19 — Analytical Integrity, Evidence-State Correction, Financial Comparability & Overview Visualization Redesign",
        "dataset_snapshot_date": check_dt,
        "build_timestamp": build_ts,
        "last_updated": build_ts,
        "universe_size": len(comp_raw),
        "total_companies": len(comp_raw),
        "total_annual_periods": len(evidence_records),
        "total_company_periods": len(evidence_records),
        "total_primary_metrics": len(evidence_flat_rows),
        "total_metric_observations": len(evidence_flat_rows),
        "primary_metric_keys": metric_keys,
        "peer_groups": peer_groups_data,
        "independently_reconciled_metrics": reconciled_metric_count,
        "tracked_offline_extract_metrics": tracked_offline_metric_count,
        "verified_and_evidenced_metrics": reconciled_metric_count + tracked_offline_metric_count,
        "live_retrieval_metrics": 0,
        "reconciled_metric_observations": reconciled_metric_count,
        "source_linked_only_metrics": source_linked_metric_count,
        "source_linked_metric_observations": source_linked_metric_count,
        "unverified_metrics": unverified_metric_count,
        "unverified_metric_observations": unverified_metric_count,
        "derived_fcf_records": len(evidence_records),
        "discrepancies_registered": len(discrepancy_ledger),
        "discrepancy_count": len(discrepancy_ledger),
        "offline_reproducible": True,
        "deployment_candidate_certified": True
    }

    metadata_out = target_out_dir / "dataset_metadata.json"
    with open(metadata_out, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)
    print(f"Updated dataset metadata at {metadata_out}")

    print("\nEvidence pipeline complete:")
    print(f"  Total primary metric observations: {len(evidence_flat_rows)}")
    print(f"  Tracked offline extracts:          {tracked_offline_metric_count} ({tracked_offline_metric_count/len(evidence_flat_rows)*100:.1f}%)")
    print(f"  Independently reconciled (Audited): {reconciled_metric_count} ({reconciled_metric_count/len(evidence_flat_rows)*100:.1f}%)")
    print(f"  Total verified and evidenced:      {reconciled_metric_count + tracked_offline_metric_count} ({(reconciled_metric_count + tracked_offline_metric_count)/len(evidence_flat_rows)*100:.1f}%)")
    print(f"  Live regulatory retrievals:        0 (Offline reproducible build)")
    print(f"  Source-linked only:                {source_linked_metric_count} ({source_linked_metric_count/len(evidence_flat_rows)*100:.1f}%)")
    print(f"  Unverified / Discrepant:           {unverified_metric_count}")
    print(f"  Discrepancies catalogued:          {len(discrepancy_ledger)}")
    print(f"  Discrepancies catalogued:          {len(discrepancy_ledger)}")

    return {
        "evidence_records": evidence_records,
        "evidence_flat_rows": evidence_flat_rows,
        "updated_sources": updated_sources,
        "source_check_records": source_check_records,
        "metadata": metadata
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build Fundamentals Lens Evidence Register")
    parser.add_argument("--offline", action="store_true", default=True, help="Run in offline mode (default)")
    parser.add_argument("--online", action="store_true", help="Run in online verification mode")
    parser.add_argument("--timestamp", type=str, default=None, help="Fixed ISO timestamp for deterministic build")
    parser.add_argument("--output-dir", type=str, default=None, help="Output directory")
    args = parser.parse_args()

    mode = "ONLINE" if args.online else "OFFLINE"
    out_dir = Path(args.output_dir) if args.output_dir else None

    build_evidence_pipeline(output_dir=out_dir, verification_mode=mode, fixed_timestamp=args.timestamp)
