import sqlite3
from typing import Dict, List, Any
from .store import rows

def get_latest_and_prior(c, ticker, metrics):
    obs = rows(c, "SELECT metric, value, period_end, unit, period_type FROM observations WHERE company=? AND period_type='QUARTER' ORDER BY period_end DESC", (ticker,))
    if not obs:
        return {}, {}
        
    latest_end = obs[0]['period_end']
    from datetime import date
    try:
        latest_end_dt = date.fromisoformat(latest_end)
    except ValueError:
        return {}, {}
    
    latest = {}
    prior = {}
    
    # We want YoY comparable quarter (350 to 380 days prior)
    for o in obs:
        m = o['metric']
        if m not in metrics:
            continue
            
        if o['period_end'] == latest_end and m not in latest:
            latest[m] = o
        else:
            try:
                candidate_dt = date.fromisoformat(o['period_end'])
                days_diff = (latest_end_dt - candidate_dt).days
                if 350 <= days_diff <= 380 and m not in prior:
                    prior[m] = o
            except ValueError:
                continue
            
    return latest, prior

def _format_pct(change):
    if change > 0: return f"+{change*100:.1f}%"
    return f"{change*100:.1f}%"
    
def _format_bps(change):
    if change > 0: return f"+{change*10000:.0f} bps"
    return f"{change*10000:.0f} bps"

def synthesize_company(ticker: str, c: sqlite3.Connection) -> Dict[str, List[str]]:
    metrics_to_check = {
        'revenue', 'net_income', 'operating_income', 
        'gross_margin', 'operating_margin', 'net_margin',
        'operating_cash_flow', 'free_cash_flow', 'cash_conversion',
        'cash_and_equivalents', 'debt', 'current_liabilities',
        'share_count'
    }
    
    latest, prior = get_latest_and_prior(c, ticker, metrics_to_check)
    
    synthesis = {
        "observed": [],
        "context": [],
        "investigate": []
    }
    
    if not latest:
        synthesis["observed"].append("No recent financial observations found.")
        return synthesis

    # Evaluate Growth
    growth_trends = []
    if 'revenue' in latest and 'revenue' in prior:
        r_change = (latest['revenue']['value'] - prior['revenue']['value']) / abs(prior['revenue']['value']) if prior['revenue']['value'] != 0 else 0
        synthesis["observed"].append(f"Revenue changed by {_format_pct(r_change)}.")
        growth_trends.append("positive" if r_change > 0 else "negative")
        
    if 'net_income' in latest and 'net_income' in prior:
        ni_change = (latest['net_income']['value'] - prior['net_income']['value']) / abs(prior['net_income']['value']) if prior['net_income']['value'] != 0 else 0
        synthesis["observed"].append(f"Net income changed by {_format_pct(ni_change)}.")

    # Evaluate Profitability
    margin_trends = []
    if 'gross_margin' in latest and 'gross_margin' in prior:
        gm_change = latest['gross_margin']['value'] - prior['gross_margin']['value']
        synthesis["observed"].append(f"Gross margin changed by {_format_bps(gm_change)}.")
        margin_trends.append("expanded" if gm_change > 0 else "contracted")
        
    if 'operating_margin' in latest and 'operating_margin' in prior:
        om_change = latest['operating_margin']['value'] - prior['operating_margin']['value']
        synthesis["observed"].append(f"Operating margin changed by {_format_bps(om_change)}.")
        margin_trends.append("expanded" if om_change > 0 else "contracted")

    # Evaluate Cash
    cash_trends = []
    if 'operating_cash_flow' in latest and 'operating_cash_flow' in prior:
        ocf_change = (latest['operating_cash_flow']['value'] - prior['operating_cash_flow']['value']) / abs(prior['operating_cash_flow']['value']) if prior['operating_cash_flow']['value'] != 0 else 0
        synthesis["observed"].append(f"Operating cash flow changed by {_format_pct(ocf_change)}.")
        cash_trends.append("strengthened" if ocf_change > 0 else "weakened")

    # Pattern identification
    if growth_trends and margin_trends and cash_trends:
        is_growth = growth_trends[0] == "positive"
        is_margin_weak = all(m == "contracted" for m in margin_trends)
        is_cash_weak = cash_trends[0] == "weakened"
        
        if is_growth and is_margin_weak and is_cash_weak:
            synthesis["observed"].append("Observed pattern: Top-line growth remained positive while profitability and cash generation weakened relative to the prior comparable period.")
        elif not is_growth and is_margin_weak:
            synthesis["observed"].append("Observed pattern: Simultaneous top-line and margin deterioration.")
        elif is_growth and not is_margin_weak:
            synthesis["observed"].append("Observed pattern: Growth accompanied by stable or expanding margins.")

    # Context (from events)
    events = rows(c, "SELECT title FROM events WHERE company=? ORDER BY date DESC LIMIT 3", (ticker,))
    if events:
        synthesis["context"].append("Recent 8-K filings establish the following corporate events:")
        for e in events:
            synthesis["context"].append(f"- {e['title']}")
    else:
        synthesis["context"].append("No recent 8-K context located.")
        
    # Investigate
    if "contracted" in margin_trends:
        synthesis["investigate"].append("Review management commentary to determine if margin compression is structural or transient.")
    if cash_trends and cash_trends[0] == "weakened":
        synthesis["investigate"].append("Analyze working capital changes driving cash flow deterioration.")
    if not synthesis["investigate"]:
        synthesis["investigate"].append("Monitor upcoming filings for deviation from observed stable trends.")
        
    return synthesis
