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
    candidates = [o for o in observations if o.metric == metric and o.period_type == period_type]
    if not candidates:
        return None, None
        
    # Sort strictly by period_end descending
    candidates.sort(key=lambda x: x.period_end, reverse=True)
    current = candidates[0]
    
    prior = None
    for candidate in candidates[1:]:
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
        
    for (pend, pt), metrics in groups.items():
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
                provenance=tuple(set(p for b in bases for p in getattr(b, "provenance", ()))),
                derived_from=tuple(b.metric for b in bases),
                comparable=all(getattr(b, "comparable", True) for b in bases),
                period_start=bases[0].period_start if bases and hasattr(bases[0], "period_start") else None
            )

        rev = metrics.get("revenue")
        gp = metrics.get("gross_profit")
        oi = metrics.get("operating_income")
        ni = metrics.get("net_income")
        ocf = metrics.get("operating_cash_flow")
        fcf = metrics.get("free_cash_flow")
        capex = metrics.get("capex")
        debt = metrics.get("debt")
        cash = metrics.get("cash_and_equivalents")
        cl = metrics.get("current_liabilities")
        shares = metrics.get("share_count")
        
        # Gross Margin
        if rev and gp and rev.value and rev.value != 0:
            derived.append(_derive("gross_margin", gp.value / rev.value, "pure", [gp, rev]))
            
        # Operating Margin
        if rev and oi and rev.value and rev.value != 0:
            derived.append(_derive("operating_margin", oi.value / rev.value, "pure", [oi, rev]))
            
        # Net Margin
        if rev and ni and rev.value and rev.value != 0:
            derived.append(_derive("net_margin", ni.value / rev.value, "pure", [ni, rev]))
            
        # Free Cash Flow (if not directly reported but derived from OCF - Capex)
        if ocf and capex and not fcf and ocf.value is not None and capex.value is not None:
            derived.append(_derive("free_cash_flow", ocf.value - capex.value, ocf.unit, [ocf, capex]))
            fcf = derived[-1]
            
        # Cash Conversion (OCF / Net Income)
        if ocf and ni and ni.value and ni.value != 0:
            derived.append(_derive("cash_conversion", ocf.value / ni.value, "pure", [ocf, ni]))
            
        # Debt / Operating Income
        if debt and oi and oi.value and oi.value > 0:
            # We enforce same period type and end date for simplicity of representation here
            # For debt (INSTANT) vs oi (PERIOD), normalization handles the period_type logic,
            # but if they happen to align here, we compute it. If not, signals will use pair logic.
            pass
            
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
