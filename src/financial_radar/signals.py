from .models import Signal, DataQuality

def _ok(*o):
    return all(
        x is not None and getattr(x, "value", None) is not None and getattr(x, "comparable", True)
        and getattr(x, "quality", None) in (DataQuality.REPORTED, DataQuality.DERIVED, DataQuality.AMENDED)
        for x in o
    )

def _confidence(*o):
    return "MODERATE" if any(getattr(x, "quality", None) == DataQuality.DERIVED for x in o) else "HIGH"

def divergence(signal_id, curr, prior):
    if not _ok(curr, prior): return None
    d = curr.value - prior.value
    if d >= 0.15:
        sev = "HIGH" if d >= 0.30 else "MODERATE"
        return Signal(signal_id, curr.company, sev, _confidence(curr, prior),
                      f"Ratio increased by {abs(d):.1%} points.", (curr, prior))
    return None

def gross_margin_compression(curr, prior):
    if not _ok(curr, prior): return None
    d = curr.value - prior.value
    if d <= -0.03:
        sev = "HIGH" if d <= -0.06 else "MODERATE"
        return Signal("GROSS_MARGIN_COMPRESSION", curr.company, sev, _confidence(curr, prior),
                      f"Gross margin fell {abs(d):.1%} points.", (curr, prior))
    return None

def operating_margin_deterioration(curr, prior):
    if not _ok(curr, prior): return None
    d = curr.value - prior.value
    if d <= -0.03:
        sev = "HIGH" if d <= -0.06 else "MODERATE"
        return Signal("OPERATING_MARGIN_DETERIORATION", curr.company, sev, _confidence(curr, prior),
                      f"Operating margin fell {abs(d):.1%} points.", (curr, prior))
    return None

def cash_conversion(curr, prior):
    if not _ok(curr, prior): return None
    d = curr.value - prior.value
    if d <= -0.2:
        return Signal("EARNINGS_CASH_CONVERSION_DETERIORATION", curr.company, "HIGH" if d <= -0.4 else "MODERATE", _confidence(curr, prior),
                      f"Cash conversion dropped {abs(d):.1f} points.", (curr, prior))
    return None

def fcf_deterioration(curr, prior):
    if not _ok(curr, prior): return None
    if prior.value == 0: return None
    d = (curr.value - prior.value) / abs(prior.value)
    # 20% of prior +  floor
    if d <= -0.20 and (prior.value - curr.value) >= 1_000_000:
        return Signal("FREE_CASH_FLOW_DETERIORATION", curr.company, "HIGH", _confidence(curr, prior),
                      f"FCF fell {abs(d):.1%} (>).", (curr, prior))
    return None

def leverage(curr, prior):
    if not _ok(curr, prior): return None
    d = curr.value - prior.value
    if d >= 0.5:
        return Signal("DEBT_OPERATING_INCOME_DETERIORATION", curr.company, "HIGH" if d >= 1 else "MODERATE", _confidence(curr, prior),
                      f"Debt/OpInc increased from {prior.value:.2f}x to {curr.value:.2f}x.", (curr, prior))
    return None

def liquidity(curr, prior):
    if not _ok(curr, prior): return None
    d = curr.value - prior.value
    if d <= -0.1:
        return Signal("LIQUIDITY_COMPRESSION", curr.company, "HIGH" if d <= -0.2 else "MODERATE", _confidence(curr, prior),
                      f"Liquidity ratio fell from {prior.value:.2f}x to {curr.value:.2f}x.", (curr, prior))
    return None

def dilution(curr, prior):
    if not _ok(curr, prior): return None
    if prior.value == 0: return None
    d = (curr.value - prior.value) / prior.value
    if d >= 0.03:
        return Signal("SHARE_COUNT_DILUTION", curr.company, "HIGH" if d >= 0.10 else "MODERATE", _confidence(curr, prior),
                      f"Share count grew {d:.1%}.", (curr, prior))
    return None

def cluster(out):
    if len(out) >= 3:
        obs_set = set()
        for sig in out:
            for o in sig.evidence:
                obs_set.add(o)
        return [Signal("MULTI_FACTOR_DETERIORATION_CLUSTER", out[0].company, "HIGH", "HIGH",
                       f"Detected {len(out)} concurrent warnings.", tuple(obs_set), component_signal_ids=tuple(s.signal_id for s in out))]
    return []
