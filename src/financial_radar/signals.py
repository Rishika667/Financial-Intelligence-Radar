from collections import defaultdict
from .models import DataQuality, Signal
from .core import pct_change
def _ok(*o): return all(x.value is not None and x.comparable and x.quality in (DataQuality.REPORTED,DataQuality.DERIVED) for x in o)
def divergence(kind,balance,revenue,prior_balance,prior_revenue,threshold=.15):
    if not _ok(balance,revenue,prior_balance,prior_revenue): return Signal(kind,balance.company,"","LOW","Cannot assess: missing or incomparable data",(balance,revenue),suppressed_reason="data quality/comparability")
    gap=pct_change(balance.value,prior_balance.value)-pct_change(revenue.value,prior_revenue.value)
    return Signal(kind,balance.company,"HIGH" if gap>=.30 else "MODERATE","HIGH",f"{balance.metric} grew {gap:.0%} faster than revenue.",(balance,revenue,prior_balance,prior_revenue)) if gap>=threshold else None
def margin_compression(current,prior,threshold=.03):
    if not _ok(current,prior): return Signal("GROSS_MARGIN_COMPRESSION",current.company,"","LOW","Cannot assess margin",(current,prior),suppressed_reason="data quality/comparability")
    d=current.value-prior.value
    return Signal("GROSS_MARGIN_COMPRESSION",current.company,"HIGH" if d<=-.06 else "MODERATE","HIGH",f"Gross margin fell {abs(d):.1%} points.",(current,prior)) if d<=-threshold else None
def cluster(signals):
    groups=defaultdict(list)
    for s in signals:
        if s and s.actionable: groups[s.company].append(s)
    return [Signal("MULTI_FACTOR_DETERIORATION_CLUSTER",c,"HIGH","MEDIUM",f"{len(v)} distinct deterioration signals warrant review.",tuple(o for s in v for o in s.evidence)) for c,v in groups.items() if len({s.signal_id for s in v})>=3]