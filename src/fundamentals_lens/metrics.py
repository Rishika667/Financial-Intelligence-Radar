from typing import Optional, List, Dict
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


def calculate_cash_conversion(operating_cash_flow: Optional[float], net_income: Optional[float]) -> tuple[Optional[float], Optional[str]]:
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
        op_margin = calculate_operating_margin(fact.operating_income, fact.revenue)
        net_margin = calculate_net_margin(fact.net_income, fact.revenue)
        fcf = calculate_free_cash_flow(fact.operating_cash_flow, fact.capital_expenditure)
        cash_conv, qual_reason = calculate_cash_conversion(fact.operating_cash_flow, fact.net_income)
        
        results.append(DerivedMetrics(
            ticker=fact.ticker,
            fiscal_year=fact.fiscal_year,
            fiscal_year_label=fact.fiscal_year_label,
            revenue_growth_yoy=rev_growth,
            operating_margin=op_margin,
            net_margin=net_margin,
            free_cash_flow=fcf,
            cash_conversion_ratio=cash_conv,
            cash_conversion_qualified_reason=qual_reason
        ))
        
    return results
