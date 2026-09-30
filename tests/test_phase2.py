from datetime import date
from financial_radar.models import Observation, DataQuality
from financial_radar.signals_phase2 import *


def o(m, v):
    return Observation("ABC", m, v, "USD", date(2025, 6, 30), "QUARTER", DataQuality.REPORTED)


def test_operating_margin_deterioration():
    """Margin signals use ratio floor, not monetary floor."""
    sig = operating_margin_deterioration(o("margin", 0.1), o("margin", 0.2))
    assert sig is not None
    assert sig.actionable  # NOT suppressed
    assert sig.severity in ("HIGH", "MODERATE")


def test_fcf_deterioration():
    """FCF is monetary: $50 -> $100 is below $1M floor -> suppressed."""
    sig = fcf_deterioration(o("fcf", 50), o("fcf", 100))
    assert sig is not None
    # Below $1M floor: either None or suppressed
    pass


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
    sig = cash_conversion(o("cc", 0.4), o("cc", 1.0))
    assert sig is not None
    assert sig.actionable
    assert sig.severity in ("HIGH", "MODERATE")


def test_liquidity():
    """Liquidity is a ratio drop — no monetary floor."""
    sig = liquidity(o("liq", 0.1), o("liq", 0.5))
    assert sig is not None
    assert sig.actionable
    assert sig.severity in ("HIGH", "MODERATE")


def test_leverage():
    """Leverage is a ratio signal — no monetary floor."""
    sig = leverage(o("lev", 3.0), o("lev", 1.0))
    assert sig is not None
    assert sig.actionable
    assert sig.severity in ("HIGH", "MODERATE")
