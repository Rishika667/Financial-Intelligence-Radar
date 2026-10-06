from typing import List, Optional, Tuple, Dict
from datetime import date
from .models import Observation, DataQuality

def get_comparison_pair(
    observations: List[Observation],
    metric: str,
    period_type: str,
    mode: str = "yoy",
    current_obs: Optional[Observation] = None
) -> Tuple[Optional[Observation], Optional[Observation]]:
    """
    Authoritative comparison methodology.
    """
    valid_obs = [
        o for o in observations
        if o.metric == metric
        and o.period_type == period_type
        and o.value is not None
        and getattr(o, "quality", None) in (DataQuality.REPORTED, DataQuality.DERIVED, DataQuality.AMENDED, DataQuality.RESTATED)
        and getattr(o, "comparable", True)
    ]
    if not valid_obs:
        return None, None
        
    valid_obs.sort(key=lambda x: x.period_end, reverse=True)
    current = current_obs if current_obs is not None else valid_obs[0]
    
    prior = None
    for candidate in valid_obs:
        if candidate == current:
            continue
        if candidate.period_end >= current.period_end:
            continue
        if candidate.unit != current.unit:
            continue
            
        # Fiscal semantics first
        cfy = getattr(current, "fiscal_year", None)
        cfp = getattr(current, "fiscal_period", None)
        pfy = getattr(candidate, "fiscal_year", None)
        pfp = getattr(candidate, "fiscal_period", None)
        
        days_diff = (current.period_end - candidate.period_end).days
        
        if cfy and pfy and cfp and pfp:
            is_match = False
            if mode == "yoy":
                if cfy == pfy + 1 and cfp == pfp:
                    is_match = True
            elif mode == "annual":
                if cfy == pfy + 1 and cfp == "FY" and pfp == "FY":
                    is_match = True
            elif mode == "sequential":
                if "Q" in cfp and "Q" in pfp:
                    if (cfy == pfy and int(cfp.replace("Q", "")) == int(pfp.replace("Q", "")) + 1):
                        is_match = True
                    elif cfy == pfy + 1 and cfp == "Q1" and pfp == "Q4":
                        is_match = True
                elif cfp == "H1" and pfp == "FY" and cfy == pfy + 1:
                    is_match = True
            
            if is_match:
                prior = candidate
                break
            else:
                continue # STRICTLY enforce fiscal semantics if both present

        # Fallback to date boundaries ONLY if fiscal info is missing
        if mode in ("yoy", "annual") and (350 <= days_diff <= 380):
            prior = candidate
            break
        elif mode == "sequential" and (80 <= days_diff <= 100):
            prior = candidate
            break
                
    return current, prior

def derive_analytical_metrics(observations: List[Observation]) -> List[Observation]:
    """
    Canonical analytical metric layer.
    Computes standard derived metrics directly into Observations.
    """
    derived = []
    
    # Group by (period_end, period_type, period_start, unit, fiscal_year, fiscal_period)
    groups = {}
    for o in observations:
        key = (o.period_end, o.period_type, getattr(o, "period_start", None), o.unit, getattr(o, "fiscal_year", None), getattr(o, "fiscal_period", None))
        if key not in groups:
            groups[key] = {}
        groups[key][o.metric] = o
        
    def get_instant(m_name, pend, required_unit):
        # Search all obs for INSTANT match
        for o in observations:
            if o.period_type == "INSTANT" and o.period_end == pend and o.metric == m_name and o.unit == required_unit:
                return o
        return None
        
    for key_tuple, metrics in groups.items():
        pend, pt, pstart, req_unit, fy, fp = key_tuple
        if pt == "INSTANT":
            continue
            
        company = next(iter(metrics.values())).company
        
        # Helper to create derived obs
        def _derive(metric_name: str, value: float, unit: str, bases: List[Observation], quality=DataQuality.DERIVED):
            primary = bases[0] if bases else None
            return Observation(
                company=company,
                metric=metric_name,
                value=value,
                unit=unit,
                period_end=pend,
                period_type=pt,
                quality=quality,
                provenance=sum((b.provenance for b in bases), ()),
                derived_from=tuple(b.metric for b in bases),
                comparable=all(b.comparable for b in bases),
                fiscal_year=getattr(primary, "fiscal_year", None) if primary else None,
                fiscal_period=getattr(primary, "fiscal_period", None) if primary else None
            )
            
        rev = metrics.get("revenue")
        gp = metrics.get("gross_profit")
        oi = metrics.get("operating_income")
        ni = metrics.get("net_income")
        ocf = metrics.get("operating_cash_flow")
        capex = metrics.get("capital_expenditures")
        
        # Gross Margin
        if gp and rev and rev.value and rev.value > 0 and gp.unit == rev.unit:
            derived.append(_derive("gross_margin", gp.value / rev.value, "pure", [gp, rev]))
            
        # Operating Margin
        if oi and rev and rev.value and rev.value > 0 and oi.unit == rev.unit:
            derived.append(_derive("operating_margin", oi.value / rev.value, "pure", [oi, rev]))
            
        # Net Margin
        if ni and rev and rev.value and rev.value > 0 and ni.unit == rev.unit:
            derived.append(_derive("net_margin", ni.value / rev.value, "pure", [ni, rev]))
            
        # Free Cash Flow (if not directly reported but derived from OCF - Capex)
        if ocf and capex and ocf.value is not None and capex.value is not None and ocf.unit == capex.unit and "free_cash_flow" not in metrics:
            derived.append(_derive("free_cash_flow", ocf.value - abs(capex.value), ocf.unit, [ocf, capex]))
            
        # Cash Conversion
        if ocf and ni and ni.value and ni.value > 0 and ocf.unit == ni.unit:
            derived.append(_derive("cash_conversion", ocf.value / ni.value, "pure", [ocf, ni]))
            
        # Debt / Operating Income
        debt = get_instant("debt", pend, req_unit)
        if debt and oi and oi.value and oi.value > 0 and debt.unit == oi.unit:
            derived.append(_derive("debt_operating_income", debt.value / oi.value, "pure", [debt, oi]))
            
        # Liquidity (Cash / Current Liabilities)
        cash = get_instant("cash_and_equivalents", pend, req_unit)
        cl = get_instant("current_liabilities", pend, req_unit)
        if cash and cl and cl.value and cl.value > 0 and cash.unit == cl.unit:
            derived.append(_derive("liquidity_ratio", cash.value / cl.value, "pure", [cash, cl]))
            
        # Receivables / Revenue
        ar = get_instant("accounts_receivable", pend, req_unit)
        if ar and rev and rev.value and rev.value > 0 and ar.unit == rev.unit:
            derived.append(_derive("receivables_revenue_ratio", ar.value / rev.value, "pure", [ar, rev]))
            
        # Inventory / Revenue
        inv = get_instant("inventory", pend, req_unit)
        if inv and rev and rev.value and rev.value > 0 and inv.unit == rev.unit:
            derived.append(_derive("inventory_revenue_ratio", inv.value / rev.value, "pure", [inv, rev]))
            
    # Calculate Growth metrics using our canonical comparison engine
    all_obs = observations + derived
    for m in ["revenue", "share_count"]:
        for pt in ["QUARTER", "ANNUAL"]:
            curr_obs_list = [o for o in all_obs if o.metric == m and o.period_type == pt]
            for curr in curr_obs_list:
                _, prior = get_comparison_pair(all_obs, m, pt, "annual" if pt == "ANNUAL" else "yoy", current_obs=curr)
                if prior and prior.value and prior.value != 0:
                    val = (curr.value - prior.value) / prior.value
                    derived.append(Observation(
                        company=curr.company,
                        metric=f"{m}_growth_yoy",
                        value=val,
                        unit="pure",
                        period_end=curr.period_end,
                        period_type=curr.period_type,
                        quality=DataQuality.DERIVED,
                        provenance=tuple(set(list(getattr(curr, "provenance", ())) + list(getattr(prior, "provenance", ())))),
                        derived_from=(curr.metric,),
                        comparable=curr.comparable and prior.comparable,
                        period_start=curr.period_start,
                        fiscal_year=getattr(curr, "fiscal_year", None),
                        fiscal_period=getattr(curr, "fiscal_period", None)
                    ))

    return derived
