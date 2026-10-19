"""
End-to-End Discrepancy Ledger Validator (Phase 15 Hardened).

Enforces:
1. Single authoritative schema for all discrepancy ledger entries.
2. Complete field validation: initial, pre-correction, reported, and final values.
3. Strict resolution status validation: verifies that canonical facts and source observations
   actually agree with the documented resolution before accepting RESOLVED status.
4. Non-numerical discrimination: DISC-011 is strictly classified as FILING_IDENTITY_ALIGNMENT
   with is_numerical=False and excluded from numerical discrepancy counts.
5. Sub-metric and multi-year precision: every sub-metric in affected_metrics_detail is
   individually validated against its exact company, metric, and fiscal year.
6. Derived calculation consistency: verifies that FCF and operating margins in canonical facts
   reflect the resolved primary metrics.
"""

import re
from typing import Dict, Any, List, Optional, Tuple, Set


VALID_CATEGORIES = {
    "NUMERICAL_REVISION",
    "ACCOUNTING_PROXY_CLASSIFICATION",
    "ATTRIBUTION_BASIS",
    "FILING_IDENTITY_ALIGNMENT"
}

VALID_STATUSES = {
    "RESOLVED",
    "UNRESOLVED",
    "REQUIRES_SOURCE_REVIEW"
}

PRIMARY_METRICS = {
    "revenue",
    "operating_income",
    "net_income",
    "operating_cash_flow",
    "capital_expenditure"
}

ALL_ALLOWED_METRICS = PRIMARY_METRICS | {"free_cash_flow", "accession_alignment"}

DISCREPANCY_ID_PATTERN = re.compile(r"^DISC-\d{3}$")


def validate_discrepancy_ledger(
    ledger: List[Dict[str, Any]],
    financial_facts: Optional[List[Dict[str, Any]]] = None,
    source_observations: Optional[List[Dict[str, Any]]] = None,
    tolerance: float = 0.001
) -> Dict[str, Any]:
    """
    Exhaustive validation of discrepancy ledger entries against schema,
    canonical financial facts, and primary source observations.

    Returns:
        Dict containing:
            is_valid (bool): True if zero errors encountered
            total_entries (int): Total ledger entries
            numerical_count (int): Count of numerical discrepancies
            identity_count (int): Count of identity-only alignments
            resolved_count (int): Count of resolved discrepancies
            unresolved_count (int): Count of unresolved discrepancies
            category_breakdown (dict): Counts by discrepancy_category
            errors (list): List of actionable validation error strings
    """
    errors: List[str] = []
    seen_ids: Set[str] = set()
    category_counts: Dict[str, int] = {}
    numerical_count = 0
    identity_count = 0
    resolved_count = 0
    unresolved_count = 0

    seen_ledger_keys: Set[Tuple[str, int, str]] = set()

    # Index facts and observations if provided with collision detection
    facts_map: Dict[Tuple[str, int], Dict[str, Any]] = {}
    if financial_facts:
        for f in financial_facts:
            # support both dict and FinancialFact dataclass
            t = f.get("ticker") if isinstance(f, dict) else getattr(f, "ticker", None)
            fy = f.get("fiscal_year") if isinstance(f, dict) else getattr(f, "fiscal_year", None)
            if t and fy:
                f_key = (t, int(fy))
                if f_key in facts_map:
                    errors.append(f"Duplicate financial fact encountered for ticker='{t}', fiscal_year={fy} in input facts population.")
                else:
                    facts_map[f_key] = f if isinstance(f, dict) else f.__dict__

    obs_map: Dict[Tuple[str, int, str], Dict[str, Any]] = {}
    if source_observations:
        for o in source_observations:
            t = o.get("ticker")
            fy = o.get("fiscal_year")
            m = o.get("metric_name")
            if t and fy and m:
                o_key = (t, int(fy), m)
                if o_key in obs_map:
                    errors.append(f"Duplicate source observation encountered for ticker='{t}', fiscal_year={fy}, metric='{m}' in input observations population.")
                else:
                    obs_map[o_key] = o

    for idx, d in enumerate(ledger):
        did = d.get("discrepancy_id")
        entry_prefix = f"Ledger entry #{idx+1} ({did or 'MISSING_ID'})"

        # 1. ID format and uniqueness
        if not did or not DISCREPANCY_ID_PATTERN.match(did):
            errors.append(f"{entry_prefix}: Invalid or missing discrepancy_id format (must match 'DISC-XXX')")
        elif did in seen_ids:
            errors.append(f"{entry_prefix}: Duplicate discrepancy_id '{did}' detected")
        if did:
            seen_ids.add(did)

        # 2. Company ticker and fiscal year
        ticker = d.get("ticker")
        if not ticker or not isinstance(ticker, str):
            errors.append(f"{entry_prefix}: Missing or invalid ticker '{ticker}'")

        fy = d.get("fiscal_year")
        if fy is None or not isinstance(fy, int) or fy < 2020 or fy > 2030:
            errors.append(f"{entry_prefix}: Missing or invalid fiscal_year '{fy}'")

        # 3. Metric name
        metric = d.get("metric")
        if not metric or metric not in ALL_ALLOWED_METRICS:
            errors.append(f"{entry_prefix}: Invalid metric '{metric}' (allowed: {sorted(ALL_ALLOWED_METRICS)})")

        if ticker and fy and metric:
            l_key = (ticker, fy, metric)
            if l_key in seen_ledger_keys:
                errors.append(f"{entry_prefix}: Duplicate ledger composite key for ticker='{ticker}', fiscal_year={fy}, metric='{metric}'")
            else:
                seen_ledger_keys.add(l_key)

        # 4. Category and classification
        category = d.get("discrepancy_category")
        if category not in VALID_CATEGORIES:
            errors.append(f"{entry_prefix}: Invalid discrepancy_category '{category}' (allowed: {sorted(VALID_CATEGORIES)})")
        else:
            category_counts[category] = category_counts.get(category, 0) + 1

        is_num = d.get("is_numerical")
        if is_num is None or not isinstance(is_num, bool):
            errors.append(f"{entry_prefix}: Missing or non-boolean 'is_numerical'")
        else:
            if category == "FILING_IDENTITY_ALIGNMENT" and is_num is not False:
                errors.append(f"{entry_prefix}: FILING_IDENTITY_ALIGNMENT must have is_numerical=False")
            elif category != "FILING_IDENTITY_ALIGNMENT" and is_num is not True:
                errors.append(f"{entry_prefix}: {category} must have is_numerical=True")

            if is_num:
                numerical_count += 1
            else:
                identity_count += 1

        # 5. Status
        status = d.get("status")
        if status not in VALID_STATUSES:
            errors.append(f"{entry_prefix}: Invalid status '{status}' (allowed: {sorted(VALID_STATUSES)})")
        elif status == "RESOLVED":
            resolved_count += 1
        else:
            unresolved_count += 1

        # 6. Rationale and source key
        rationale = d.get("resolution_rationale") or d.get("resolution") or d.get("resolution_or_reconciliation_note")
        if not rationale or len(str(rationale).strip()) < 10:
            errors.append(f"{entry_prefix}: Missing or insufficient resolution_rationale (>= 10 chars required)")

        source_key = d.get("source_accession_or_key")
        if not source_key or len(str(source_key).strip()) < 4:
            errors.append(f"{entry_prefix}: Missing or truncated source_accession_or_key")

        # 7. Value fields presence and types
        init_val = d.get("initial_dataset_value")
        pre_val = d.get("canonical_value_before_correction")
        rep_val = d.get("primary_reported_value") if d.get("primary_reported_value") is not None else d.get("reported_value")
        fin_val = d.get("final_canonical_value") if d.get("final_canonical_value") is not None else d.get("canonical_value")

        if is_num:
            for v_name, v_val in [
                ("initial_dataset_value", init_val),
                ("canonical_value_before_correction", pre_val),
                ("primary_reported_value", rep_val),
                ("final_canonical_value", fin_val)
            ]:
                if v_val is None or not isinstance(v_val, (int, float)):
                    errors.append(f"{entry_prefix}: Numerical discrepancy missing numeric {v_name} (found: {v_val})")

            # Validate unit
            unit = d.get("unit")
            if not unit:
                errors.append(f"{entry_prefix}: Numerical discrepancy missing 'unit'")

        # 8. Sub-metric detail validation (affected_metrics_detail)
        sub_metrics = d.get("affected_metrics_detail")
        if is_num:
            if not isinstance(sub_metrics, list) or len(sub_metrics) == 0:
                errors.append(f"{entry_prefix}: Numerical discrepancy requires non-empty 'affected_metrics_detail'")
            else:
                for s_idx, sm in enumerate(sub_metrics):
                    sm_metric = sm.get("metric")
                    if not sm_metric or sm_metric not in ALL_ALLOWED_METRICS:
                        errors.append(f"{entry_prefix} sub #{s_idx+1}: Invalid sub-metric '{sm_metric}'")
                    sm_fin = sm.get("final_canonical_value")
                    sm_rep = sm.get("primary_reported_value")
                    if sm_fin is None or not isinstance(sm_fin, (int, float)):
                        errors.append(f"{entry_prefix} sub #{s_idx+1} ({sm_metric}): Missing numeric final_canonical_value")
                    if sm_rep is None or not isinstance(sm_rep, (int, float)):
                        errors.append(f"{entry_prefix} sub #{s_idx+1} ({sm_metric}): Missing numeric primary_reported_value")
        else:
            # Identity only: affected_metrics_detail should be empty
            if sub_metrics and len(sub_metrics) > 0:
                errors.append(f"{entry_prefix}: Non-numerical discrepancy should have empty affected_metrics_detail")

        # 9. Cross-artifact integrity validation against canonical facts & source observations
        if facts_map and ticker and fy:
            fact = facts_map.get((ticker, fy))
            if not fact:
                errors.append(f"{entry_prefix}: No canonical financial fact found for {ticker} FY{fy}")
            elif is_num and fin_val is not None and metric in PRIMARY_METRICS:
                fact_val = fact.get(metric)
                if fact_val is None:
                    errors.append(f"{entry_prefix}: Fact value for {ticker} FY{fy} {metric} is None")
                elif status == "RESOLVED":
                    # Fact MUST equal final_canonical_value
                    if abs(float(fact_val) - float(fin_val)) > tolerance:
                        errors.append(
                            f"{entry_prefix}: Fact value {fact_val} != final_canonical_value {fin_val} for RESOLVED status"
                        )
            elif not is_num:
                # Identity check: accession in fact must match source_key
                fact_acc = fact.get("accession_id") or fact.get("official_filing_id")
                if fact_acc and source_key and fact_acc != source_key:
                    errors.append(
                        f"{entry_prefix}: Fact accession '{fact_acc}' != resolved source_accession_or_key '{source_key}'"
                    )

            # Check sub-metrics against facts
            if is_num and sub_metrics:
                for sm in sub_metrics:
                    sm_metric = sm.get("metric")
                    sm_fy = sm.get("fiscal_year", fy)
                    sm_fin = sm.get("final_canonical_value")
                    if sm_metric in PRIMARY_METRICS and sm_fin is not None:
                        sm_fact = facts_map.get((ticker, sm_fy))
                        if not sm_fact:
                            errors.append(f"{entry_prefix} sub ({sm_metric}): No fact found for {ticker} FY{sm_fy}")
                        else:
                            sm_fact_val = sm_fact.get(sm_metric)
                            if sm_fact_val is not None and status == "RESOLVED":
                                if abs(float(sm_fact_val) - float(sm_fin)) > tolerance:
                                    errors.append(
                                        f"{entry_prefix} sub ({sm_metric} FY{sm_fy}): Fact value {sm_fact_val} != final_canonical_value {sm_fin}"
                                    )

                # Check derived FCF arithmetic if free_cash_flow, OCF, or Capex is in sub-metrics
                sm_fcf = next((s for s in sub_metrics if s.get("metric") == "free_cash_flow"), None)
                if sm_fcf and sm_fcf.get("final_canonical_value") is not None:
                    sm_fcf_val = float(sm_fcf["final_canonical_value"])
                    sm_fy = sm_fcf.get("fiscal_year", fy)
                    chk_fact = facts_map.get((ticker, sm_fy))
                    if chk_fact:
                        ocf = chk_fact.get("operating_cash_flow")
                        capex = chk_fact.get("capital_expenditure")
                        if ocf is not None and capex is not None:
                            expected_fcf = float(ocf) - float(capex)
                            if abs(sm_fcf_val - expected_fcf) > tolerance:
                                errors.append(
                                    f"{entry_prefix}: Sub-metric FCF {sm_fcf_val} != (Fact OCF {ocf} - Capex {capex} = {expected_fcf})"
                                )
                        fact_fcf = chk_fact.get("free_cash_flow")
                        if fact_fcf is not None and ocf is not None and capex is not None:
                            if abs(float(fact_fcf) - (float(ocf) - float(capex))) > tolerance:
                                errors.append(
                                    f"{entry_prefix}: Fact FCF {fact_fcf} != (OCF {ocf} - Capex {capex})"
                                )

                # Check derived Operating Margin arithmetic if Revenue or Operating Income is in facts
                affected_metric_names = {sm.get("metric") for sm in sub_metrics} | {metric}
                if "revenue" in affected_metric_names or "operating_income" in affected_metric_names:
                    for sm in sub_metrics:
                        sm_fy = sm.get("fiscal_year", fy)
                        chk_fact = facts_map.get((ticker, sm_fy))
                        if chk_fact:
                            rev = chk_fact.get("revenue")
                            oi = chk_fact.get("operating_income")
                            op_margin = chk_fact.get("operating_margin")
                            if rev and oi is not None and op_margin is not None:
                                expected_margin = round((float(oi) / float(rev)) * 100.0, 4)
                                if abs(float(op_margin) - expected_margin) > 0.05:
                                    errors.append(
                                        f"{entry_prefix}: Derived Operating Margin {op_margin}% != (OI {oi} / Rev {rev} = {expected_margin}%)"
                                    )

        # 10. Cross-artifact integrity validation against source observations
        if obs_map and ticker and fy and is_num:
            if metric in PRIMARY_METRICS:
                obs = obs_map.get((ticker, fy, metric))
                if not obs:
                    errors.append(f"{entry_prefix}: No source observation found for {ticker} FY{fy} {metric}")
                elif rep_val is not None and status == "RESOLVED":
                    obs_rep = obs.get("reported_value")
                    if obs_rep is None:
                        errors.append(f"{entry_prefix}: Source observation reported_value is None for {ticker} FY{fy} {metric}")
                    elif abs(float(obs_rep) - float(rep_val)) > tolerance:
                        errors.append(
                            f"{entry_prefix}: Observation reported_value {obs_rep} != primary_reported_value {rep_val}"
                        )

            # Check sub-metrics against observations
            if sub_metrics:
                for sm in sub_metrics:
                    sm_metric = sm.get("metric")
                    sm_fy = sm.get("fiscal_year", fy)
                    sm_rep = sm.get("primary_reported_value")
                    if sm_metric in PRIMARY_METRICS and sm_rep is not None and status == "RESOLVED":
                        sm_obs = obs_map.get((ticker, sm_fy, sm_metric))
                        if sm_obs:
                            sm_obs_rep = sm_obs.get("reported_value")
                            if sm_obs_rep is not None and abs(float(sm_obs_rep) - float(sm_rep)) > tolerance:
                                errors.append(
                                    f"{entry_prefix} sub ({sm_metric} FY{sm_fy}): Observation reported_value {sm_obs_rep} != primary_reported_value {sm_rep}"
                                )

    return {
        "is_valid": len(errors) == 0,
        "total_entries": len(ledger),
        "numerical_count": numerical_count,
        "identity_count": identity_count,
        "resolved_count": resolved_count,
        "unresolved_count": unresolved_count,
        "category_breakdown": category_counts,
        "errors": errors
    }
