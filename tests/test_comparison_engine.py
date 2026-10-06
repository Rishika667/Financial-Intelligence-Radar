import pytest
from datetime import date, timedelta
from financial_radar.metrics import get_comparison_pair
from financial_radar.models import Observation, DataQuality

def _o(pend, pt, fy, fp, val=100):
    return Observation("A", "rev", val, "U", pend, pt, DataQuality.REPORTED, tuple(), comparable=True, fiscal_year=fy, fiscal_period=fp)

def test_comparison_engine_scenarios():
    q1_24 = _o(date(2023,12,31), "QUARTER", 2024, "Q1")
    q2_24 = _o(date(2024,3,31), "QUARTER", 2024, "Q2")
    q3_24 = _o(date(2024,6,30), "QUARTER", 2024, "Q3")
    q4_24 = _o(date(2024,9,30), "QUARTER", 2024, "Q4")
    
    q1_25 = _o(date(2024,12,31), "QUARTER", 2025, "Q1")
    q2_25 = _o(date(2025,3,31), "QUARTER", 2025, "Q2")
    q3_25 = _o(date(2025,6,30), "QUARTER", 2025, "Q3")
    q4_25 = _o(date(2025,9,30), "QUARTER", 2025, "Q4")
    
    fy_24 = _o(date(2024,9,30), "ANNUAL", 2024, "FY")
    fy_25 = _o(date(2025,9,30), "ANNUAL", 2025, "FY")
    
    obs = [q1_24, q2_24, q3_24, q4_24, q1_25, q2_25, q3_25, q4_25, fy_24, fy_25]

    # YoY 
    assert get_comparison_pair(obs, "rev", "QUARTER", "yoy", current_obs=q1_25)[1] == q1_24
    assert get_comparison_pair(obs, "rev", "QUARTER", "yoy", current_obs=q2_25)[1] == q2_24
    assert get_comparison_pair(obs, "rev", "QUARTER", "yoy", current_obs=q3_25)[1] == q3_24
    assert get_comparison_pair(obs, "rev", "QUARTER", "yoy", current_obs=q4_25)[1] == q4_24
    
    # Sequential
    assert get_comparison_pair(obs, "rev", "QUARTER", "sequential", current_obs=q2_24)[1] == q1_24
    assert get_comparison_pair(obs, "rev", "QUARTER", "sequential", current_obs=q3_24)[1] == q2_24
    assert get_comparison_pair(obs, "rev", "QUARTER", "sequential", current_obs=q4_24)[1] == q3_24
    assert get_comparison_pair(obs, "rev", "QUARTER", "sequential", current_obs=q1_25)[1] == q4_24

    # Annual
    assert get_comparison_pair(obs, "rev", "ANNUAL", "annual", current_obs=fy_25)[1] == fy_24

    # Missing fiscal metadata fallback
    no_meta_1 = _o(date(2023,12,31), "QUARTER", None, None)
    no_meta_2 = _o(date(2024,12,31), "QUARTER", None, None)
    assert get_comparison_pair([no_meta_1, no_meta_2], "rev", "QUARTER", "yoy", current_obs=no_meta_2)[1] == no_meta_1

    # Mismatched fiscal metadata
    mismatch_1 = _o(date(2023,12,31), "QUARTER", 2024, "Q2")
    mismatch_2 = _o(date(2024,12,31), "QUARTER", 2025, "Q1")
    assert get_comparison_pair([mismatch_1, mismatch_2], "rev", "QUARTER", "yoy", current_obs=mismatch_2)[1] is None

    # Same date distance but incorrect fiscal period
    wrong_1 = _o(date(2023,12,31), "QUARTER", 2024, "Q3")
    wrong_2 = _o(date(2024,12,31), "QUARTER", 2025, "Q4")
    assert get_comparison_pair([wrong_1, wrong_2], "rev", "QUARTER", "yoy", current_obs=wrong_2)[1] is None

    # 53-week shifted fiscal calendar
    shift_24 = _o(date(2024,2,3), "QUARTER", 2024, "Q4")
    shift_25 = _o(date(2025,2,1), "QUARTER", 2025, "Q4")
    assert get_comparison_pair([shift_24, shift_25], "rev", "QUARTER", "yoy", current_obs=shift_25)[1] == shift_24
