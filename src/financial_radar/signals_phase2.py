from .models import Signal, DataQuality
from .core import pct_change
import logging

logger = logging.getLogger(__name__)

def ok(*x):
    valid_states = all(
        a and a.value is not None and a.comparable
        and a.quality in (DataQuality.REPORTED, DataQuality.DERIVED, DataQuality.AMENDED)
        for a in x
    )
    if not valid_states:
        return False
    units = {a.unit for a in x if a and a.unit != "pure"}
    return len(units) <= 1

def _confidence(*x):
    if any(a and getattr(a, "quality", None) == DataQuality.DERIVED for a in x):
        return "MEDIUM"
    return "HIGH"

def suppressed(id, *x):
    return Signal(
        id, x[0].company, "UNKNOWN", "LOW",
        "Suppressed: unreliable or incomparable evidence", tuple(x),
        suppressed_reason="data quality/comparability"
    )

def misaligned(id, *x):
    return Signal(
        id, x[0].company, "UNKNOWN", "LOW",
        "Cannot assess: misaligned periods", tuple(x),
        suppressed_reason="misaligned periods"
    )


# ---------------------------------------------------------------------------
# Materiality helpers — metric-type-aware
# ---------------------------------------------------------------------------
def _monetary_material(val1, val2, floor=1_000_000):
    """Economic magnitude gate for monetary values (revenue, debt, cash)."""
    return abs(val1 - val2) >= floor


def _ratio_material(val1, val2, floor=0.005):
    """Materiality gate for ratio/margin signals — always material above floor."""
    return abs(val1 - val2) >= floor


# ---------------------------------------------------------------------------
# Signal functions
# ---------------------------------------------------------------------------
def decline(id, current, prior, floor, label):
    """Decline signal for margin/ratio values — no monetary materiality."""
    if not ok(current, prior):
        return suppressed(id, current, prior)

    d = current.value - prior.value
    if d <= -floor:
        sev = "HIGH" if d <= -2 * floor else "MODERATE"
        return Signal(
            id, current.company, sev, _confidence(current, prior),
            f"{label} deteriorated by {abs(d):.2f}.", (current, prior)
        )
    return None


def operating_margin_deterioration(c, p):
    return decline("OPERATING_MARGIN_DETERIORATION", c, p, 0.03, "Operating margin")


def fcf_deterioration(c, p):
    """FCF is monetary — apply monetary materiality floor."""
    if not ok(c, p):
        return suppressed("FREE_CASH_FLOW_DETERIORATION", c, p)

    if not _monetary_material(c.value, p.value):
        return Signal(
            "FREE_CASH_FLOW_DETERIORATION", c.company, "LOW", _confidence(c, p),
            "Changes are economically insignificant", (c, p),
            suppressed_reason="economic insignificance"
        )

    floor = max(abs(p.value) * 0.2, 1) if p.value is not None else 1
    d = c.value - p.value
    if d <= -floor:
        sev = "HIGH" if d <= -2 * floor else "MODERATE"
        return Signal(
            "FREE_CASH_FLOW_DETERIORATION", c.company, sev, _confidence(c, p),
            f"Free cash flow deteriorated by {abs(d):.2f}.", (c, p)
        )
    return None


def dilution(c, p):
    if not ok(c, p):
        return suppressed("SHARE_COUNT_DILUTION", c, p)

    r = pct_change(c.value, p.value)
    if r is not None and r >= 0.03:
        sev = "HIGH" if r >= 0.1 else "MODERATE"
        return Signal(
            "SHARE_COUNT_DILUTION", c.company, sev, _confidence(c, p),
            f"Share count increased {r:.1%}.", (c, p)
        )
    return None


def ratio_drop(id, a, b, oa, ob, floor, label):
    """Ratio-based signal — no monetary materiality, only ratio floor."""
    if not ok(a, b, oa, ob) or b.value <= 0 or ob.value <= 0:
        return suppressed(id, a, b)
    
    if (a.company != b.company
        or oa.company != ob.company
        or a.period_end != b.period_end
        or oa.period_end != ob.period_end):
        return misaligned(id, a, b, oa, ob)

    now, old = a.value / b.value, oa.value / ob.value
    if old - now >= floor:
        sev = "HIGH" if old - now >= 2 * floor else "MODERATE"
        return Signal(
            id, a.company, sev, _confidence(a, b, oa, ob),
            f"{label} declined from {old:.2f}x to {now:.2f}x.",
            (a, b, oa, ob)
        )
    return None


def cash_conversion(a, b, oa, ob):
    return ratio_drop("EARNINGS_CASH_CONVERSION_DETERIORATION", a, b, oa, ob, 0.2, "OCF/earnings conversion")


def liquidity(a, b, oa, ob):
    return ratio_drop("LIQUIDITY_COMPRESSION", a, b, oa, ob, 0.1, "Cash/current-liabilities")


def leverage(debt, ebit, old_debt, old_ebit):
    """Leverage uses monetary inputs but the signal is ratio-based."""
    if not ok(debt, ebit, old_debt, old_ebit) or ebit.value <= 0 or old_ebit.value <= 0:
        return suppressed("LEVERAGE_INTEREST_BURDEN", debt, ebit)

    if (debt.company != ebit.company
        or old_debt.company != old_ebit.company
        or debt.period_end != ebit.period_end
        or old_debt.period_end != old_ebit.period_end):
        return misaligned("LEVERAGE_INTEREST_BURDEN", debt, ebit, old_debt, old_ebit)

    now, old = debt.value / ebit.value, old_debt.value / old_ebit.value
    if now - old >= 0.5:
        sev = "HIGH" if now - old >= 1 else "MODERATE"
        return Signal(
            "LEVERAGE_INTEREST_BURDEN", debt.company, sev, _confidence(debt, ebit, old_debt, old_ebit),
            f"Debt/operating-income increased from {old:.2f}x to {now:.2f}x.",
            (debt, ebit, old_debt, old_ebit)
        )
    return None
