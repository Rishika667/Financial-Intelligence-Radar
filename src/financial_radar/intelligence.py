import json
import logging

logger = logging.getLogger(__name__)


def resolve_evidence_pair(evidence):
    """
    Resolve and order current vs prior evidence observations deterministically.

    Accepts:
    - a JSON string representing a list of observations/dicts
    - a list or tuple of dicts or Observation objects

    Returns:
    (current_obs, prior_obs) as dicts, or (None, None) if insufficient evidence.

    Ordering logic:
    If observations contain period_end or fiscal information, sorts so that
    the later observation is current and the earlier observation is prior.
    If period information is identical or absent, preserves [0] as current
    and [1] as prior for backwards compatibility with test mocks.
    """
    ev = []
    if isinstance(evidence, str):
        try:
            if evidence.strip():
                ev = json.loads(evidence)
        except Exception:
            return None, None
    elif isinstance(evidence, (list, tuple)):
        ev = list(evidence)
    else:
        return None, None

    if not ev:
        return None, None
    if len(ev) == 1:
        item = ev[0]
        if not isinstance(item, dict):
            item = _obs_to_dict(item)
        return item, None

    dict_items = [_obs_to_dict(x) if not isinstance(x, dict) else dict(x) for x in ev]

    def _date_key(item):
        pe = item.get("period_end") or ""
        fy = item.get("fiscal_year") or 0
        fp = item.get("fiscal_period") or ""
        ps = item.get("period_start") or ""
        pe_str = pe.isoformat() if hasattr(pe, "isoformat") else str(pe)
        ps_str = ps.isoformat() if hasattr(ps, "isoformat") else str(ps)
        try:
            fy_int = int(fy) if fy else 0
        except (ValueError, TypeError):
            fy_int = 0
        return (pe_str, fy_int, str(fp), ps_str)

    k0 = _date_key(dict_items[0])
    k1 = _date_key(dict_items[1])

    # If distinct dates/fiscal info exist, sort descending (most recent first)
    if k0 != k1 and (k0 != ("", 0, "", "") or k1 != ("", 0, "", "")):
        sorted_ev = sorted(dict_items, key=_date_key, reverse=True)
        return sorted_ev[0], sorted_ev[1]

    return dict_items[0], dict_items[1]


def _obs_to_dict(item):
    if isinstance(item, dict):
        return item
    d = {}
    for k in (
        "metric", "value", "unit", "period_end", "period_type", "quality",
        "comparable", "provenance", "derived_from", "period_start",
        "fiscal_year", "fiscal_period"
    ):
        val = getattr(item, k, None)
        if hasattr(val, "isoformat"):
            val = val.isoformat()
        elif hasattr(val, "value"):
            val = val.value
        d[k] = val
    return d


def group_cluster_evidence_by_metric(evidence):
    """
    Groups multi-factor cluster evidence observations by metric so each metric
    is displayed with its own current and prior observation without cross-metric pairing.

    Accepts:
    - a JSON string representing a list of observations/dicts
    - a list or tuple of dicts or Observation objects

    Returns:
    dict: {metric_name: {"current": obs_dict, "prior": obs_dict, "observations": [obs_dicts]}}
    """
    ev = []
    if isinstance(evidence, str):
        try:
            if evidence.strip():
                ev = json.loads(evidence)
        except Exception:
            return {}
    elif isinstance(evidence, (list, tuple)):
        ev = list(evidence)
    else:
        return {}

    from collections import defaultdict
    by_metric = defaultdict(list)
    for item in ev:
        d = _obs_to_dict(item) if not isinstance(item, dict) else dict(item)
        m = d.get("metric", "unknown")
        by_metric[m].append(d)

    grouped = {}
    for m, items in by_metric.items():
        if len(items) >= 2:
            c, p = resolve_evidence_pair(items)
        elif len(items) == 1:
            c, p = items[0], None
        else:
            c, p = None, None
        grouped[m] = {
            "current": c,
            "prior": p,
            "observations": items
        }
    return grouped


def generate_intelligence(signal_id, company, sector, evidence_str):
    curr_item, prior_item = resolve_evidence_pair(evidence_str)

    what = "Metric triggered predefined deterioration thresholds."

    if curr_item and prior_item:
        curr = curr_item.get("value")
        prev = prior_item.get("value")
        if curr is not None and prev is not None:
            if "MARGIN" in signal_id:
                margin_type = "Gross" if "GROSS" in signal_id else ("Operating" if "OPERATING" in signal_id else signal_id.replace('_', ' ').title().split(' ')[0])
                diff_pp = abs(curr - prev) * 100
                if curr < prev:
                    what = f"{margin_type} margin declined from {prev*100:.1f}% to {curr*100:.1f}%, a {diff_pp:.1f} percentage-point decline."
                elif curr > prev:
                    what = f"{margin_type} margin increased from {prev*100:.1f}% to {curr*100:.1f}%, a {diff_pp:.1f} percentage-point expansion."
                else:
                    what = f"{margin_type} margin was unchanged at {curr*100:.1f}%."

            elif "DIVERGENCE" in signal_id:
                if "RECEIVABLES" in signal_id or curr_item.get("metric") == "receivables_revenue_ratio":
                    metric_name = "Receivables/revenue ratio"
                    divergence_context = "This may reflect a change in the balance-sheet measure, revenue, or both; investigate the underlying disclosures."
                elif "INVENTORY" in signal_id or curr_item.get("metric") == "inventory_sales_ratio":
                    metric_name = "Inventory/sales ratio"
                    divergence_context = "This may reflect a change in inventory levels, sales, or both; investigate the underlying disclosures."
                else:
                    raw_m = curr_item.get("metric")
                    metric_name = raw_m.replace("_", " ").title() if raw_m else "Divergence ratio"
                    divergence_context = "This may reflect changes in numerator, denominator, or both; investigate the underlying disclosures."

                unit = curr_item.get("unit", "")
                if unit in ("pure", "%", ""):
                    diff_pp = abs(curr - prev) * 100
                    if curr > prev:
                        what = f"{metric_name} increased by {diff_pp:.1f} percentage points from {prev*100:.1f}% to {curr*100:.1f}%. {divergence_context}"
                    elif curr < prev:
                        what = f"{metric_name} decreased by {diff_pp:.1f} percentage points from {prev*100:.1f}% to {curr*100:.1f}%. {divergence_context}"
                    else:
                        what = f"{metric_name} was unchanged at {curr*100:.1f}%."
                else:
                    from financial_radar.synthesis import format_val
                    if curr > prev:
                        what = f"{metric_name} grew to {format_val(curr, unit)} compared to {format_val(prev, unit)} in prior period. {divergence_context}"
                    elif curr < prev:
                        what = f"{metric_name} declined to {format_val(curr, unit)} compared to {format_val(prev, unit)} in prior period. {divergence_context}"
                    else:
                        what = f"{metric_name} was unchanged at {format_val(curr, unit)}."

            elif "SHARE" in signal_id:
                pct = ((curr - prev) / prev) * 100 if prev != 0 else 0
                from financial_radar.synthesis import format_val
                if curr > prev:
                    what = f"Diluted share count increased by {pct:.1f}% from {format_val(prev, 'shares')} to {format_val(curr, 'shares')}."
                elif curr < prev:
                    what = f"Diluted share count declined by {abs(pct):.1f}% from {format_val(prev, 'shares')} to {format_val(curr, 'shares')}."
                else:
                    what = f"Diluted share count remained unchanged at {format_val(curr, 'shares')}."

            elif "DEBT" in signal_id:
                if curr > prev:
                    what = f"Debt/operating-income increased from {prev:.2f}x to {curr:.2f}x."
                elif curr < prev:
                    what = f"Debt/operating-income decreased from {prev:.2f}x to {curr:.2f}x."
                else:
                    what = f"Debt/operating-income was unchanged at {curr:.2f}x."

            elif signal_id == "EARNINGS_CASH_CONVERSION_DETERIORATION":
                if curr < prev:
                    what = f"Cash conversion declined from {prev:.2f}x to {curr:.2f}x, indicating lower operating cash generation relative to net income."
                elif curr > prev:
                    what = f"Cash conversion increased from {prev:.2f}x to {curr:.2f}x, indicating higher operating cash generation relative to net income."
                else:
                    what = f"Cash conversion was unchanged at {curr:.2f}x."

            elif signal_id == "FREE_CASH_FLOW_DETERIORATION":
                from financial_radar.synthesis import format_val
                unit_curr = curr_item.get("unit", "USD")
                unit_prev = prior_item.get("unit", "USD")
                if curr < prev:
                    what = f"Free cash flow fell from {format_val(prev, unit_prev)} to {format_val(curr, unit_curr)}."
                elif curr > prev:
                    what = f"Free cash flow grew from {format_val(prev, unit_prev)} to {format_val(curr, unit_curr)}."
                else:
                    what = f"Free cash flow was unchanged at {format_val(curr, unit_curr)}."

            elif signal_id == "LIQUIDITY_COMPRESSION":
                if curr < prev:
                    what = f"Liquidity ratio fell from {prev:.2f}x to {curr:.2f}x, indicating reduced short-term coverage."
                elif curr > prev:
                    what = f"Liquidity ratio rose from {prev:.2f}x to {curr:.2f}x, indicating improved short-term coverage."
                else:
                    what = f"Liquidity ratio was unchanged at {curr:.2f}x."

    if signal_id == "RECEIVABLES_REVENUE_DIVERGENCE":
        return {
            "title": "Working-Capital Divergence",
            "what_changed": what,
            "why_it_matters": "Receivables are growing faster than reported revenue, which serves as a screening hypothesis for working-capital absorption; warrants analyst review of collections, payment terms, customer concentration, and revenue recognition footnotes rather than assuming credit impairment.",
            "investigate": [
                "Review revenue recognition footnotes and unbilled receivables.",
                "Check Days Sales Outstanding (DSO) trends and aging schedules.",
                "Examine management commentary on customer credit terms and billing milestones."
            ]
        }
    elif signal_id == "INVENTORY_SALES_DIVERGENCE":
        return {
            "title": "Inventory Divergence",
            "what_changed": what,
            "why_it_matters": "Inventory is growing faster than sales, which serves as a screening indicator of potential inventory build or demand deceleration; warrants analyst review of product mix changes, seasonal stocking, supply chain buffer strategies, or obsolescence reserves.",
            "investigate": [
                "Check for inventory write-downs or obsolescence reserves in footnote disclosures.",
                "Review management discussion on supply chain lead times and demand patterns.",
                "Examine raw materials vs finished goods inventory composition."
            ]
        }
    elif signal_id == "GROSS_MARGIN_COMPRESSION":
        return {
            "title": "Gross Margin Compression",
            "what_changed": what,
            "why_it_matters": "Gross margin compression serves as a screening flag for potential input cost inflation, unfavorable product mix, or discounting; warrants analyst investigation into cost of sales components and pricing disclosures.",
            "investigate": [
                "Review pricing power disclosures and volume vs price realization.",
                "Examine cost of goods sold drivers, input commodities, or freight costs.",
                "Check segment gross margins if disclosed."
            ]
        }
    elif signal_id == "OPERATING_MARGIN_DETERIORATION":
        return {
            "title": "Operating Margin Deterioration",
            "what_changed": what,
            "why_it_matters": "Operating profitability declined relative to revenue, serving as an investigation starting point. The metric change alone does not establish root cause without verifying SG&A leverage, R&D outlays, or one-off items.",
            "investigate": [
                "Review SG&A and overhead expense trends.",
                "Check for restructuring charges, litigation, or impairment charges.",
                "Analyze segment-level operating performance."
            ]
        }
    elif signal_id == "EARNINGS_CASH_CONVERSION_DETERIORATION":
        return {
            "title": "Cash Conversion Decline",
            "what_changed": what,
            "why_it_matters": "Cash conversion (operating cash flow divided by net income) declined, serving as a screening hypothesis of potential earnings quality divergence or working capital drag warranting cash flow statement review.",
            "investigate": [
                "Review working capital line-item changes on the cash flow statement.",
                "Examine non-cash adjustments to net income (depreciation, stock comp, deferred taxes).",
                "Evaluate timing differences between revenue recognition and collections."
            ]
        }
    elif signal_id == "FREE_CASH_FLOW_DETERIORATION":
        return {
            "title": "Free Cash Flow Deterioration",
            "what_changed": what,
            "why_it_matters": "Free cash flow decline serves as a screening indicator of reduced operational cash generation or elevated capital expenditures; warrants review of capex cycle and operating cash drivers.",
            "investigate": [
                "Review capital expenditure trends, maintenance vs growth capex.",
                "Check operating cash flow components and cash interest/taxes paid.",
                "Evaluate free cash flow coverage of fixed charges and dividend obligations."
            ]
        }
    elif signal_id == "DEBT_OPERATING_INCOME_DETERIORATION":
        return {
            "title": "Debt to Operating Income Deterioration",
            "what_changed": what,
            "why_it_matters": "Higher debt relative to operating income serves as a screening flag for leverage and interest coverage capacity, warranting review of debt structure and operating earnings trends.",
            "investigate": [
                "Review recent debt issuance, refinancing, or acquisition financing.",
                "Check debt maturity profile, floating-rate exposure, and interest coverage ratios.",
                "Assess covenant headroom disclosures in credit agreement footnotes."
            ]
        }
    elif signal_id == "LIQUIDITY_COMPRESSION":
        return {
            "title": "Liquidity Compression",
            "what_changed": what,
            "why_it_matters": "Lower liquidity ratios serve as a screening flag for potential short-term funding pressure or working capital absorption, warranting review of quick assets and upcoming debt maturities.",
            "investigate": [
                "Review short-term debt maturities and commercial paper balances.",
                "Check cash, cash equivalents, and marketable securities composition.",
                "Examine committed credit facility availability and liquidity covenants."
            ]
        }
    elif signal_id == "SHARE_COUNT_DILUTION":
        return {
            "title": "Share Count Increase",
            "what_changed": what,
            "why_it_matters": "An increase in diluted share count serves as a screening indicator of potential per-share dilution, warranting review of share-based compensation, equity offerings, or convertible instruments.",
            "investigate": [
                "Review recent equity issuances, secondary offerings, or M&A consideration.",
                "Check stock-based compensation expense and dilution schedules.",
                "Analyze convertible debt conversions or option/warrant exercises."
            ]
        }
    elif signal_id == "MULTI_FACTOR_DETERIORATION_CLUSTER":
        ev_items = []
        if isinstance(evidence_str, str) and evidence_str.strip():
            try:
                ev_items = json.loads(evidence_str)
            except Exception:
                pass
        elif isinstance(evidence_str, (list, tuple)):
            ev_items = list(evidence_str)

        grouped = group_cluster_evidence_by_metric(ev_items) if ev_items else {}
        if grouped:
            metric_names = [m.replace('_', ' ').title() for m in grouped.keys()]
            cluster_what = f"Simultaneous deterioration detected across {len(grouped)} fundamental metrics ({', '.join(metric_names)}) in the same comparison window."
        else:
            cluster_what = "3 or more fundamental deterioration signals fired simultaneously across distinct operational and financial metrics."

        return {
            "title": "Multi-Factor Deterioration Cluster",
            "what_changed": cluster_what,
            "why_it_matters": "Multiple fundamental deterioration signals observed simultaneously suggest correlated operational or financial friction, warranting comprehensive cross-statement review rather than isolated metric analysis. Do not treat individual metrics within the cluster as a single two-point comparison.",
            "investigate": [
                "Review the comprehensive earnings release and 10-Q/10-K disclosures.",
                "Check management guidance and strategic updates across individual metrics.",
                "Assess cumulative impact on liquidity, leverage, and covenant compliance."
            ]
        }

    return {
        "title": signal_id.replace("_", " ").title(),
        "what_changed": what,
        "why_it_matters": "Screening indicator triggering predefined variation thresholds; warrants analyst review of underlying filings and drivers rather than representing a proven conclusion.",
        "investigate": [
            "Review underlying SEC filings and evidence trail.",
            "Inspect disclosures and MD&A commentary."
        ]
    }
