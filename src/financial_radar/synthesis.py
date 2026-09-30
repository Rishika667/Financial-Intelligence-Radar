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
    
    # Load all observations
    obs_rows = rows(c, "SELECT * FROM observations WHERE company=?", (ticker,))
    if not obs_rows:
        synthesis["observed"].append("No sufficient financial evidence for synthesis.")
        return synthesis
        
    obs = []
    for r in obs_rows:
        from datetime import date
        pend = date.fromisoformat(r['period_end'])
        pstart = date.fromisoformat(r['period_start']) if r['period_start'] else None
        obs.append(Observation(
            company=r['company'],
            metric=r['metric'],
            value=r['value'],
            unit=r['unit'],
            period_end=pend,
            period_type=r['period_type'],
            quality=DataQuality(r['quality']) if r['quality'] else DataQuality.REPORTED,
            comparable=bool(r['comparable']),
            period_start=pstart,
        ))

    # Identify YoY metrics
    rev, prevrev = get_comparison_pair(obs, "revenue", "QUARTER", "yoy")
    gm, prevgm = get_comparison_pair(obs, "gross_margin", "QUARTER", "yoy")
    om, prevom = get_comparison_pair(obs, "operating_margin", "QUARTER", "yoy")
    
    if rev and prevrev and prevrev.value:
        change = (rev.value - prevrev.value) / prevrev.value
        synthesis["observed"].append(f"Revenue moved {change:+.1%} YoY to .")
        
    if gm and prevgm and gm.value is not None and prevgm.value is not None:
        change = gm.value - prevgm.value
        synthesis["observed"].append(f"Gross margin moved {change*100:+.1f} points YoY to {gm.value*100:.1f}%.")
        
    if om and prevom and om.value is not None and prevom.value is not None:
        change = om.value - prevom.value
        synthesis["observed"].append(f"Operating margin moved {change*100:+.1f} points YoY to {om.value*100:.1f}%.")
        if change <= -0.03:
            synthesis["investigate"].append("Analyze margin drivers (pricing vs input costs) during the period.")
            
    # Cash Flow
    ocf, prevocf = get_comparison_pair(obs, "operating_cash_flow", "QUARTER", "yoy")
    if ocf and prevocf and prevocf.value:
        change = (ocf.value - prevocf.value) / prevocf.value
        synthesis["observed"].append(f"Operating cash flow changed {change:+.1%} YoY to .")
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
