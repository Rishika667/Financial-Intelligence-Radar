from collections import defaultdict
from .models import DataQuality, Signal
from .core import pct_change

def _ok(*o): 
    """Comparability and completeness gate."""
    return all(x.value is not None and x.comparable and x.quality in (DataQuality.REPORTED, DataQuality.DERIVED) for x in o)

def _confidence(*o):
    """Determine signal confidence based on data quality."""
    if any(x.quality == DataQuality.DERIVED for x in o):
        return "MEDIUM"
    return "HIGH"

def _material(val1, val2, economic_floor=1_000_000):
    """Economic magnitude gate."""
    return abs(val1 - val2) >= economic_floor

def divergence(kind, balance, revenue, prior_balance, prior_revenue, threshold=0.15):
    if not _ok(balance, revenue, prior_balance, prior_revenue): 
        return Signal(
            kind, balance.company, "UNKNOWN", "LOW",
            "Cannot assess: missing or incomparable data",
            (balance, revenue), suppressed_reason="data quality/comparability"
        )
    
    # Materiality: economic floor
    if not _material(balance.value, prior_balance.value) and not _material(revenue.value, prior_revenue.value):
        return Signal(
            kind, balance.company, "LOW", _confidence(balance, revenue, prior_balance, prior_revenue),
            "Changes are economically insignificant",
            (balance, revenue, prior_balance, prior_revenue), suppressed_reason="economic insignificance"
        )
        
    gap = pct_change(balance.value, prior_balance.value) - pct_change(revenue.value, prior_revenue.value)
    
    if gap >= threshold:
        sev = "HIGH" if gap >= 0.30 else "MODERATE"
        conf = _confidence(balance, revenue, prior_balance, prior_revenue)
        return Signal(
            kind, balance.company, sev, conf,
            f"{balance.metric} grew {gap:.0%} faster than revenue.",
            (balance, revenue, prior_balance, prior_revenue)
        )
    return None

def margin_compression(current, prior, threshold=0.03):
    if not _ok(current, prior): 
        return Signal(
            "GROSS_MARGIN_COMPRESSION", current.company, "UNKNOWN", "LOW",
            "Cannot assess margin", (current, prior),
            suppressed_reason="data quality/comparability"
        )
    
    d = current.value - prior.value
    if d <= -threshold:
        sev = "HIGH" if d <= -0.06 else "MODERATE"
        conf = _confidence(current, prior)
        return Signal(
            "GROSS_MARGIN_COMPRESSION", current.company, sev, conf,
            f"Gross margin fell {abs(d):.1%} points.",
            (current, prior)
        )
    return None

def cluster(signals):
    groups = defaultdict(list)
    for s in signals:
        # Priority 6: only cluster valid comparable signals
        if s and s.actionable and s.confidence in ("HIGH", "MEDIUM"):
            groups[s.company].append(s)
            
    out = []
    for c, v in groups.items():
        # unique signal ids
        unique_sigs = {s.signal_id for s in v}
        if len(unique_sigs) >= 3:
            evidence = tuple(o for s in v for o in s.evidence)
            out.append(Signal(
                "MULTI_FACTOR_DETERIORATION_CLUSTER", c, "HIGH", "HIGH",
                f"{len(v)} distinct valid deterioration signals warrant review.",
                evidence
            ))
    return out
