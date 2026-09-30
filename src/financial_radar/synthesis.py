from .store import rows
from .metrics import get_comparison_pair
from .models import Observation, DataQuality

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

    # Identify YoY metrics
    rev, prevrev = get_comparison_pair(obs, "revenue", "QUARTER", "yoy")
    gm, prevgm = get_comparison_pair(obs, "gross_margin", "QUARTER", "yoy")
    om, prevom = get_comparison_pair(obs, "operating_margin", "QUARTER", "yoy")
    
    def _fmt(val):
        if val is None: return "unavailable"
        if val >= 1_000_000_000:
            return f"B"
        if val >= 1_000_000:
            return f"M"
        return f""

    if rev and prevrev and prevrev.value is not None and prevrev.value != 0:
        change = (rev.value - prevrev.value) / prevrev.value if rev.value is not None else None
        if change is not None and rev.value is not None:
            direction = "increased" if change > 0 else "decreased"
            synthesis["observed"].append(f"Revenue {direction} {abs(change):.1%} YoY to {_fmt(rev.value)} from {_fmt(prevrev.value)}.")
        elif change is not None:
            direction = "increased" if change > 0 else "decreased"
            synthesis["observed"].append(f"Revenue {direction} {abs(change):.1%} YoY; current value unavailable.")

    if gm and prevgm and gm.value is not None and prevgm.value is not None:
        change = gm.value - prevgm.value
        direction = "increased" if change > 0 else "decreased"
        synthesis["observed"].append(f"Gross margin {direction} {abs(change)*100:.1f} points YoY to {gm.value*100:.1f}% from {prevgm.value*100:.1f}%.")
        
    if om and prevom and om.value is not None and prevom.value is not None:
        change = om.value - prevom.value
        direction = "increased" if change > 0 else "decreased"
        synthesis["observed"].append(f"Operating margin {direction} {abs(change)*100:.1f} points YoY to {om.value*100:.1f}% from {prevom.value*100:.1f}%.")
        if change <= -0.03:
            synthesis["investigate"].append("Analyze margin drivers (pricing vs input costs) during the period.")
            
    # Cash Flow
    ocf, prevocf = get_comparison_pair(obs, "operating_cash_flow", "QUARTER", "yoy")
    if ocf and prevocf and prevocf.value is not None and prevocf.value != 0:
        change = (ocf.value - prevocf.value) / prevocf.value if ocf.value is not None else None
        if change is not None and ocf.value is not None:
            direction = "increased" if change > 0 else "decreased"
            synthesis["observed"].append(f"Operating cash flow {direction} {abs(change):.1%} YoY to {_fmt(ocf.value)} from {_fmt(prevocf.value)}.")
            if change <= -0.10:
                synthesis["investigate"].append("Determine working capital components impacting cash generation.")
            
    # Signals Context
    sigs = rows(c, "SELECT signal_id, severity FROM signals WHERE company=? AND suppressed IS NULL", (ticker,))
    if sigs:
        ids = [s['signal_id'] for s in sigs]
        synthesis["observed"].append(f"Detected actionable deterioration signals: {', '.join(ids)}.")
        
    # Context (Events)
    events = rows(c, "SELECT description, form, filed FROM events WHERE company=? ORDER BY filed DESC LIMIT 3", (ticker,))
    if events:
        synthesis["context"].append("Recent filings contain the following context:")
        for e in events:
            synthesis["context"].append(f"- {e['form']} ({e['filed']}): {e['description']}")
    else:
        synthesis["context"].append("No recent 8-K context located.")
        
    if not synthesis["investigate"]:
        synthesis["investigate"].append("Standard fundamental tracking recommended.")

    return synthesis
