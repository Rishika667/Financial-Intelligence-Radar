from .models import Signal, DataQuality

def ok(*o):
    return all(
        x is not None and getattr(x, "value", None) is not None and getattr(x, "comparable", True)
        and getattr(x, "quality", None) in (DataQuality.REPORTED, DataQuality.DERIVED, DataQuality.AMENDED)
        for x in o
    )

def _confidence(*o):
    if any(x.quality == DataQuality.DERIVED for x in o): return "MODERATE"
    return "HIGH"

def operating_margin_deterioration(curr, prior):
    if not ok(curr, prior): return None
    d = curr.value - prior.value
    if d <= -0.03:
        sev = "HIGH" if d <= -0.06 else "MODERATE"
        return Signal("OPERATING_MARGIN_DETERIORATION", curr.company, sev, _confidence(curr, prior),
                      f"Operating margin fell {abs(d):.1%} points.", (curr, prior))
    return None

def cash_conversion(curr, prior):
    if not ok(curr, prior): return None
    d = curr.value - prior.value
    if d <= -0.2:
        return Signal("CASH_CONVERSION_DETERIORATION", curr.company, "HIGH" if d <= -0.4 else "MODERATE", _confidence(curr, prior),
                      f"Cash conversion dropped {abs(d):.1%} points.", (curr, prior))
    return None

def fcf_deterioration(curr, prior):
    if not ok(curr, prior): return None
    d = (curr.value - prior.value) / prior.value if prior.value > 0 else 0
    if d <= -0.15:
        return Signal("FREE_CASH_FLOW_DETERIORATION", curr.company, "HIGH" if d <= -0.3 else "MODERATE", _confidence(curr, prior),
                      f"FCF fell {abs(d):.1%}.", (curr, prior))
    return None

def leverage(curr, prior):
    if not ok(curr, prior): return None
    d = curr.value - prior.value
    if d >= 0.5:
        return Signal("DEBT_OPERATING_INCOME_DETERIORATION", curr.company, "HIGH" if d >= 1 else "MODERATE", _confidence(curr, prior),
                      f"Debt/OpInc increased from {prior.value:.2f}x to {curr.value:.2f}x.", (curr, prior))
    return None

def liquidity(curr, prior):
    if not ok(curr, prior): return None
    d = curr.value - prior.value
    if d <= -0.1:
        return Signal("LIQUIDITY_COMPRESSION", curr.company, "HIGH" if d <= -0.2 else "MODERATE", _confidence(curr, prior),
                      f"Liquidity ratio fell from {prior.value:.2f}x to {curr.value:.2f}x.", (curr, prior))
    return None

def dilution(curr, prior):
    if not ok(curr, prior): return None
    d = (curr.value - prior.value) / prior.value if prior.value > 0 else 0
    if d >= 0.05:
        return Signal("SHARE_DILUTION", curr.company, "HIGH" if d >= 0.1 else "MODERATE", _confidence(curr, prior),
                      f"Share count grew {d:.1%}.", (curr, prior))
    return None
