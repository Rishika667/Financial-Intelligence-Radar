from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum

class DataQuality(str, Enum):
    REPORTED="REPORTED"; DERIVED="DERIVED"; NOT_REPORTED="NOT_REPORTED"; NOT_APPLICABLE="NOT_APPLICABLE"
    MAPPING_UNRESOLVED="MAPPING_UNRESOLVED"; EXTRACTION_FAILED="EXTRACTION_FAILED"; PERIOD_UNAVAILABLE="PERIOD_UNAVAILABLE"
    CALCULATION_INVALID="CALCULATION_INVALID"; COMPARABILITY_SUPPRESSED="COMPARABILITY_SUPPRESSED"; AMENDED="AMENDED"; RESTATED="RESTATED"

@dataclass(frozen=True)
class Provenance:
    accession: str; source_url: str; filing_date: date; form: str; concept: str; retrieval_timestamp: datetime
    raw_value: float | None = None; mapping_version: str = "v1"; period_start: date | None = None

@dataclass(frozen=True)
class Observation:
    company: str; metric: str; value: float | None; unit: str; period_end: date; period_type: str; quality: DataQuality
    provenance: tuple[Provenance, ...] = (); derived_from: tuple[str, ...] = (); comparable: bool = True; comparability_reason: str | None = None; period_start: date | None = None

@dataclass(frozen=True)
class Signal:
    signal_id: str; company: str; severity: str; confidence: str; explanation: str; evidence: tuple[Observation, ...]
    version: str = "v1"; suppressed_reason: str | None = None
    component_signal_ids: tuple[str, ...] = ()
    @property
    def actionable(self): return self.suppressed_reason is None
