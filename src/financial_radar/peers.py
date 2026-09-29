import json
from pathlib import Path
from statistics import median
from .models import DataQuality


def load_peer_groups(universe_path="config/sp500_representative_50_2026.json"):
    """Dynamically generate peer groups from the company universe based on GICS Sectors/Sub-Industries."""
    try:
        data = json.loads(Path(universe_path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {"version": "unknown", "groups": []}

    companies = data.get("companies", [])
    
    # Group by Sector and Sub-Industry
    sub_industries = {}
    sectors = {}
    for c in companies:
        sub = c.get("sub_industry") or c.get("sector") or "Unknown"
        sec = c.get("sector") or "Unknown"
        sub_industries.setdefault(sub, []).append(c["ticker"])
        sectors.setdefault(sec, []).append(c["ticker"])
        
    groups = []
    # If a sub-industry has >= 3 members, it is a tight peer group
    # Otherwise, fall back to sector if sector has >= 3 members
    for c in companies:
        ticker = c["ticker"]
        sub = c.get("sub_industry") or c.get("sector") or "Unknown"
        sec = c.get("sector") or "Unknown"
        
        if len(sub_industries[sub]) >= 3:
            groups.append({"id": f"SubInd:{sub}", "members": sub_industries[sub]})
        elif len(sectors[sec]) >= 3:
            groups.append({"id": f"Sector:{sec}", "members": sectors[sec]})
            
    # Deduplicate groups
    unique_groups = []
    seen = set()
    for g in groups:
        if g["id"] not in seen:
            seen.add(g["id"])
            unique_groups.append(g)
            
    return {"version": data.get("version", "dynamic"), "groups": unique_groups}


def find_peer_group(ticker, peer_groups):
    """Find the tightest peer group containing a given ticker."""
    best_group = None
    best_members = []
    
    # Prefer SubInd over Sector, but load_peer_groups handles naming
    for group in peer_groups.get("groups", []):
        if ticker in group.get("members", []):
            if best_group is None or group["id"].startswith("SubInd:"):
                best_group = group["id"]
                best_members = [m for m in group["members"] if m != ticker]
                
    if best_group:
        return best_group, best_members
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
        and o.period_end == anchor.period_end
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
