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
    if d >= 0.05:
        sev = "HIGH" if d >= 0.1 else "MODERATE"
        return Signal(signal_id, curr.company, sev, _confidence(curr, prior),
                      f"Ratio increased by {abs(d):.1%} points.", (curr, prior))
    return None

def margin_compression(curr, prior):
    if not _ok(curr, prior): return None
    d = curr.value - prior.value
    if d <= -0.03:
        sev = "HIGH" if d <= -0.06 else "MODERATE"
        return Signal("GROSS_MARGIN_COMPRESSION", curr.company, sev, _confidence(curr, prior),
                      f"Gross margin fell {abs(d):.1%} points.", (curr, prior))
    return None

def cluster(out):
    if len(out) >= 3:
        # Extract unique underlying observations from all component signals
        obs_set = set()
        for sig in out:
            for o in sig.evidence:
                obs_set.add(o)
        return [Signal("MULTIPLE_DETERIORATION", out[0].company, "HIGH", "HIGH",
                       f"Detected {len(out)} concurrent warnings.", tuple(obs_set), component_signal_ids=tuple(s.signal_id for s in out))]
    return []
