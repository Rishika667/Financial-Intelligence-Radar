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
    comparability_flag: str = "DIRECT"
    accounting_notes: str = ""
    reconciliation_tier: str = "INDEPENDENTLY_RECONCILED"


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
