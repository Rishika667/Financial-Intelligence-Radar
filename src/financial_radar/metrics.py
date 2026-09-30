from typing import List, Optional, Tuple, Dict
from datetime import date
from .models import Observation, DataQuality

def get_comparison_pair(
    observations: List[Observation],
    metric: str,
    period_type: str,
    mode: str = "yoy"
) -> Tuple[Optional[Observation], Optional[Observation]]:
    """
    Authoritative comparison methodology.
    Explicitly distinguishes:
    - yoy: Q2 2026 vs Q2 2025 (QUARTER, ~365 days apart)
    - sequential: Q2 2026 vs Q1 2026 (QUARTER, ~90 days apart)
    - annual: FY2026 vs FY2025 (ANNUAL, ~365 days apart)
    """
    # Filter for completely valid observations
    valid_obs = [
        o for o in observations
        if o.metric == metric
        and o.period_type == period_type
        and o.value is not None
        and getattr(o, "quality", None) in (DataQuality.REPORTED, DataQuality.DERIVED, DataQuality.AMENDED)
        and getattr(o, "comparable", True)
    ]
    if not valid_obs:
        return None, None
        
    # Sort strictly by period_end descending
    valid_obs.sort(key=lambda x: x.period_end, reverse=True)
    current = valid_obs[0]
    
    prior = None
    for candidate in valid_obs[1:]:
        # Must have same unit
        if candidate.unit != current.unit:
            continue
            
        days_diff = (current.period_end - candidate.period_end).days
        
        if mode == "yoy":
            if 350 <= days_diff <= 380:
                prior = candidate
                break
        elif mode == "sequential":
            if 80 <= days_diff <= 100:
                prior = candidate
                break
        elif mode == "annual":
            if 350 <= days_diff <= 380:
                prior = candidate
                break
                
    return current, prior

def derive_analytical_metrics(observations: List[Observation]) -> List[Observation]:
    """
    Canonical analytical metric layer.
    Computes standard derived metrics directly into Observations.
    """
    derived = []
    
    # Group by (period_end, period_type)
    groups: Dict[Tuple[date, str], Dict[str, Observation]] = {}
    for o in observations:
        key = (o.period_end, o.period_type)
        if key not in groups:
            groups[key] = {}
        groups[key][o.metric] = o
        
    # Helper to retrieve an INSTANT metric matching the period_end
    def get_instant(m_name, pend):
        if (pend, "INSTANT") in groups:
            return groups[(pend, "INSTANT")].get(m_name)
        return None
        
    for (pend, pt), metrics in groups.items():
        if pt == "INSTANT":
            continue # We derive ratios from the PERIOD metrics (QUARTER/ANNUAL) combined with INSTANT metrics
            
        company = next(iter(metrics.values())).company
        
        # Helper to create derived obs
        def _derive(metric_name: str, value: float, unit: str, bases: List[Observation], quality=DataQuality.DERIVED):
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
                comparable=all(b.comparable for b in bases)
            )
            
        rev = metrics.get("revenue")
        gp = metrics.get("gross_profit")
        oi = metrics.get("operating_income")
        ni = metrics.get("net_income")
        ocf = metrics.get("operating_cash_flow")
        capex = metrics.get("capital_expenditures")
        
        # Gross Margin
        if gp and rev and rev.value and rev.value > 0:
            derived.append(_derive("gross_margin", gp.value / rev.value, "pure", [gp, rev]))
            
        # Operating Margin
        if oi and rev and rev.value and rev.value > 0:
            derived.append(_derive("operating_margin", oi.value / rev.value, "pure", [oi, rev]))
            
        # Net Margin
        if ni and rev and rev.value and rev.value > 0:
            derived.append(_derive("net_margin", ni.value / rev.value, "pure", [ni, rev]))
            
        # Free Cash Flow (if not directly reported but derived from OCF - Capex)
        if ocf and capex and "free_cash_flow" not in metrics:
            derived.append(_derive("free_cash_flow", ocf.value - capex.value, ocf.unit, [ocf, capex]))
            
        # Cash Conversion
        if ocf and ni and ni.value and ni.value > 0:
            derived.append(_derive("cash_conversion", ocf.value / ni.value, "pure", [ocf, ni]))
            
        # Debt / Operating Income
        debt = get_instant("debt", pend)
        if debt and oi and oi.value and oi.value > 0:
            derived.append(_derive("debt_operating_income", debt.value / oi.value, "pure", [debt, oi]))
            
        # Liquidity (Cash / Current Liabilities)
        cash = get_instant("cash_and_equivalents", pend)
        cl = get_instant("current_liabilities", pend)
        if cash and cl and cl.value and cl.value > 0:
            derived.append(_derive("liquidity_ratio", cash.value / cl.value, "pure", [cash, cl]))
            
        # Receivables / Revenue
        ar = get_instant("accounts_receivable", pend)
        if ar and rev and rev.value and rev.value > 0:
            derived.append(_derive("receivables_revenue_ratio", ar.value / rev.value, "pure", [ar, rev]))
            
        # Inventory / Revenue
        inv = get_instant("inventory", pend)
        if inv and rev and rev.value and rev.value > 0:
            derived.append(_derive("inventory_revenue_ratio", inv.value / rev.value, "pure", [inv, rev]))
            
    # Calculate Growth metrics using our canonical comparison engine
    all_obs = observations + derived
    for m in ["revenue", "share_count"]:
        for pt in ["QUARTER", "ANNUAL"]:
            # For each distinct period in the data, try to find a YoY prior
            # To do this safely, we iterate over all periods.
            unique_periods = set(o.period_end for o in all_obs if o.metric == m and o.period_type == pt)
            for pend in unique_periods:
                # We need a sub-list of obs up to this pend to find its prior
                sub_obs = [o for o in all_obs if getattr(o, "period_end", date.min) <= pend]
                curr, prior = get_comparison_pair(sub_obs, m, pt, "annual" if pt == "ANNUAL" else "yoy")
                if curr and prior and prior.value and prior.value != 0:
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
                        period_start=curr.period_start
                    ))

    return derived
