import math
from typing import Optional, List, Dict, Any, Tuple
from .models import FinancialFact, DerivedMetrics


def calculate_revenue_growth(current_rev: Optional[float], prior_rev: Optional[float]) -> Optional[float]:
    if current_rev is None or prior_rev is None:
        return None
    if prior_rev <= 0:
        return None
    return round(((current_rev / prior_rev) - 1.0) * 100.0, 2)


def calculate_operating_margin(operating_income: Optional[float], revenue: Optional[float]) -> Optional[float]:
    if operating_income is None or revenue is None:
        return None
    if revenue <= 0:
        return None
    return round((operating_income / revenue) * 100.0, 2)


def calculate_net_margin(net_income: Optional[float], revenue: Optional[float]) -> Optional[float]:
    if net_income is None or revenue is None:
        return None
    if revenue <= 0:
        return None
    return round((net_income / revenue) * 100.0, 2)


def calculate_free_cash_flow(operating_cash_flow: Optional[float], capital_expenditure: Optional[float]) -> Optional[float]:
    if operating_cash_flow is None or capital_expenditure is None:
        return None
    # Capex is stored as a positive magnitude
    return round(operating_cash_flow - capital_expenditure, 2)


def calculate_cash_conversion(operating_cash_flow: Optional[float], net_income: Optional[float]) -> Tuple[Optional[float], Optional[str]]:
    if operating_cash_flow is None or net_income is None:
        return None, "Missing inputs for cash conversion"
    if net_income == 0:
        return None, "Net income is zero; cash conversion undefined"
    if net_income < 0:
        return None, "Net loss reported; cash conversion ratio misleading"
    if abs(net_income) < 1.0:
        return None, "Near-zero net income; cash conversion ratio distorted"
    
    conversion = round(operating_cash_flow / net_income, 2)
    return conversion, None


def calculate_margin_change_bps(current_margin: Optional[float], prior_margin: Optional[float]) -> Optional[float]:
    """Calculates year-over-year margin shift in basis points (1% = 100 bps)."""
    if current_margin is None or prior_margin is None:
        return None
    return round((current_margin - prior_margin) * 100.0, 1)


def calculate_fcf_margin(free_cash_flow: Optional[float], revenue: Optional[float]) -> Optional[float]:
    """Calculates Free Cash Flow as a percentage of revenue."""
    if free_cash_flow is None or revenue is None:
        return None
    if revenue <= 0:
        return None
    return round((free_cash_flow / revenue) * 100.0, 2)


def calculate_capex_intensity(capital_expenditure: Optional[float], revenue: Optional[float]) -> Optional[float]:
    """Calculates Capital Expenditure as a percentage of revenue."""
    if capital_expenditure is None or revenue is None:
        return None
    if revenue <= 0:
        return None
    return round((capital_expenditure / revenue) * 100.0, 2)


def calculate_reinvestment_rate(capital_expenditure: Optional[float], operating_cash_flow: Optional[float]) -> Tuple[Optional[float], Optional[str]]:
    """Calculates Capex reinvestment as a percentage of Operating Cash Flow."""
    if capital_expenditure is None or operating_cash_flow is None:
        return None, "Missing cash flow inputs"
    if operating_cash_flow <= 0:
        return None, "Operating cash flow is non-positive; reinvestment rate undefined"
    rate = round((capital_expenditure / operating_cash_flow) * 100.0, 2)
    return rate, None


def calculate_operating_leverage(op_inc_growth: Optional[float], rev_growth: Optional[float]) -> Optional[float]:
    """Calculates operating leverage divergence (Operating Income growth % - Revenue growth %)."""
    if op_inc_growth is None or rev_growth is None:
        return None
    return round(op_inc_growth - rev_growth, 2)


def calculate_cagr(start_val: Optional[float], end_val: Optional[float], num_years: int) -> Tuple[Optional[float], Optional[str]]:
    """
    Computes Compound Annual Growth Rate (CAGR) with explicit guard rails.
    num_years represents the number of elapsed growth intervals (e.g. 5 annual observations = 4 growth intervals).
    """
    if start_val is None or end_val is None:
        return None, "Missing start or end period values"
    if num_years <= 0:
        return None, "Period span must be at least 1 interval (>= 2 observations)"
    if start_val <= 0:
        return None, "Base period value is non-positive; CAGR mathematically undefined"
    if end_val <= 0:
        return None, "End period value is non-positive; CAGR mathematically undefined"
    cagr = round(((end_val / start_val) ** (1.0 / num_years) - 1.0) * 100.0, 2)
    return cagr, None


def calculate_margin_volatility(margins: List[Optional[float]]) -> Optional[float]:
    """Computes the sample standard deviation of profit margins across periods."""
    valid = [m for m in margins if m is not None]
    if len(valid) < 2:
        return None
    mean = sum(valid) / len(valid)
    var = sum((x - mean) ** 2 for x in valid) / (len(valid) - 1)
    return round(math.sqrt(var), 2)


def evaluate_growth_consistency(growth_rates: List[Optional[float]]) -> Dict[str, Any]:
    """Evaluates the multi-year revenue growth consistency."""
    valid = [g for g in growth_rates if g is not None]
    if not valid:
        return {
            "label": "INSUFFICIENT_DATA",
            "description": "Insufficient growth history for consistency scoring.",
            "positive_years": 0,
            "total_years": 0,
            "expansion_rate_pct": 0.0
        }
    pos_count = sum(1 for g in valid if g > 0)
    total = len(valid)
    if pos_count == total:
        label = "CONSISTENT_EXPANSION"
        desc = f"Uninterrupted growth across all {total} observed annual intervals."
    elif pos_count >= total * 0.75:
        label = "MOSTLY_POSITIVE"
        desc = f"Positive expansion in {pos_count} of {total} observed intervals."
    elif pos_count == 0:
        label = "CONSISTENT_CONTRACTION"
        desc = f"Revenue contracted across all {total} observed intervals."
    else:
        label = "CYCLICAL_MIXED"
        desc = f"Mixed trajectory with {pos_count} expansion and {total - pos_count} contraction intervals."
    return {
        "label": label,
        "description": desc,
        "positive_years": pos_count,
        "total_years": total,
        "expansion_rate_pct": round((pos_count / total) * 100.0, 1)
    }


def calculate_cumulative_cash_flows(facts: List[FinancialFact]) -> Dict[str, Any]:
    """
    Computes cumulative cash flow generation and reinvestment metrics across complete sets of periods.
    Suppresses incomplete aggregates if any period has missing OCF or Capex.
    """
    if not facts:
        return {}
    sorted_facts = sorted(facts, key=lambda x: x.fiscal_year)
    total_periods = len(sorted_facts)

    valid_facts = [
        f for f in sorted_facts 
        if f.operating_cash_flow is not None and f.capital_expenditure is not None
    ]

    # Check for consecutive fiscal periods
    has_gap = False
    for i in range(1, len(valid_facts)):
        if valid_facts[i].fiscal_year != valid_facts[i - 1].fiscal_year + 1:
            has_gap = True
            break

    is_complete = (len(valid_facts) == total_periods and total_periods >= 5 and not has_gap)

    if len(valid_facts) < 2 or len(valid_facts) != total_periods or has_gap:
        suppress_reason = (
            "Non-consecutive fiscal periods detected in cash flow series" if has_gap
            else "Incomplete cash flow disclosures across fiscal horizon" if len(valid_facts) != total_periods
            else "Insufficient periods with complete cash flow and capex disclosures"
        )
        return {
            "cumulative_ocf": None,
            "cumulative_capex": None,
            "cumulative_fcf": None,
            "cumulative_reinvestment_pct": None,
            "cumulative_fcf_conversion_pct": None,
            "periods_included": len(valid_facts),
            "total_periods": total_periods,
            "is_complete": False,
            "suppressed": True,
            "suppress_reason": suppress_reason,
            "start_period": sorted_facts[0].fiscal_year_label if sorted_facts else "",
            "end_period": sorted_facts[-1].fiscal_year_label if sorted_facts else "",
            "currency": sorted_facts[0].currency if sorted_facts else "",
            "unit": sorted_facts[0].unit if sorted_facts else "",
        }

    cum_ocf = sum(f.operating_cash_flow for f in valid_facts)
    cum_capex = sum(f.capital_expenditure for f in valid_facts)
    cum_fcf = cum_ocf - cum_capex
    reinvest_pct = round((cum_capex / cum_ocf) * 100.0, 2) if cum_ocf > 0 else None
    fcf_conversion_pct = round((cum_fcf / cum_ocf) * 100.0, 2) if cum_ocf > 0 else None

    return {
        "cumulative_ocf": round(cum_ocf, 2),
        "cumulative_capex": round(cum_capex, 2),
        "cumulative_fcf": round(cum_fcf, 2),
        "cumulative_reinvestment_pct": reinvest_pct,
        "cumulative_fcf_conversion_pct": fcf_conversion_pct,
        "periods_included": len(valid_facts),
        "total_periods": total_periods,
        "is_complete": is_complete,
        "suppressed": False,
        "start_period": valid_facts[0].fiscal_year_label,
        "end_period": valid_facts[-1].fiscal_year_label,
        "currency": valid_facts[0].currency,
        "unit": valid_facts[0].unit,
    }


def compute_derived_metrics_for_company(facts: List[FinancialFact]) -> List[DerivedMetrics]:
    # Sort chronologically by fiscal_year
    sorted_facts = sorted(facts, key=lambda x: x.fiscal_year)
    results = []
    
    for i, fact in enumerate(sorted_facts):
        prior_fact = sorted_facts[i - 1] if i > 0 else None
        
        rev_growth = calculate_revenue_growth(
            fact.revenue, 
            prior_fact.revenue if prior_fact else None
        )
        op_inc_growth = calculate_revenue_growth(
            fact.operating_income,
            prior_fact.operating_income if prior_fact else None
        )
        
        op_margin = calculate_operating_margin(fact.operating_income, fact.revenue)
        net_margin = calculate_net_margin(fact.net_income, fact.revenue)
        fcf = calculate_free_cash_flow(fact.operating_cash_flow, fact.capital_expenditure)
        cash_conv, qual_reason = calculate_cash_conversion(fact.operating_cash_flow, fact.net_income)

        # Deeper metrics
        prior_op_margin = calculate_operating_margin(prior_fact.operating_income, prior_fact.revenue) if prior_fact else None
        prior_net_margin = calculate_net_margin(prior_fact.net_income, prior_fact.revenue) if prior_fact else None

        op_margin_bps = calculate_margin_change_bps(op_margin, prior_op_margin)
        net_margin_bps = calculate_margin_change_bps(net_margin, prior_net_margin)
        fcf_margin = calculate_fcf_margin(fcf, fact.revenue)
        capex_intensity = calculate_capex_intensity(fact.capital_expenditure, fact.revenue)
        reinvest_rate, _ = calculate_reinvestment_rate(fact.capital_expenditure, fact.operating_cash_flow)
        op_leverage = calculate_operating_leverage(op_inc_growth, rev_growth)
        
        results.append(DerivedMetrics(
            ticker=fact.ticker,
            fiscal_year=fact.fiscal_year,
            fiscal_year_label=fact.fiscal_year_label,
            revenue_growth_yoy=rev_growth,
            operating_margin=op_margin,
            net_margin=net_margin,
            free_cash_flow=fcf,
            cash_conversion_ratio=cash_conv,
            cash_conversion_qualified_reason=qual_reason,
            operating_margin_change_bps=op_margin_bps,
            net_margin_change_bps=net_margin_bps,
            fcf_margin=fcf_margin,
            capex_intensity=capex_intensity,
            reinvestment_rate=reinvest_rate,
            operating_leverage=op_leverage,
        ))
        
    return results
