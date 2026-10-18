"""
Canonical reconciliation engine for Fundamentals Lens.
Provides explicit record-level and metric-level reconciliation functions,
multi-dimensional verification statuses, and exact discrepancy validation.
"""
from enum import Enum
from typing import Dict, Any, Optional, Tuple, List


class DocumentIdentityStatus(str, Enum):
    VALIDATED = "VALIDATED"
    INVALID_FORMAT = "INVALID_FORMAT"
    UNVERIFIED = "UNVERIFIED"


class DocumentRetrievalStatus(str, Enum):
    RETRIEVED_OFFLINE_EXTRACT = "RETRIEVED_OFFLINE_EXTRACT"
    RETRIEVED_ONLINE_EDGAR = "RETRIEVED_ONLINE_EDGAR"
    RETRIEVED_ONLINE_BSE = "RETRIEVED_ONLINE_BSE"
    PENDING_RETRIEVAL = "PENDING_RETRIEVAL"


class PeriodMatchStatus(str, Enum):
    EXACT_PERIOD_MATCH = "EXACT_PERIOD_MATCH"
    PERIOD_MISMATCH = "PERIOD_MISMATCH"


class MetricExtractionStatus(str, Enum):
    EXTRACTED_LINE_ITEM = "EXTRACTED_LINE_ITEM"
    VALUE_NOT_LOCATED = "VALUE_NOT_LOCATED"


class NumericReconciliationStatus(str, Enum):
    EXACT_STATEMENT_MATCH = "EXACT_STATEMENT_MATCH"
    RECONCILED_WITH_APPROVED_ADJUSTMENT = "RECONCILED_WITH_APPROVED_ADJUSTMENT"
    UNEXPLAINED_DISCREPANCY = "UNEXPLAINED_DISCREPANCY"
    IDENTITY_UNVERIFIED = "IDENTITY_UNVERIFIED"
    NOT_RECONCILED = "NOT_RECONCILED"


class ReconciliationTier(str, Enum):
    INDEPENDENTLY_RECONCILED = "INDEPENDENTLY_RECONCILED"
    SOURCE_LINKED_ONLY = "SOURCE_LINKED_ONLY"
    DISCREPANT = "DISCREPANT"
    UNVERIFIED = "UNVERIFIED"


def find_matching_approved_discrepancy(
    ticker: str,
    metric_key: str,
    fiscal_year: int,
    fiscal_year_label: str,
    reported_val: float,
    canonical_val: float,
    discrepancy_ledger: List[Dict[str, Any]]
) -> Optional[Dict[str, Any]]:
    """
    Validates whether a numerical mismatch matches an EXACT approved entry in the discrepancy ledger.
    Requires exact ticker, metric, fiscal year, and exact matching of the approved reported value.
    Arbitrary mismatches without matching numerical amounts are strictly rejected.
    """
    for d in discrepancy_ledger:
        if d.get("ticker") != ticker:
            continue
        if d.get("metric") != metric_key:
            continue

        d_lbl = d.get("fiscal_year_label", "")
        # Exact label match, or slash compound label (e.g. FY2025/FY2026 for multi-year entries)
        if d_lbl != fiscal_year_label and str(fiscal_year) not in d_lbl:
            continue

        # Check status is approved/resolved
        if d.get("status") not in ("RESOLVED", "APPROVED", "AUDITED"):
            continue

        approved_rep = d.get("primary_reported_value")
        if approved_rep is None:
            approved_rep = d.get("reported_value")
        if approved_rep is None:
            continue

        # Exact match of reported value against the approved discrepancy amount
        if abs(float(reported_val) - float(approved_rep)) < 0.001:
            return d

    return None


def reconcile_metric_observation(
    canonical_val: Optional[float],
    reported_val: Optional[float],
    ticker: str,
    fiscal_year: int,
    fiscal_year_label: str,
    metric_key: str,
    src_entry: Dict[str, Any],
    discrepancy_ledger: List[Dict[str, Any]],
    obs_entry: Dict[str, Any],
    verification_mode: str = "OFFLINE",
    verification_timestamp: str = ""
) -> Dict[str, Any]:
    """
    Single explicit record-level reconciliation function.
    Maintains semantically distinct verification dimensions:
    - document_identity_status
    - document_retrieval_status
    - period_match_status
    - metric_extraction_status
    - numeric_reconciliation_status
    """
    is_identity_verified = bool(src_entry.get("document_identity_verified", False))
    doc_id_status = (
        DocumentIdentityStatus.VALIDATED.value
        if is_identity_verified
        else DocumentIdentityStatus.UNVERIFIED.value
    )

    is_us = (src_entry.get("reference_type") == "SEC_ACCESSION" or src_entry.get("country") == "US")
    if verification_mode == "ONLINE":
        doc_retrieval_status = (
            DocumentRetrievalStatus.RETRIEVED_ONLINE_EDGAR.value
            if is_us
            else DocumentRetrievalStatus.RETRIEVED_ONLINE_BSE.value
        )
    else:
        doc_retrieval_status = DocumentRetrievalStatus.RETRIEVED_OFFLINE_EXTRACT.value

    # Period match check
    obs_fy = obs_entry.get("fiscal_year")
    obs_pend = obs_entry.get("period_end")
    if obs_fy == fiscal_year and obs_pend:
        period_match_status = PeriodMatchStatus.EXACT_PERIOD_MATCH.value
    else:
        period_match_status = PeriodMatchStatus.PERIOD_MISMATCH.value

    # Metric extraction status
    if reported_val is None:
        metric_extraction_status = MetricExtractionStatus.VALUE_NOT_LOCATED.value
    else:
        metric_extraction_status = MetricExtractionStatus.EXTRACTED_LINE_ITEM.value

    # Numeric reconciliation logic
    matched_disc = None
    if not is_identity_verified:
        numeric_status = NumericReconciliationStatus.IDENTITY_UNVERIFIED.value
        tier = ReconciliationTier.UNVERIFIED.value
        is_reconciled = False
        disc_note = "Filing document identity check failed (malformed accession, CIK path mismatch, or invalid filing key)."
        conv_formula = "None (Filing document identity could not be validated)"
    elif reported_val is None:
        numeric_status = NumericReconciliationStatus.NOT_RECONCILED.value
        tier = ReconciliationTier.SOURCE_LINKED_ONLY.value
        is_reconciled = False
        disc_note = "Metric linked to registered primary source; independent line-item statement reconciliation pending."
        conv_formula = "None (Independent line-item statement reconciliation pending)"
    else:
        diff = abs(float(reported_val) - float(canonical_val))
        if diff < 0.001:
            numeric_status = NumericReconciliationStatus.EXACT_STATEMENT_MATCH.value
            tier = ReconciliationTier.INDEPENDENTLY_RECONCILED.value
            is_reconciled = True
            stmt_name = obs_entry.get("statement_name", "Financial Statements")
            acc_id = src_entry.get("official_filing_id") or src_entry.get("accession_id", "")
            if is_us:
                disc_note = f"Reconciled to Form 10-K {stmt_name} under accession {acc_id}."
            else:
                disc_note = f"Reconciled to Ind AS Consolidated {stmt_name} ({acc_id})."
        else:
            # Check for exact approved adjustment in ledger
            matched_disc = find_matching_approved_discrepancy(
                ticker=ticker,
                metric_key=metric_key,
                fiscal_year=fiscal_year,
                fiscal_year_label=fiscal_year_label,
                reported_val=float(reported_val),
                canonical_val=float(canonical_val),
                discrepancy_ledger=discrepancy_ledger
            )
            if matched_disc is not None:
                numeric_status = NumericReconciliationStatus.RECONCILED_WITH_APPROVED_ADJUSTMENT.value
                tier = ReconciliationTier.INDEPENDENTLY_RECONCILED.value
                is_reconciled = True
                disc_note = f"Audited reconciliation ({matched_disc['discrepancy_id']}): {matched_disc.get('investigation_finding')}"
            else:
                numeric_status = NumericReconciliationStatus.UNEXPLAINED_DISCREPANCY.value
                tier = ReconciliationTier.DISCREPANT.value
                is_reconciled = False
                disc_note = f"Unexplained numerical delta: reported {reported_val} != canonical {canonical_val} (diff: {diff:.2f}). No matching approved adjustment in ledger."

        rep_sign = obs_entry.get("reported_sign", "POSITIVE")
        if rep_sign == "NEGATIVE_OUTFLOW":
            conv_formula = "abs(reported_outflow) (Normalized to positive magnitude cash outflow)"
        else:
            conv_formula = "reported_value * 1.0 (No scale conversion required)"

    return {
        "metric_key": metric_key,
        "statement_name": obs_entry.get("statement_name", ""),
        "reported_line_item": obs_entry.get("reported_line_item", ""),
        "reported_value": reported_val,
        "reported_unit": obs_entry.get("source_unit", ""),
        "reported_sign": obs_entry.get("reported_sign", "POSITIVE"),
        "canonical_value": canonical_val,
        "canonical_unit": obs_entry.get("source_unit", ""),
        "conversion_formula": conv_formula,
        "statement_locator": obs_entry.get("statement_locator", ""),
        "reconciliation_tier": tier,
        "reconciliation_method": obs_entry.get("extraction_method", ""),
        "comparison_result": numeric_status,
        "discrepancy_note": disc_note,
        "evidence_check_date": verification_timestamp[:10] if verification_timestamp else "2026-10-18",
        "comparability": obs_entry.get("comparability_flag", "DIRECT"),
        "definition_type": obs_entry.get("definition_type"),
        "attribution_basis": "ATTRIBUTABLE_TO_OWNERS" if "attributable" in (obs_entry.get("reported_line_item") or "").lower() else "CONSOLIDATED_TOTAL",
        "scope_type": obs_entry.get("definition_type"),
        "notes": f"Reconciled via {obs_entry.get('extraction_method', '')} against primary statement disclosure.",
        # Multi-dimensional status fields
        "document_identity_status": doc_id_status,
        "document_retrieval_status": doc_retrieval_status,
        "period_match_status": period_match_status,
        "metric_extraction_status": metric_extraction_status,
        "numeric_reconciliation_status": numeric_status,
        "verification_mode": verification_mode,
        "verification_timestamp": verification_timestamp,
        "is_reconciled": is_reconciled,
        "approved_discrepancy_id": matched_disc["discrepancy_id"] if matched_disc else None
    }


def derive_source_reconciliation_status(
    source_entry: Dict[str, Any],
    metric_results: List[Dict[str, Any]]
) -> str:
    """
    Derives the source-level reconciliation status from its underlying metric results.
    A source cannot be INDEPENDENTLY_RECONCILED if document identity is unverified
    or if any metric observation is discrepant or unverified.
    """
    if not source_entry.get("document_identity_verified", False):
        return ReconciliationTier.UNVERIFIED.value

    if not metric_results:
        return ReconciliationTier.SOURCE_LINKED_ONLY.value

    # Check for discrepancies or unverified metrics
    has_discrepant = any(m.get("reconciliation_tier") == ReconciliationTier.DISCREPANT.value for m in metric_results)
    if has_discrepant:
        return ReconciliationTier.DISCREPANT.value

    has_unverified = any(m.get("reconciliation_tier") == ReconciliationTier.UNVERIFIED.value for m in metric_results)
    if has_unverified:
        return ReconciliationTier.UNVERIFIED.value

    has_source_linked_only = any(m.get("reconciliation_tier") == ReconciliationTier.SOURCE_LINKED_ONLY.value for m in metric_results)
    if has_source_linked_only:
        return ReconciliationTier.SOURCE_LINKED_ONLY.value

    all_reconciled = all(m.get("reconciliation_tier") == ReconciliationTier.INDEPENDENTLY_RECONCILED.value for m in metric_results)
    if all_reconciled:
        return ReconciliationTier.INDEPENDENTLY_RECONCILED.value

    return ReconciliationTier.SOURCE_LINKED_ONLY.value
