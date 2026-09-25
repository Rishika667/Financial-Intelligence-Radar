import json
from pathlib import Path
from statistics import median
from .models import DataQuality


def load_peer_groups(path="config/peer_groups.json"):
    """Load versioned peer group configuration."""
    data = json.loads(Path(path).read_text())
    return data


def find_peer_group(ticker, peer_groups):
    """Find the peer group containing a given ticker. Returns (group_id, members) or (None, [])."""
    for group in peer_groups.get("groups", []):
        if ticker in group.get("members", []):
            return group["id"], [m for m in group["members"] if m != ticker]
    return None, []


def peer_context(company, metric, observations, members):
    """Compute peer context for a metric. Returns dict with peer median, range, and company position."""
    
    # 1. Identify the company's anchor observation (most recent comparable value)
    own_obs = [
        o for o in observations
        if o.company == company
        and o.metric == metric
        and o.value is not None
        and o.comparable
        and o.quality in (DataQuality.REPORTED, DataQuality.DERIVED, DataQuality.AMENDED)
    ]
    
    if not own_obs:
        return {
            "metric": metric,
            "available": False,
            "company_value": None,
            "peer_median": None,
            "peer_range": None,
            "n_peers": 0,
            "peer_group_version": None,
        }
        
    anchor = sorted(own_obs, key=lambda x: x.period_end)[-1]
    
    # 2. Filter peers strictly against the anchor's context
    peer_values = [
        o.value
        for o in observations
        if o.company in members
        and o.metric == metric
        and o.value is not None
        and o.comparable
        and o.unit == anchor.unit
        and o.period_type == anchor.period_type
        and o.period_end == anchor.period_end
        and o.quality in (DataQuality.REPORTED, DataQuality.DERIVED, DataQuality.AMENDED)
    ]
    
    has_peers = len(peer_values) >= 1
    return {
        "metric": metric,
        "available": has_peers,
        "company_value": anchor.value,
        "peer_median": median(peer_values) if has_peers else None,
        "peer_range": (min(peer_values), max(peer_values)) if has_peers else None,
        "n_peers": len(peer_values),
        "peer_group_version": None,  # Set by caller
    }


def peer_context_for_company(company, observations, peer_groups, metrics=None):
    """Build peer context across all canonical metrics for a company."""
    group_id, members = find_peer_group(company, peer_groups)
    if not members:
        return {"group_id": None, "contexts": [], "version": peer_groups.get("version")}
    if metrics is None:
        metrics = sorted({o.metric for o in observations if o.company == company})
    contexts = []
    for m in metrics:
        ctx = peer_context(company, m, observations, members)
        ctx["peer_group_version"] = peer_groups.get("version")
        ctx["group_id"] = group_id
        if ctx["available"]:
            contexts.append(ctx)
    return {"group_id": group_id, "contexts": contexts, "version": peer_groups.get("version")}