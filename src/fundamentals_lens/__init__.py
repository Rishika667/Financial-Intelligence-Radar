"""
Fundamentals Lens: High-integrity financial data foundation and analytical research engine.
"""

from .models import (
    Company,
    FinancialFact,
    DerivedMetrics,
    ValidationResult,
    ValidationStatus,
    DataQualityState,
    VerificationTier,
    SourceReferenceType,
    ComparabilityFlag,
    MetricEvidence
)
from .data_loader import (
    load_companies,
    load_financial_facts,
    load_source_register,
    load_coverage_report,
    load_evidence_register,
    load_discrepancy_ledger,
    load_dataset_metadata,
    load_ohlcv_manifest,
    get_company_by_ticker,
    get_facts_for_company
)
from .metrics import (
    calculate_revenue_growth,
    calculate_operating_margin,
    calculate_net_margin,
    calculate_free_cash_flow,
    calculate_cash_conversion,
    compute_derived_metrics_for_company
)
from .validator import FundamentalsValidator
from .insights import FinancialInsight, NarrativeEngine
from .peers import PeerComparisonEngine, PeerGroupMetadata
from .exports import ExportGenerator

__all__ = [
    "Company",
    "FinancialFact",
    "DerivedMetrics",
    "ValidationResult",
    "ValidationStatus",
    "DataQualityState",
    "load_companies",
    "load_financial_facts",
    "load_source_register",
    "load_coverage_report",
    "load_evidence_register",
    "load_discrepancy_ledger",
    "load_dataset_metadata",
    "load_ohlcv_manifest",
    "get_company_by_ticker",
    "get_facts_for_company",
    "calculate_revenue_growth",
    "calculate_operating_margin",
    "calculate_net_margin",
    "calculate_free_cash_flow",
    "calculate_cash_conversion",
    "compute_derived_metrics_for_company",
    "FundamentalsValidator",
    "FinancialInsight",
    "NarrativeEngine",
    "PeerComparisonEngine",
    "PeerGroupMetadata",
    "ExportGenerator"
]
