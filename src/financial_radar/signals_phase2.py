from .models import Signal, DataQuality
from .core import pct_change

def ok(*x):
    return all(a and a.value is not None and a.comparable and a.quality in (DataQuality.REPORTED, DataQuality.DERIVED, DataQuality.AMENDED) for a in x)

def _confidence(*x):
    if any(a and getattr(a, "quality", None) == DataQuality.DERIVED for a in x):
        return "MEDIUM"
    return "HIGH"

def suppressed(id, *x):
    return Signal(
        id, x[0].company, "UNKNOWN", "LOW",
        "Suppressed: unreliable or incomparable evidence", tuple(x),
        suppressed_reason="data quality/comparability"
    )

def _material(val1, val2, economic_floor=1_000_000):
    return abs(val1 - val2) >= economic_floor

def decline(id, current, prior, floor, label):
    if not ok(current, prior):
        return suppressed(id, current, prior)
    
    if not _material(current.value, prior.value):
        return Signal(
            id, current.company, "LOW", _confidence(current, prior),
            "Changes are economically insignificant", (current, prior),
            suppressed_reason="economic insignificance"
        )
        
    d = current.value - prior.value
    if d <= -floor:
        sev = "HIGH" if d <= -2 * floor else "MODERATE"
        return Signal(
            id, current.company, sev, _confidence(current, prior),
            f"{label} deteriorated by {abs(d):.2f}.", (current, prior)
        )
    return None

def operating_deleverage(c, p):
    return decline("OPERATING_DELEVERAGE", c, p, 0.03, "Operating margin")

def fcf_deterioration(c, p):
    floor = max(abs(p.value) * 0.2, 1) if p.value is not None else 1
    return decline("FREE_CASH_FLOW_DETERIORATION", c, p, floor, "Free cash flow")

def dilution(c, p):
    if not ok(c, p):
        return suppressed("SHARE_COUNT_DILUTION", c, p)
    
    if not _material(c.value, p.value, economic_floor=1000): # smaller floor for shares
        return Signal(
            "SHARE_COUNT_DILUTION", c.company, "LOW", _confidence(c, p),
            "Changes are economically insignificant", (c, p),
            suppressed_reason="economic insignificance"
        )
        
    r = pct_change(c.value, p.value)
    if r is not None and r >= 0.03:
        sev = "HIGH" if r >= 0.1 else "MODERATE"
        return Signal("SHARE_COUNT_DILUTION", c.company, sev, _confidence(c, p), f"Share count increased {r:.1%}.", (c, p))
    return None

def ratio_drop(id, a, b, oa, ob, floor, label):
    if not ok(a, b, oa, ob) or b.value <= 0 or ob.value <= 0:
        return suppressed(id, a, b)
    
    if not _material(a.value, oa.value) and not _material(b.value, ob.value):
         return Signal(
            id, a.company, "LOW", _confidence(a, b, oa, ob),
            "Changes are economically insignificant", (a, b, oa, ob),
            suppressed_reason="economic insignificance"
        )
        
    now, old = a.value / b.value, oa.value / ob.value
    if old - now >= floor:
        sev = "HIGH" if old - now >= 2 * floor else "MODERATE"
        return Signal(id, a.company, sev, _confidence(a, b, oa, ob), f"{label} declined from {old:.2f}x to {now:.2f}x.", (a, b, oa, ob))
    return None

def cash_conversion(a, b, oa, ob):
    return ratio_drop("EARNINGS_CASH_CONVERSION_DETERIORATION", a, b, oa, ob, 0.2, "OCF/earnings conversion")

def liquidity(a, b, oa, ob):
    return ratio_drop("LIQUIDITY_COMPRESSION", a, b, oa, ob, 0.1, "Cash/current-liabilities")

def leverage(debt, ebit, old_debt, old_ebit):
    if not ok(debt, ebit, old_debt, old_ebit) or ebit.value <= 0 or old_ebit.value <= 0:
        return suppressed("LEVERAGE_INTEREST_BURDEN", debt, ebit)
        
    if not _material(debt.value, old_debt.value) and not _material(ebit.value, old_ebit.value):
         return Signal(
            "LEVERAGE_INTEREST_BURDEN", debt.company, "LOW", _confidence(debt, ebit, old_debt, old_ebit),
            "Changes are economically insignificant", (debt, ebit, old_debt, old_ebit),
            suppressed_reason="economic insignificance"
        )
        
    now, old = debt.value / ebit.value, old_debt.value / old_ebit.value
    if now - old >= 0.5:
        sev = "HIGH" if now - old >= 1 else "MODERATE"
        return Signal(
            "LEVERAGE_INTEREST_BURDEN", debt.company, sev, _confidence(debt, ebit, old_debt, old_ebit),
            f"Debt/operating-income increased from {old:.2f}x to {now:.2f}x.", (debt, ebit, old_debt, old_ebit)
        )
    return None
