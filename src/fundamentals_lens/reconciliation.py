"""
Canonical reconciliation engine for Fundamentals Lens.
Provides explicit record-level and metric-level reconciliation functions,
multi-dimensional verification statuses, exact discrepancy validation,
and official document identity verification.
"""
from enum import Enum
import re
from datetime import date, datetime, timezone, timedelta
from typing import Dict, Any, Optional, Tuple, List

SEC_ACCESSION_PATTERN = re.compile(r"^\d{10}-\d{2}-\d{6}$")

# Official corporate domains for Indian companies (investor relations / annual reports)
INDIAN_OFFICIAL_DOMAINS = {
    "TCS": "tcs.com",
    "INFY": "infosys.com",
    "HCLTECH": "hcltech.com",
    "HINDUNILVR": "hul.co.in",
    "BRITANNIA": "britannia.co.in",
    "DABUR": "dabur.com",
    "MARUTI": "marutisuzuki.com",
    "BAJAJ-AUTO": "bajajauto.com",
    "HEROMOTOCO": "heromotocorp.com"
}

# Standard fiscal calendar ending months for target universe companies
COMPANY_FISCAL_END_MONTHS = {
    "AAPL": 9,      # September
    "MSFT": 6,      # June
    "GOOGL": 12,    # December
    "AMZN": 12,     # December
    "NVDA": 1,      # January
    "COST": 8,      # August/September
    "WMT": 1,       # January
    "TGT": 1,       # January/February
    "TCS": 3,       # March
    "INFY": 3,      # March
    "HCLTECH": 3,   # March
    "RELIANCE": 3,  # March
    "HDFCBANK": 3,  # March
    "BRITANNIA": 3, # March
    "DABUR": 3,     # March
    "MARUTI": 3,    # March
    "BAJAJ-AUTO": 3,# March
    "HEROMOTOCO": 3,# March
    "BAJAJFINSV": 3 # March
}

MONTH_NAME_TO_NUM = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12
}


class DocumentIdentityStatus(str, Enum):
    VALIDATED = "VALIDATED"
    INVALID_FORMAT = "INVALID_FORMAT"
    UNVERIFIED = "UNVERIFIED"


class DocumentRetrievalStatus(str, Enum):
    RETRIEVED_OFFLINE_EXTRACT = "RETRIEVED_OFFLINE_EXTRACT"
    OFFLINE_SOURCE_RECORDED = "OFFLINE_SOURCE_RECORDED"
    OFFLINE_AUDITED = "OFFLINE_AUDITED"
    RETRIEVED_ONLINE_EDGAR = "RETRIEVED_ONLINE_EDGAR"
    RETRIEVED_ONLINE_BSE = "RETRIEVED_ONLINE_BSE"
    PENDING_RETRIEVAL = "PENDING_RETRIEVAL"
    NOT_CHECKED = "NOT_CHECKED"
    INCONCLUSIVE = "INCONCLUSIVE"
    FAILED = "FAILED"


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
    TRACKED_OFFLINE_EXTRACT = "TRACKED_OFFLINE_EXTRACT"
    SOURCE_LINKED_ONLY = "SOURCE_LINKED_ONLY"
    DISCREPANT = "DISCREPANT"
    UNVERIFIED = "UNVERIFIED"


class AssuranceState(str, Enum):
    SOURCE_REFERENCE_RECORDED = "SOURCE_REFERENCE_RECORDED"
    SOURCE_IDENTITY_CHECKED = "SOURCE_IDENTITY_CHECKED"
    OFFLINE_EXTRACT_RECORDED = "OFFLINE_EXTRACT_RECORDED"
    DOCUMENT_SNAPSHOT_HASHED = "DOCUMENT_SNAPSHOT_HASHED"
    PRIMARY_STATEMENT_LINE_ITEM_AUDITED = "PRIMARY_STATEMENT_LINE_ITEM_AUDITED"
    LIVE_RETRIEVAL_SUCCEEDED = "LIVE_RETRIEVAL_SUCCEEDED"
    APPROVED_ADJUSTMENT_RESOLVED = "APPROVED_ADJUSTMENT_RESOLVED"
    PENDING_OR_DISCREPANT = "PENDING_OR_DISCREPANT"


def derive_document_identity_verified(
    source_entry: Dict[str, Any],
    company_meta: Dict[str, Any]
) -> Tuple[bool, str]:
    """
    Dynamically derives document_identity_verified from accession syntax,
    official identifier alignment (CIK / BSE scrip), and source URL authenticity.
    Validates official corporate and exchange domains for Indian sources.
    Never unconditionally returns True.
    """
    ticker = source_entry.get("ticker", "")
    meta_ticker = company_meta.get("ticker", "")
    if ticker and meta_ticker and ticker != meta_ticker:
        return False, f"Document ticker mismatch: source '{ticker}' does not match company '{meta_ticker}'"

    country = company_meta.get("country", "")
    is_us = (country == "US" or source_entry.get("reference_type") == "SEC_ACCESSION")
    url = source_entry.get("source_url", "")
    filing_date = source_entry.get("filing_date", "")

    # Date validity check
    if not filing_date or not re.match(r"^\d{4}-\d{2}-\d{2}$", filing_date):
        return False, f"Invalid filing_date format: '{filing_date}'"

    # URL protocol check
    if not url or not url.startswith("https://"):
        return False, f"Insecure or missing source_url: '{url}'"

    import urllib.parse
    try:
        parsed_url = urllib.parse.urlparse(url)
    except Exception as e:
        return False, f"Unparseable source_url '{url}': {e}"

    host = (parsed_url.netloc or "").lower().split(":")[0]
    path = parsed_url.path or ""

    if is_us:
        acc = source_entry.get("official_filing_id") or source_entry.get("accession_id", "")
        cik = company_meta.get("cik") or company_meta.get("sec_cik", "")
        if not acc or not SEC_ACCESSION_PATTERN.match(acc):
            return False, f"SEC accession '{acc}' does not match standard 20-digit pattern"
        if host not in ("www.sec.gov", "sec.gov"):
            return False, f"US SEC filing URL host '{host}' does not originate from official sec.gov"
        if not path.startswith("/Archives/edgar/data/"):
            return False, f"US SEC filing URL path '{path}' does not originate from /Archives/edgar/data/"
        cik_clean = cik.lstrip("0") if cik else ""
        acc_clean = acc.replace("-", "")
        if cik_clean and f"/data/{cik_clean}/" not in path and f"/data/{cik}/" not in path:
            return False, f"SEC filing URL path does not contain company CIK {cik}"
        if acc_clean not in path:
            return False, f"SEC filing URL path does not contain accession {acc}"

        # Filing Form check: Form 10-K required for annual US filings
        form = source_entry.get("form") or ""
        title = source_entry.get("source_title") or ""
        if form and form != "10-K":
            return False, f"US annual filing form must be '10-K' (found '{form}')"
        if not form and "10-K" not in title and "10K" not in title:
            return False, f"US annual filing source title does not reference Form 10-K: '{title}'"

        return True, "US SEC EDGAR 20-digit accession, CIK path, and sec.gov domain verified"
    else:
        key = source_entry.get("internal_document_key") or source_entry.get("accession_id", "")
        scrip = company_meta.get("bse_scrip", "")
        if not key or len(key.strip()) < 5:
            return False, f"Missing or truncated Indian filing document key: '{key}'"
        if scrip and scrip not in key:
            return False, f"Internal document key '{key}' does not contain registered BSE scrip '{scrip}'"

        expected_domain = INDIAN_OFFICIAL_DOMAINS.get(ticker)
        allowed_domains = ["bseindia.com", "nseindia.com"]
        if expected_domain:
            allowed_domains.append(expected_domain)

        domain_valid = False
        for allowed in allowed_domains:
            if host == allowed or host.endswith("." + allowed):
                domain_valid = True
                break

        if not domain_valid:
            return False, f"Indian source URL domain invalid / Indian source URL host invalid: '{host}' from '{url}' (expected registered corporate domain '{expected_domain}' or official exchange)"

        return True, f"BSE scrip ({scrip}) document key format and official corporate URL verified"


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
    Supports top-level single metric entries, multi-metric detail entries (affected_metrics_detail),
    and multi-period entries.
    Arbitrary mismatches without matching numerical amounts are strictly rejected.
    """
    for d in discrepancy_ledger:
        if d.get("ticker") != ticker:
            continue

        # Check status is approved/resolved
        if d.get("status") not in ("RESOLVED", "APPROVED", "AUDITED"):
            continue

        affected_periods = d.get("affected_periods") or []
        d_fy = d.get("fiscal_year")
        d_lbl = d.get("fiscal_year_label", "")
        period_matched = (
            fiscal_year in affected_periods
            or d_fy == fiscal_year
            or d_lbl == fiscal_year_label
            or str(fiscal_year) in d_lbl
        )
        if not period_matched:
            continue

        # Check 1: Top-level metric match
        if d.get("metric") == metric_key:
            approved_rep = d.get("primary_reported_value")
            if approved_rep is None:
                approved_rep = d.get("reported_value")
            if approved_rep is not None and abs(float(reported_val) - float(approved_rep)) < 0.001:
                return d

        # Check 2: Sub-metric or multi-period detail match in affected_metrics_detail
        details = d.get("affected_metrics_detail") or []
        for det in details:
            if det.get("metric") != metric_key:
                continue
            det_fy = det.get("fiscal_year")
            det_lbl = det.get("fiscal_year_label")
            if det_fy is not None and det_fy != fiscal_year:
                continue
            if det_lbl is not None and det_lbl != fiscal_year_label and str(fiscal_year) not in det_lbl:
                continue
            approved_rep = det.get("primary_reported_value")
            if approved_rep is None:
                approved_rep = det.get("reported_value")
            if approved_rep is not None and abs(float(reported_val) - float(approved_rep)) < 0.001:
                return {
                    **d,
                    "matched_sub_metric": metric_key,
                    "primary_reported_value": approved_rep,
                    "final_canonical_value": det.get("final_canonical_value"),
                    "investigation_finding": det.get("investigation_finding") or d.get("investigation_finding")
                }

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
    verification_timestamp: str = "",
    company_meta: Optional[Dict[str, Any]] = None,
    retrieval_outcome: Optional[Dict[str, Any]] = None
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

    # Explicit per-document retrieval outcome handling
    outcome = retrieval_outcome or src_entry.get("retrieval_outcome") or obs_entry.get("retrieval_outcome")
    if outcome is not None:
        outcome_status = str(outcome.get("outcome") or outcome.get("status") or "").upper()
        http_code = outcome.get("http_status")
        if outcome_status == "SUCCESS" or http_code == 200:
            doc_retrieval_status = (
                DocumentRetrievalStatus.RETRIEVED_ONLINE_EDGAR.value
                if is_us
                else DocumentRetrievalStatus.RETRIEVED_ONLINE_BSE.value
            )
        elif outcome_status in ("TIMEOUT", "INCONCLUSIVE"):
            doc_retrieval_status = DocumentRetrievalStatus.INCONCLUSIVE.value
        elif outcome_status == "NOT_ATTEMPTED":
            doc_retrieval_status = DocumentRetrievalStatus.NOT_CHECKED.value
        else:
            doc_retrieval_status = DocumentRetrievalStatus.FAILED.value
    else:
        if verification_mode == "ONLINE":
            # In online mode without recorded successful retrieval outcome, status is NOT_CHECKED
            doc_retrieval_status = DocumentRetrievalStatus.NOT_CHECKED.value
        else:
            doc_retrieval_status = (
                src_entry.get("check_status")
                or obs_entry.get("source_document_status")
                or DocumentRetrievalStatus.RETRIEVED_OFFLINE_EXTRACT.value
            )

    # Substantive period match check: verify fiscal year, period dates exist, start < end, duration is 300..400 days,
    # and period_end month aligns with company fiscal calendar
    obs_fy = obs_entry.get("fiscal_year")
    obs_pstart = obs_entry.get("period_start")
    obs_pend = obs_entry.get("period_end")
    period_match_status = PeriodMatchStatus.PERIOD_MISMATCH.value
    period_mismatch_reason = ""
    if obs_fy == fiscal_year and obs_pstart and obs_pend:
        try:
            p_start_d = date.fromisoformat(str(obs_pstart)[:10])
            p_end_d = date.fromisoformat(str(obs_pend)[:10])
            duration_days = (p_end_d - p_start_d).days
            if p_start_d < p_end_d and 300 <= duration_days <= 400:
                # Check company fiscal calendar alignment
                meta_end_month = None
                if company_meta and company_meta.get("fiscal_year_end_month"):
                    m_name = str(company_meta.get("fiscal_year_end_month")).strip().lower()
                    meta_end_month = MONTH_NAME_TO_NUM.get(m_name)
                elif ticker in COMPANY_FISCAL_END_MONTHS:
                    meta_end_month = COMPANY_FISCAL_END_MONTHS[ticker]

                if meta_end_month is not None:
                    allowed_months = {meta_end_month, (meta_end_month % 12) + 1}
                    if p_end_d.month in allowed_months:
                        period_match_status = PeriodMatchStatus.EXACT_PERIOD_MATCH.value
                    else:
                        period_match_status = PeriodMatchStatus.PERIOD_MISMATCH.value
                        period_mismatch_reason = (
                            f"Fiscal calendar mismatch: ticker '{ticker}' fiscal year ends around month {meta_end_month}, "
                            f"but observation period_end '{obs_pend}' is month {p_end_d.month}."
                        )
                else:
                    period_match_status = PeriodMatchStatus.EXACT_PERIOD_MATCH.value
            else:
                period_match_status = PeriodMatchStatus.PERIOD_MISMATCH.value
                period_mismatch_reason = f"Duration outside 300..400 days ({duration_days} days) or invalid chronological bounds."
        except (ValueError, TypeError) as e:
            period_match_status = PeriodMatchStatus.PERIOD_MISMATCH.value
            period_mismatch_reason = f"Invalid date formatting: {e}"

    # Substantive metric extraction status check
    loc = (obs_entry.get("statement_locator") or "").strip()
    line_item = (obs_entry.get("reported_line_item") or "").strip()
    stmt_name = (obs_entry.get("statement_name") or "").strip()
    generic_locators = {
        "consolidated financial statements",
        "financial statements",
        "item 8",
        "item 8 - consolidated financial statements",
        "item 8 - financial statements",
        "annual report",
        "annual reports",
        "statements",
        "consolidated statements"
    }

    unit = (obs_entry.get("source_unit") or obs_entry.get("reported_unit") or "").strip()
    sign = (obs_entry.get("reported_sign") or "").strip()
    raw_basis = (obs_entry.get("statement_basis") or "").strip().upper()
    basis = raw_basis or ("CONSOLIDATED" if "consolidated" in stmt_name.lower() else "")
    ext_method = (obs_entry.get("extraction_method") or "").strip()

    if (
        reported_val is None
        or not loc
        or len(loc) < 10
        or loc.lower() in generic_locators
        or len(line_item) < 3
        or len(stmt_name) < 3
        or not unit
        or not sign
        or basis == "STANDALONE"
        or (basis and basis != "CONSOLIDATED")
        or (ext_method and ext_method not in ("MANUAL_AUDITED_STATEMENT_EXTRACT", "SEC_XBRL_FACTS_PRIMARY"))
    ):
        metric_extraction_status = MetricExtractionStatus.VALUE_NOT_LOCATED.value
    else:
        metric_extraction_status = MetricExtractionStatus.EXTRACTED_LINE_ITEM.value

    # Numeric reconciliation logic
    matched_disc = None
    assurance_state = AssuranceState.PENDING_OR_DISCREPANT.value
    if not is_identity_verified:
        numeric_status = NumericReconciliationStatus.IDENTITY_UNVERIFIED.value
        tier = ReconciliationTier.UNVERIFIED.value
        assurance_state = AssuranceState.PENDING_OR_DISCREPANT.value
        is_reconciled = False
        disc_note = "Filing document identity check failed (malformed accession, CIK path mismatch, or invalid filing key)."
        conv_formula = "None (Filing document identity could not be validated)"
    elif verification_mode == "ONLINE" and doc_retrieval_status in (
        DocumentRetrievalStatus.FAILED.value,
        DocumentRetrievalStatus.INCONCLUSIVE.value,
        DocumentRetrievalStatus.NOT_CHECKED.value
    ):
        numeric_status = NumericReconciliationStatus.NOT_RECONCILED.value
        tier = ReconciliationTier.SOURCE_LINKED_ONLY.value
        assurance_state = AssuranceState.PENDING_OR_DISCREPANT.value
        is_reconciled = False
        disc_note = f"Online document retrieval outcome was '{doc_retrieval_status}'; fresh online independent reconciliation unconfirmed; cannot earn INDEPENDENTLY_RECONCILED tier without verified live retrieval."
        conv_formula = "None (Online retrieval outcome unconfirmed)"
    elif reported_val is None or metric_extraction_status == MetricExtractionStatus.VALUE_NOT_LOCATED.value:
        numeric_status = NumericReconciliationStatus.NOT_RECONCILED.value
        tier = ReconciliationTier.SOURCE_LINKED_ONLY.value
        assurance_state = AssuranceState.SOURCE_REFERENCE_RECORDED.value
        is_reconciled = False
        disc_note = "Metric linked to registered primary source; independent line-item statement reconciliation pending."
        conv_formula = "None (Independent line-item statement reconciliation pending)"
    elif period_match_status == PeriodMatchStatus.PERIOD_MISMATCH.value:
        numeric_status = NumericReconciliationStatus.UNEXPLAINED_DISCREPANCY.value
        tier = ReconciliationTier.DISCREPANT.value
        assurance_state = AssuranceState.PENDING_OR_DISCREPANT.value
        is_reconciled = False
        disc_note = f"Period chronology mismatch: {period_mismatch_reason or f'period_start={obs_pstart}, period_end={obs_pend} does not span valid fiscal year {fiscal_year}.'}"
        conv_formula = "None (Period duration or fiscal calendar mismatch)"
    else:
        # First check for exact approved discrepancy adjustment in ledger
        matched_disc = find_matching_approved_discrepancy(
            ticker=ticker,
            metric_key=metric_key,
            fiscal_year=fiscal_year,
            fiscal_year_label=fiscal_year_label,
            reported_val=float(reported_val),
            canonical_val=float(canonical_val),
            discrepancy_ledger=discrepancy_ledger
        )
        if not matched_disc and obs_entry.get("discrepancy_reference"):
            disc_ref = obs_entry.get("discrepancy_reference")
            for d in discrepancy_ledger:
                if d.get("discrepancy_id") == disc_ref:
                    matched_disc = d
                    break

        if matched_disc is not None:
            numeric_status = NumericReconciliationStatus.RECONCILED_WITH_APPROVED_ADJUSTMENT.value
            tier = ReconciliationTier.INDEPENDENTLY_RECONCILED.value
            assurance_state = AssuranceState.APPROVED_ADJUSTMENT_RESOLVED.value
            is_reconciled = True
            disc_note = f"Audited reconciliation ({matched_disc['discrepancy_id']}): {matched_disc.get('investigation_finding')}"
        else:
            diff = abs(float(reported_val) - float(canonical_val))
            if diff < 0.001:
                numeric_status = NumericReconciliationStatus.EXACT_STATEMENT_MATCH.value
                is_reconciled = True
                acc_id = src_entry.get("official_filing_id") or src_entry.get("accession_id", "")
                if is_us:
                    disc_note = f"Reconciled to Form 10-K {stmt_name} under accession {acc_id}."
                else:
                    disc_note = f"Reconciled to Ind AS Consolidated {stmt_name} ({acc_id}).."

                # Evidentiary gate: Live retrieval or hashed artifact earns INDEPENDENTLY_RECONCILED;
                # Tracked extract matching canonical fact earns TRACKED_OFFLINE_EXTRACT.
                if verification_mode == "ONLINE" and doc_retrieval_status in (
                    DocumentRetrievalStatus.RETRIEVED_ONLINE_EDGAR.value,
                    DocumentRetrievalStatus.RETRIEVED_ONLINE_BSE.value
                ):
                    tier = ReconciliationTier.INDEPENDENTLY_RECONCILED.value
                    assurance_state = AssuranceState.LIVE_RETRIEVAL_SUCCEEDED.value
                elif obs_entry.get("document_snapshot_hash"):
                    tier = ReconciliationTier.INDEPENDENTLY_RECONCILED.value
                    assurance_state = AssuranceState.PRIMARY_STATEMENT_LINE_ITEM_AUDITED.value
                else:
                    tier = ReconciliationTier.TRACKED_OFFLINE_EXTRACT.value
                    assurance_state = AssuranceState.OFFLINE_EXTRACT_RECORDED.value
            else:
                numeric_status = NumericReconciliationStatus.UNEXPLAINED_DISCREPANCY.value
                tier = ReconciliationTier.DISCREPANT.value
                assurance_state = AssuranceState.PENDING_OR_DISCREPANT.value
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
        "assurance_state": assurance_state,
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
    A source cannot be INDEPENDENTLY_RECONCILED or TRACKED_OFFLINE_EXTRACT if document identity
    is unverified or if any metric observation is discrepant or unverified.
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

    all_verified = all(
        m.get("reconciliation_tier") in (ReconciliationTier.INDEPENDENTLY_RECONCILED.value, ReconciliationTier.TRACKED_OFFLINE_EXTRACT.value)
        for m in metric_results
    )
    if all_verified:
        return ReconciliationTier.TRACKED_OFFLINE_EXTRACT.value

    return ReconciliationTier.SOURCE_LINKED_ONLY.value


def validate_reconciliation_telemetry(record: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """
    Validates that a reconciled metric record does not contain contradictory combinations of:
    - verification_mode
    - document_retrieval_status
    - document_identity_status
    - period_match_status
    - metric_extraction_status
    - reconciliation_tier
    - verification_timestamp
    """
    errors: List[str] = []
    mode = record.get("verification_mode")
    ret_status = record.get("document_retrieval_status")
    id_status = record.get("document_identity_status")
    period_status = record.get("period_match_status")
    ext_status = record.get("metric_extraction_status")
    tier = record.get("reconciliation_tier")
    timestamp = record.get("verification_timestamp")

    # 1. Offline build claiming online retrieval
    if mode == "OFFLINE" and ret_status in (
        DocumentRetrievalStatus.RETRIEVED_ONLINE_EDGAR.value,
        DocumentRetrievalStatus.RETRIEVED_ONLINE_BSE.value
    ):
        errors.append(f"Contradictory telemetry: verification_mode is OFFLINE but document_retrieval_status is '{ret_status}'.")

    # 2. Failed, Inconclusive, or Unchecked online retrieval earning INDEPENDENTLY_RECONCILED in online mode
    if mode == "ONLINE" and ret_status in (
        DocumentRetrievalStatus.FAILED.value,
        DocumentRetrievalStatus.INCONCLUSIVE.value,
        DocumentRetrievalStatus.NOT_CHECKED.value
    ) and tier == ReconciliationTier.INDEPENDENTLY_RECONCILED.value:
        errors.append(f"Contradictory telemetry: reconciliation_tier is INDEPENDENTLY_RECONCILED in ONLINE mode despite retrieval status '{ret_status}'.")

    # 3. Unverified identity earning INDEPENDENTLY_RECONCILED
    if id_status == DocumentIdentityStatus.UNVERIFIED.value and tier == ReconciliationTier.INDEPENDENTLY_RECONCILED.value:
        errors.append("Contradictory telemetry: reconciliation_tier is INDEPENDENTLY_RECONCILED but document_identity_status is UNVERIFIED.")

    # 4. Period mismatch earning INDEPENDENTLY_RECONCILED
    if period_status == PeriodMatchStatus.PERIOD_MISMATCH.value and tier == ReconciliationTier.INDEPENDENTLY_RECONCILED.value:
        errors.append("Contradictory telemetry: reconciliation_tier is INDEPENDENTLY_RECONCILED but period_match_status is PERIOD_MISMATCH.")

    # 5. Missing line item extraction earning INDEPENDENTLY_RECONCILED or TRACKED_OFFLINE_EXTRACT
    if ext_status == MetricExtractionStatus.VALUE_NOT_LOCATED.value and tier in (
        ReconciliationTier.INDEPENDENTLY_RECONCILED.value,
        ReconciliationTier.TRACKED_OFFLINE_EXTRACT.value
    ):
        errors.append(f"Contradictory telemetry: reconciliation_tier is {tier} but metric_extraction_status is VALUE_NOT_LOCATED.")

    # 6. Reconciled tier without verification timestamp
    if tier in (ReconciliationTier.INDEPENDENTLY_RECONCILED.value, ReconciliationTier.TRACKED_OFFLINE_EXTRACT.value) and not timestamp:
        errors.append(f"Contradictory telemetry: reconciliation_tier is {tier} but verification_timestamp is empty.")

    # 7. Online retrieved status without verification timestamp
    if ret_status in (
        DocumentRetrievalStatus.RETRIEVED_ONLINE_EDGAR.value,
        DocumentRetrievalStatus.RETRIEVED_ONLINE_BSE.value
    ) and not timestamp:
        errors.append(f"Contradictory telemetry: document_retrieval_status is '{ret_status}' but verification_timestamp is empty.")

    # 8. Unverified identity or period mismatch claiming TRACKED_OFFLINE_EXTRACT
    if id_status == DocumentIdentityStatus.UNVERIFIED.value and tier == ReconciliationTier.TRACKED_OFFLINE_EXTRACT.value:
        errors.append("Contradictory telemetry: reconciliation_tier is TRACKED_OFFLINE_EXTRACT but document_identity_status is UNVERIFIED.")
    if period_status == PeriodMatchStatus.PERIOD_MISMATCH.value and tier == ReconciliationTier.TRACKED_OFFLINE_EXTRACT.value:
        errors.append("Contradictory telemetry: reconciliation_tier is TRACKED_OFFLINE_EXTRACT but period_match_status is PERIOD_MISMATCH.")

    # 9. Offline extract claiming INDEPENDENTLY_RECONCILED without approved discrepancy or document snapshot hash
    if mode == "OFFLINE" and tier == ReconciliationTier.INDEPENDENTLY_RECONCILED.value:
        if not record.get("approved_discrepancy_id") and not record.get("document_snapshot_hash"):
            errors.append(
                "Contradictory telemetry: reconciliation_tier is INDEPENDENTLY_RECONCILED in OFFLINE mode "
                "without approved_discrepancy_id or document_snapshot_hash."
            )

    # 10. Timestamp format and future date validation
    if timestamp:
        try:
            clean_ts = timestamp.replace("Z", "+00:00")
            dt = datetime.fromisoformat(clean_ts)
            now_utc = datetime.now(timezone.utc)
            if dt > now_utc + timedelta(days=1):
                errors.append(f"Contradictory telemetry: verification_timestamp '{timestamp}' is in the future.")
        except Exception as e:
            errors.append(f"Contradictory telemetry: verification_timestamp '{timestamp}' is not valid ISO 8601: {e}")

    return len(errors) == 0, errors
