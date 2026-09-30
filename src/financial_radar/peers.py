import json
from pathlib import Path
from statistics import median
from .models import DataQuality


def load_peer_groups(universe_path="config/sp500_representative_51_2026.json"):
    """Load explicitly curated peer groups."""
    try:
        data = json.loads(Path(universe_path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {"version": "unknown", "groups": []}

    return {
        "version": data.get("peer_group_version", "v1"),
        "groups": data.get("peer_groups", [])
    }

def find_peer_group(ticker, peer_groups):
    """Find curated peer group containing ticker."""
    for group in peer_groups.get("groups", []):
        if ticker in group.get("members", []):
            return group.get("peer_group_id", group.get("id")), [m for m in group["members"] if m != ticker]
    return None, []


def peer_context(company, metric, observations, members):
    """Compute peer context for a metric. Returns dict with peer median, range, and company position."""
    
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
    
    peer_values = [
        o.value
        for o in observations
        if o.company in members
        and o.metric == metric
        and o.value is not None
        and o.comparable
        and o.unit == anchor.unit
        and o.period_type == anchor.period_type
        and abs((o.period_end - anchor.period_end).days) <= 45  # Fiscal period alignment rule
        and o.quality in (DataQuality.REPORTED, DataQuality.DERIVED, DataQuality.AMENDED)
    ]
    
    # Require at least 2 peers for meaningful comparison
    has_peers = len(peer_values) >= 2
    return {
        "metric": metric,
        "available": has_peers,
        "company_value": anchor.value,
        "peer_median": median(peer_values) if has_peers else None,
        "peer_range": (min(peer_values), max(peer_values)) if has_peers else None,
        "n_peers": len(peer_values),
        "peer_group_version": None,
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
