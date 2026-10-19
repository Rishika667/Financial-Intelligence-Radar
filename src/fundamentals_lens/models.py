from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List, Dict, Any


class ValidationStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    WARNING = "WARNING"
    UNVERIFIED = "UNVERIFIED"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class DataQualityState(str, Enum):
    AUDITED_REPORTED = "AUDITED_REPORTED"
    RESTATED = "RESTATED"
    DERIVED_RECONCILED = "DERIVED_RECONCILED"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


class VerificationTier(str, Enum):
    INDEPENDENTLY_RECONCILED = "INDEPENDENTLY_RECONCILED"
    TRACKED_OFFLINE_EXTRACT = "TRACKED_OFFLINE_EXTRACT"
    SOURCE_LINKED_ONLY = "SOURCE_LINKED_ONLY"
    UNVERIFIED = "UNVERIFIED"
    FAILED = "FAILED"
    DERIVED_VERIFIED = "DERIVED_VERIFIED"


class AssuranceState(str, Enum):
    SOURCE_REFERENCE_RECORDED = "SOURCE_REFERENCE_RECORDED"
    SOURCE_IDENTITY_CHECKED = "SOURCE_IDENTITY_CHECKED"
    OFFLINE_EXTRACT_RECORDED = "OFFLINE_EXTRACT_RECORDED"
    DOCUMENT_SNAPSHOT_HASHED = "DOCUMENT_SNAPSHOT_HASHED"
    PRIMARY_STATEMENT_LINE_ITEM_AUDITED = "PRIMARY_STATEMENT_LINE_ITEM_AUDITED"
    LIVE_RETRIEVAL_SUCCEEDED = "LIVE_RETRIEVAL_SUCCEEDED"
    APPROVED_ADJUSTMENT_RESOLVED = "APPROVED_ADJUSTMENT_RESOLVED"
    PENDING_OR_DISCREPANT = "PENDING_OR_DISCREPANT"


def normalize_verification_tier(tier: Optional[str]) -> str:
    if not tier:
        return VerificationTier.UNVERIFIED.value
    t_upper = tier.strip().upper()
    if t_upper in ("SOURCE_LINKED_AUDITED", "SOURCE_LINKED", "SOURCE_LINKED_ONLY"):
        return VerificationTier.SOURCE_LINKED_ONLY.value
    if t_upper in ("TRACKED_OFFLINE_EXTRACT", "OFFLINE_EXTRACT", "TRACKED_EXTRACT", "OFFLINE_AUDITED"):
        return VerificationTier.TRACKED_OFFLINE_EXTRACT.value
    if t_upper in ("INDEPENDENTLY_RECONCILED", "AUDITED_RECONCILED"):
        return VerificationTier.INDEPENDENTLY_RECONCILED.value
    if t_upper in ("DERIVED_VERIFIED", "DERIVED_RECONCILED", "DERIVED"):
        return VerificationTier.DERIVED_VERIFIED.value
    if t_upper == "FAILED":
        return VerificationTier.FAILED.value
    return VerificationTier.UNVERIFIED.value


class SourceReferenceType(str, Enum):
    SEC_ACCESSION = "SEC_ACCESSION"
    INTERNAL_DOCUMENT_KEY = "INTERNAL_DOCUMENT_KEY"
    EXCHANGE_FILING_ID = "EXCHANGE_FILING_ID"


class ComparabilityFlag(str, Enum):
    DIRECT = "DIRECT"
    PROXY = "PROXY"
    LIMITED = "LIMITED"
    UNKNOWN = "UNKNOWN"


@dataclass
class ValidationResult:
    rule_id: str
    rule_name: str
    status: ValidationStatus
    message: str
    details: Dict[str, Any] = field(default_factory=dict)
    dimension: str = "STRUCTURAL"


@dataclass
class Company:
    ticker: str
    name: str
    peer_group_id: str
    peer_group_name: str
    country: str
    exchange: str
    reporting_currency: str
    standard_unit_label: str
    scale_multiplier: int
    fiscal_year_end_month: str
    primary_source_url: str
    business_description: str
    peer_notes: str
    cik: Optional[str] = None
    bse_scrip: Optional[str] = None
    nse_symbol: Optional[str] = None


@dataclass
class FinancialFact:
    ticker: str
    company_name: str
    peer_group_id: str
    country: str
    currency: str
    unit: str
    scale_multiplier: int
    fiscal_year: int
    fiscal_year_label: str
    period_start: str
    period_end: str
    statement_basis: str
    revenue: float
    operating_income: float
    net_income: float
    operating_cash_flow: float
    capital_expenditure: float
    source_id: str
    source_title: str
    source_url: str
    filing_date: str
    statement_location: str
    accession_id: str
    reported_status: str
    verification_status: str
    notes: str = ""
    comparability_flag: str = "UNKNOWN"
    accounting_notes: str = ""
    reconciliation_tier: str = "UNVERIFIED"
    official_filing_id: Optional[str] = None
    internal_document_key: Optional[str] = None
    reference_type: str = "SEC_ACCESSION"


@dataclass
class MetricEvidence:
    metric_key: str
    statement_name: str
    reported_line_item: str
    reported_value: float
    reported_unit: str
    reported_sign: str
    canonical_value: float
    canonical_unit: str
    conversion_formula: str
    statement_locator: str
    reconciliation_tier: str
    reconciliation_method: str
    comparison_result: str
    discrepancy_note: str = ""
    evidence_check_date: Optional[str] = None
    comparability: str = "UNKNOWN"
    definition_type: Optional[str] = None
    attribution_basis: Optional[str] = None
    scope_type: Optional[str] = None
    notes: str = ""


@dataclass
class DerivedMetrics:
    ticker: str
    fiscal_year: int
    fiscal_year_label: str
    revenue_growth_yoy: Optional[float]
    operating_margin: Optional[float]
    net_margin: Optional[float]
    free_cash_flow: Optional[float]
    cash_conversion_ratio: Optional[float]
    cash_conversion_qualified_reason: Optional[str] = None
    operating_margin_change_bps: Optional[float] = None
    net_margin_change_bps: Optional[float] = None
    fcf_margin: Optional[float] = None
    capex_intensity: Optional[float] = None
    reinvestment_rate: Optional[float] = None
    operating_leverage: Optional[float] = None


@dataclass
class OHLCVBar:
    date: str
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass
class TechnicalIndicators:
    date: str
    close: float
    volume: float
    sma_20: Optional[float] = None
    sma_50: Optional[float] = None
    sma_200: Optional[float] = None
    rsi_14: Optional[float] = None
    macd: Optional[float] = None
    macd_signal: Optional[float] = None
    macd_hist: Optional[float] = None
    bb_upper: Optional[float] = None
    bb_middle: Optional[float] = None
    bb_lower: Optional[float] = None
    atr_14: Optional[float] = None
    daily_return: Optional[float] = None


class PriceAdjustmentBasis(str, Enum):
    SPLIT_AND_DIVIDEND_ADJUSTED = "SPLIT_AND_DIVIDEND_ADJUSTED"
    SPLIT_ADJUSTED_ONLY = "SPLIT_ADJUSTED_ONLY"
    RAW_UNADJUSTED = "RAW_UNADJUSTED"
    SYNTHETIC_SIMULATION_NOT_APPLICABLE = "SYNTHETIC_SIMULATION_NOT_APPLICABLE"
    UNKNOWN = "UNKNOWN"


@dataclass
class OHLCVValidationReport:
    is_valid: bool
    total_rows: int
    valid_rows: int
    error_count: int
    warning_count: int
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    sample_offending_rows: List[Dict[str, Any]] = field(default_factory=list)
    duplicate_dates: List[str] = field(default_factory=list)
    non_finite_dates: List[str] = field(default_factory=list)
    invariant_violation_dates: List[str] = field(default_factory=list)
    ticker: Optional[str] = None
    price_adjustment_basis: PriceAdjustmentBasis = PriceAdjustmentBasis.UNKNOWN
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    invariants_checked: List[str] = field(default_factory=list)

    @property
    def duplicate_dates_count(self) -> int:
        return len(self.duplicate_dates)

    @property
    def violations(self) -> List[str]:
        return self.errors


@dataclass
class TechnicalSummary:
    ticker: str
    last_date: str
    last_close: Optional[float] = None
    total_bars: int = 0
    change_1m: Optional[float] = None
    change_3m: Optional[float] = None
    change_6m: Optional[float] = None
    change_1y: Optional[float] = None
    high_52w: Optional[float] = None
    low_52w: Optional[float] = None
    dist_from_52w_high: Optional[float] = None
    dist_from_52w_low: Optional[float] = None
    annualized_volatility: Optional[float] = None
    max_drawdown: Optional[float] = None
    current_rsi: Optional[float] = None
    rsi_status: str = "NEUTRAL"
    sma_20_status: str = "N/A"
    sma_50_status: str = "N/A"
    sma_200_status: str = "N/A"
    benchmark_ticker: Optional[str] = None
    benchmark_change_1y: Optional[float] = None
    relative_performance_1y: Optional[float] = None
    is_simulated_demo: bool = False
    is_full_52w: bool = True
    common_benchmark_bars: Optional[int] = None
    common_benchmark_start: Optional[str] = None
    common_benchmark_end: Optional[str] = None
    benchmark_period_return: Optional[float] = None
    relative_performance_period: Optional[float] = None
    price_adjustment_basis: str = "UNKNOWN"
    currency: str = "USD"
    coverage_start_date: Optional[str] = None
    coverage_end_date: Optional[str] = None
    coverage_calendar_days: Optional[int] = None
    max_consecutive_gap_days: Optional[int] = None
    has_adequate_calendar_coverage: bool = False

