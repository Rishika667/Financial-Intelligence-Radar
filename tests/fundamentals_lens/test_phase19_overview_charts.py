"""
Tests for Phase 19 Overview Page 2x2 Chart Dashboard functions.
"""

import pytest
import plotly.graph_objects as go

from fundamentals_lens.data_loader import load_financial_facts, load_companies
from fundamentals_lens.metrics import compute_derived_metrics_for_company


def test_overview_chart_dashboard_functions():
    """Verify all 4 Overview dashboard chart functions produce correct Plotly figures with honest labeling."""
    import sys
    from pathlib import Path

    # Import chart functions from fundamentals_lens_app
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from fundamentals_lens_app import (
        plot_revenue_trajectory,
        plot_operating_income_trajectory,
        plot_margins,
        plot_cash_generation_reinvestment,
    )

    facts = load_financial_facts()
    aapl_facts = [f for f in facts if f.ticker == "AAPL"]
    aapl_derived = compute_derived_metrics_for_company(aapl_facts)

    # 1. Revenue Trajectory
    fig_rev = plot_revenue_trajectory(aapl_facts, aapl_derived, "$ Millions", "AAPL")
    assert isinstance(fig_rev, go.Figure)
    assert len(fig_rev.data) == 1
    assert fig_rev.data[0].name == "Revenue"
    assert len(fig_rev.data[0].x) == 5
    assert "Revenue ($ Millions)" in fig_rev.layout.yaxis.title.text

    # 2. Operating Income Trajectory (Dedicated Scale)
    fig_op = plot_operating_income_trajectory(aapl_facts, aapl_derived, "$ Millions")
    assert isinstance(fig_op, go.Figure)
    assert len(fig_op.data) == 1
    assert fig_op.data[0].name == "Operating Income"
    assert "Dedicated Scale" in fig_op.layout.title.text
    assert "Operating Income ($ Millions)" in fig_op.layout.yaxis.title.text

    # 3. Margins Trajectory
    fig_margins = plot_margins(aapl_derived)
    assert isinstance(fig_margins, go.Figure)
    assert len(fig_margins.data) == 2
    assert fig_margins.data[0].name == "Operating Margin %"
    assert fig_margins.data[1].name == "Net Margin %"
    assert fig_margins.layout.yaxis.ticksuffix == "%"

    # 4. Cash Generation & Reinvestment
    fig_cash = plot_cash_generation_reinvestment(aapl_facts, aapl_derived, "$ Millions")
    assert isinstance(fig_cash, go.Figure)
    assert len(fig_cash.data) == 3
    assert fig_cash.data[0].name == "Operating Cash Flow"
    assert "Capex" in fig_cash.data[1].name
    assert "Free Cash Flow" in fig_cash.data[2].name
    assert "FCF = Operating Cash Flow" in fig_cash.layout.title.text


def test_maruti_suzuki_revenue_chart_callout():
    """Verify that Maruti Suzuki revenue chart explicitly incorporates DISC-017 like-for-like callout note."""
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from fundamentals_lens_app import plot_revenue_trajectory

    facts = load_financial_facts()
    maruti_facts = [f for f in facts if f.ticker in ("MARUTI", "MARUTI.BSE")]
    maruti_derived = compute_derived_metrics_for_company(maruti_facts)

    fig_maruti = plot_revenue_trajectory(maruti_facts, maruti_derived, "₹ Crores", "MARUTI.BSE")
    assert isinstance(fig_maruti, go.Figure)
    title_text = fig_maruti.layout.title.text
    assert "DISC-017" in title_text
    assert "20.2%" in title_text
    assert "14.7%" in title_text
