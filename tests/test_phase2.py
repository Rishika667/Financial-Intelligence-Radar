from datetime import date
from financial_radar.models import Observation, DataQuality
from financial_radar.signals_phase2 import *


def o(m, v):
    return Observation("ABC", m, v, "USD", date(2025, 6, 30), "QUARTER", DataQuality.REPORTED)


def test_operating_deleverage():
    """Margin signals use ratio floor, not monetary floor."""
    sig = operating_deleverage(o("margin", 0.1), o("margin", 0.2))
    assert sig is not None
    assert sig.actionable  # NOT suppressed
    assert sig.severity in ("HIGH", "MODERATE")


def test_fcf_deterioration():
    """FCF is monetary: $50 -> $100 is below $1M floor -> suppressed."""
    sig = fcf_deterioration(o("fcf", 50), o("fcf", 100))
    # Below $1M floor: either None or suppressed
    assert sig is None or sig.suppressed_reason is not None


def test_fcf_deterioration_material():
    """FCF with material values fires correctly."""
    sig = fcf_deterioration(o("fcf", 50_000_000), o("fcf", 100_000_000))
    assert sig is not None
    assert sig.actionable
    assert sig.severity in ("HIGH", "MODERATE")


def test_dilution():
    """Share count dilution uses percentage, not monetary floor."""
    sig = dilution(o("shares", 110), o("shares", 100))
    assert sig is not None
    assert sig.actionable
    assert sig.severity in ("HIGH", "MODERATE")


def test_cash_conversion():
    """Cash conversion is a ratio drop — no monetary floor."""
    sig = cash_conversion(o("ocf", 40), o("ni", 100), o("ocf", 100), o("ni", 100))
    assert sig is not None
    assert sig.actionable
    assert sig.severity in ("HIGH", "MODERATE")


def test_liquidity():
    """Liquidity is a ratio drop — no monetary floor."""
    sig = liquidity(o("cash", 10), o("cl", 100), o("cash", 50), o("cl", 100))
    assert sig is not None
    assert sig.actionable
    assert sig.severity in ("HIGH", "MODERATE")


def test_leverage():
    """Leverage is a ratio signal — no monetary floor."""
    sig = leverage(o("debt", 300), o("ebit", 100), o("debt", 100), o("ebit", 100))
    assert sig is not None
    assert sig.actionable
    assert sig.severity in ("HIGH", "MODERATE")
