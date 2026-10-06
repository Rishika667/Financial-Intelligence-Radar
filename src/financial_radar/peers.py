import json
from pathlib import Path
from statistics import median
from .models import DataQuality

def load_peer_groups(universe_path="config/sp500_representative_51_2026.json"):
    try:
        data = json.loads(Path(universe_path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {"version": "unknown", "groups": []}
    return {
        "version": data.get("peer_group_version", "v1"),
        "groups": data.get("peer_groups", [])
    }

def find_peer_group(ticker, peer_groups):
    for group in peer_groups.get("groups", []):
        if ticker in group.get("members", []):
            return group.get("peer_group_id", group.get("id")), [m for m in group["members"] if m != ticker]
    return None, []

def peer_context(company, metric, observations, members):
    own_obs = [
        o for o in observations
        if o.company == company and o.metric == metric
        and o.value is not None and o.comparable
        and getattr(o, "quality", None) in (DataQuality.REPORTED, DataQuality.DERIVED, DataQuality.AMENDED, DataQuality.RESTATED)
    ]
    
    if not own_obs:
        return {
            "metric": metric, "available": False, "company_value": None,
            "peer_median": None, "peer_range": None, "n_peers": 0,
            "peer_group_version": None, "unavailable_peers": members
        }
        
# Anchor to the latest QUARTER observation, as analyst signals are quarterly-driven
    q_obs = [o for o in own_obs if o.period_type == "QUARTER"]
    if not q_obs:
        return {
            "metric": metric, "available": False, "company_value": None,
            "peer_median": None, "peer_range": None, "n_peers": 0,
            "peer_group_version": None, "unavailable_peers": members
        }
    anchor = sorted(q_obs, key=lambda x: (x.period_end, x.period_start or "", getattr(x, "quality", None).name if getattr(x, "quality", None) else ""))[-1]
    cfy = getattr(anchor, "fiscal_year", None)
    cfp = getattr(anchor, "fiscal_period", None)
    
    peer_values = []
    found_peers = set()
    
    for p in members:
        if p == company:
            continue
        p_obs = [
            o for o in observations
            if o.company == p and o.metric == metric
            and o.value is not None and o.comparable and o.unit == anchor.unit
            and getattr(o, "quality", None) in (DataQuality.REPORTED, DataQuality.DERIVED, DataQuality.AMENDED, DataQuality.RESTATED)
        ]
        
        match = None
        for o in p_obs:
            pfy = getattr(o, "fiscal_year", None)
            pfp = getattr(o, "fiscal_period", None)
            
            if cfy and cfp and pfy and pfp:
                if o.period_type == anchor.period_type:
                    if cfy == pfy and cfp == pfp:
                        match = o.value
                        break
                    else:
                        continue # Strict semantic match. Do not fall back to date.
            elif o.period_type == anchor.period_type and abs((o.period_end - anchor.period_end).days) <= 45:
                # Fallback to date only when fiscal metadata is genuinely absent
                match = o.value
                break
                
        if match is not None:
            peer_values.append(match)
            found_peers.add(p)
            
    missing = [p for p in members if p not in found_peers and p != company]
    has_peers = len(peer_values) >= 2
    
    p_median = median(peer_values) if has_peers else None
    pos = None
    if has_peers and anchor.value is not None:
        if anchor.value > p_median:
            pos = "Above Median"
        elif anchor.value < p_median:
            pos = "Below Median"
        else:
            pos = "At Median"

    total_peer_count = len([p for p in members if p != company])
    coverage_count = len(peer_values)
    coverage_ratio = coverage_count / total_peer_count if total_peer_count > 0 else 0
    availability_state = f"{coverage_count} / {total_peer_count} peers available"

    return {
        "metric": metric,
        "available": has_peers,
        "company_value": anchor.value,
        "peer_median": p_median,
        "peer_range": (min(peer_values), max(peer_values)) if has_peers else None,
        "n_peers": coverage_count,
        "peer_group_version": None,
        "unavailable_peers": missing,
        "position": pos if has_peers else "Unavailable",
        "coverage_count": coverage_count,
        "total_peer_count": total_peer_count,
        "coverage_ratio": coverage_ratio,
        "availability_state": availability_state
    }

def peer_context_for_company(company, observations, peer_groups, metrics=None):
    group_id, members = find_peer_group(company, peer_groups)
    if not members:
        return {"group_id": "NO_DEFINED_PEER_GROUP", "contexts": [], "version": peer_groups.get("version")}
    if metrics is None:
        metrics = sorted({o.metric for o in observations if o.company == company})
    contexts = []
    for m in metrics:
        ctx = peer_context(company, m, observations, members)
        ctx["peer_group_version"] = peer_groups.get("version")
        ctx["group_id"] = group_id
        contexts.append(ctx)
    return {"group_id": group_id, "contexts": contexts, "version": peer_groups.get("version")}
