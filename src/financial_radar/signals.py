from .models import Signal, DataQuality

def _ok(*o):
    return all(
        x is not None and getattr(x, "value", None) is not None and getattr(x, "comparable", True)
        and getattr(x, "quality", None) in (DataQuality.REPORTED, DataQuality.DERIVED, DataQuality.AMENDED, DataQuality.RESTATED)
        for x in o
    ) and (len(o) < 2 or all(getattr(o[i], "unit", None) == getattr(o[0], "unit", None) for i in range(1, len(o))))

def _confidence(*o):
    return "MEDIUM" if any(getattr(x, "quality", None) == DataQuality.DERIVED for x in o) else "HIGH"

def divergence(signal_id, curr, prior):
    if not _ok(curr, prior): return None
    d = curr.value - prior.value
    if d >= 0.15:
        sev = "HIGH" if d >= 0.30 else "MEDIUM"
        return Signal(signal_id, curr.company, sev, _confidence(curr, prior),
                      f"Ratio increased from {prior.value:.1%} to {curr.value:.1%}.", (curr, prior))
    return None

def gross_margin_compression(curr, prior):
    if not _ok(curr, prior): return None
    d = curr.value - prior.value
    if d <= -0.03:
        sev = "HIGH" if d <= -0.06 else "MEDIUM"
        return Signal("GROSS_MARGIN_COMPRESSION", curr.company, sev, _confidence(curr, prior),
                      f"Gross margin fell from {prior.value:.1%} to {curr.value:.1%}.", (curr, prior))
    return None

def operating_margin_deterioration(curr, prior):
    if not _ok(curr, prior): return None
    d = curr.value - prior.value
    if d <= -0.03:
        sev = "HIGH" if d <= -0.06 else "MEDIUM"
        return Signal("OPERATING_MARGIN_DETERIORATION", curr.company, sev, _confidence(curr, prior),
                      f"Operating margin fell from {prior.value:.1%} to {curr.value:.1%}.", (curr, prior))
    return None

def cash_conversion(curr, prior):
    if not _ok(curr, prior): return None
    d = curr.value - prior.value
    if d <= -0.2:
        return Signal("EARNINGS_CASH_CONVERSION_DETERIORATION", curr.company, "HIGH" if d <= -0.4 else "MEDIUM", _confidence(curr, prior),
                      f"Cash conversion fell from {prior.value:.1f}x to {curr.value:.1f}x.", (curr, prior))
    return None

def fcf_deterioration(curr, prior):
    if not _ok(curr, prior): return None
    if prior.value == 0: return None
    d = (curr.value - prior.value) / abs(prior.value)
    # 20% of prior decline
    if d <= -0.20:
        return Signal("FREE_CASH_FLOW_DETERIORATION", curr.company, "HIGH", _confidence(curr, prior),
                      f"FCF fell {abs(d):.1%} from {prior.value:,.1f} to {curr.value:,.1f}.", (curr, prior))
    return None

def leverage(curr, prior):
    if not _ok(curr, prior): return None
    d = curr.value - prior.value
    if d >= 0.5:
        return Signal("DEBT_OPERATING_INCOME_DETERIORATION", curr.company, "HIGH" if d >= 1 else "MEDIUM", _confidence(curr, prior),
                      f"Debt/OpInc increased from {prior.value:.2f}x to {curr.value:.2f}x.", (curr, prior))
    return None

def liquidity(curr, prior):
    if not _ok(curr, prior): return None
    d = curr.value - prior.value
    if d <= -0.1:
        return Signal("LIQUIDITY_COMPRESSION", curr.company, "HIGH" if d <= -0.2 else "MEDIUM", _confidence(curr, prior),
                      f"Liquidity ratio fell from {prior.value:.2f}x to {curr.value:.2f}x.", (curr, prior))
    return None

def dilution(curr, prior):
    if not _ok(curr, prior): return None
    if prior.value == 0: return None
    d = (curr.value - prior.value) / prior.value
    if d >= 0.03:
        return Signal("SHARE_COUNT_DILUTION", curr.company, "HIGH" if d >= 0.10 else "MEDIUM", _confidence(curr, prior),
                      f"Share count grew {d:.1%} from {prior.value:,.1f} to {curr.value:,.1f}.", (curr, prior))
    return None

def cluster(out):
    """
    Group non-suppressed signals into multi-factor clusters.

    Cluster identity = (company, current_period_end, prior_period_end).
    Signals with different comparison windows MUST NOT cluster together
    even when their current period_end is the same.

    Confidence: HIGH only when all components are HIGH; MEDIUM otherwise.
    Evidence ordering is deterministic: sorted by (company, metric, period_end, period_start).
    """
    valid = [s for s in out if not s.suppressed_reason and s.severity in ("HIGH", "MEDIUM", "LOW")]

    from collections import defaultdict
    from datetime import date as _date
    by_window = defaultdict(list)

    for s in valid:
        if not s.evidence:
            continue
        evd_sorted = sorted(s.evidence, key=lambda x: x.period_end)
        curr_period = evd_sorted[-1].period_end
        # Prior period: oldest evidence end — distinguishes comparison windows
        prior_period = evd_sorted[0].period_end
        by_window[(s.company, curr_period, prior_period)].append(s)

    clusters = []
    for (company, curr_period, prior_period), sigs in by_window.items():
        if len(sigs) >= 3:
            obs_set = set()
            has_medium_conf = False
            for sig in sigs:
                if getattr(sig, "confidence", "HIGH") != "HIGH":
                    has_medium_conf = True
                for o in sig.evidence:
                    obs_set.add(o)

            # Deterministic evidence ordering
            obs_list = sorted(list(obs_set), key=lambda x: (
                x.company,
                x.metric,
                x.period_end,
                getattr(x, "period_start", None) or _date.min
            ))

            cluster_conf = "MEDIUM" if has_medium_conf else "HIGH"

            clusters.append(Signal(
                "MULTI_FACTOR_DETERIORATION_CLUSTER",
                company,
                "HIGH",
                cluster_conf,
                f"Detected {len(sigs)} concurrent warnings in period {curr_period.isoformat()}.",
                tuple(obs_list),
                component_signal_ids=tuple(sorted(list(set(s.signal_id for s in sigs))))
            ))
    return clusters
