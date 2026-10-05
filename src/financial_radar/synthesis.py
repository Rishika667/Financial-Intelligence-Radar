from .store import rows
from .metrics import get_comparison_pair
from .models import Observation, DataQuality

def format_val(val, unit="USD"):
    if val is None: return "unavailable"
    if unit == "USD":
        if abs(val) >= 1_000_000_000:
            return f"B" if val >= 0 else f"-B"
        elif abs(val) >= 1_000_000:
            return f"M" if val >= 0 else f"-M"
        else:
            return f"" if val >= 0 else f"-"
    elif unit == "shares":
        if abs(val) >= 1_000_000_000:
            return f"{val/1_000_000_000:.1f}B"
        elif abs(val) >= 1_000_000:
            return f"{val/1_000_000:.1f}M"
        else:
            return f"{val:,.0f}"
    elif unit == "pure":
        return f"{val*100:.1f}%"
    return str(val)

def synthesize_company(ticker, c):
    """
    Synthesizes current financial posture strictly using explicit, supported facts.
    """
    synthesis = {
        "observed": [],
        "context": [],
        "investigate": []
    }
    
    from .store import load_observations_for_companies
    obs = load_observations_for_companies(c, [ticker])
    if not obs:
        synthesis["observed"].append("No sufficient financial evidence for synthesis.")
        return synthesis

    rev, prevrev = get_comparison_pair(obs, "revenue", "QUARTER", "yoy")
    gm, prevgm = get_comparison_pair(obs, "gross_margin", "QUARTER", "yoy")
    om, prevom = get_comparison_pair(obs, "operating_margin", "QUARTER", "yoy")
    ocf, prevocf = get_comparison_pair(obs, "operating_cash_flow", "QUARTER", "yoy")
    ar_rev, prev_ar = get_comparison_pair(obs, "receivables_revenue_ratio", "QUARTER", "yoy")
    fcf, prevfcf = get_comparison_pair(obs, "free_cash_flow", "QUARTER", "yoy")
    
    rev_down = False
    ocf_down = False
    ar_up = False
    om_down = False
    fcf_down = False
    
    if rev and prevrev and rev.value is not None and prevrev.value and prevrev.value != 0:
        change = (rev.value - prevrev.value) / abs(prevrev.value)
        direction = "increased" if change > 0 else "decreased"
        if change < 0: rev_down = True
        synthesis["observed"].append(f"Revenue {direction} {abs(change):.1%} YoY to {format_val(rev.value, rev.unit)} from {format_val(prevrev.value, prevrev.unit)}.")

    if gm and prevgm and gm.value is not None and prevgm.value is not None:
        change = gm.value - prevgm.value
        direction = "increased" if change > 0 else "decreased"
        synthesis["observed"].append(f"Gross margin {direction} {abs(change)*100:.1f} points YoY to {format_val(gm.value, gm.unit)} from {format_val(prevgm.value, prevgm.unit)}.")
        
    if om and prevom and om.value is not None and prevom.value is not None:
        change = om.value - prevom.value
        direction = "increased" if change > 0 else "decreased"
        if change < 0: om_down = True
        synthesis["observed"].append(f"Operating margin {direction} {abs(change)*100:.1f} points YoY to {format_val(om.value, om.unit)} from {format_val(prevom.value, prevom.unit)}.")

    if ocf and prevocf and ocf.value is not None and prevocf.value and prevocf.value != 0:
        change = (ocf.value - prevocf.value) / abs(prevocf.value)
        direction = "increased" if change > 0 else "decreased"
        if change < 0: ocf_down = True
        synthesis["observed"].append(f"Operating cash flow {direction} {abs(change):.1%} YoY to {format_val(ocf.value, ocf.unit)} from {format_val(prevocf.value, prevocf.unit)}.")

    if ar_rev and prev_ar and ar_rev.value is not None and prev_ar.value is not None:
        if ar_rev.value > prev_ar.value: ar_up = True
        
    if fcf and prevfcf and fcf.value is not None and prevfcf.value is not None:
        if fcf.value < prevfcf.value: fcf_down = True
        
    # Multi-dimensional cross-metric synthesis
    if rev_down and ar_up and ocf_down:
        synthesis["context"].append("Revenue decline coupled with rising receivables/revenue and falling operating cash flow is consistent with a working-capital deterioration pattern.")
        synthesis["investigate"].append("Review collections, payment terms, customer mix, and revenue-related disclosures.")
        
    if rev_down and om_down and fcf_down:
        synthesis["context"].append("Simultaneous deterioration in revenue, operating margin, and free cash flow mechanically indicates multi-dimensional operating and cash deterioration.")
        synthesis["investigate"].append("Analyze margin drivers, structural cost base, and capital expenditure efficiency.")

    sigs = rows(c, "SELECT signal_id, severity FROM signals WHERE company=? AND suppressed IS NULL", (ticker,))
    if sigs:
        ids = [s['signal_id'] for s in sigs]
        synthesis["observed"].append(f"Detected actionable deterioration signals: {', '.join(ids)}.")
        
    events = rows(c, "SELECT description, form, filed FROM events WHERE company=? ORDER BY filed DESC LIMIT 3", (ticker,))
    if events:
        synthesis["context"].append("Recent SEC disclosures (investigate for drivers):")
        for e in events:
            synthesis["context"].append(f"- {e['form']} ({e['filed']}): {e['description']}")
            
    if not synthesis["investigate"]:
        synthesis["investigate"].append("Standard fundamental tracking recommended.")

    return synthesis
