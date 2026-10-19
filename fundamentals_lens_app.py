"""
Fundamentals Lens: Evidence-First Financial Intelligence & Research Application
Entry point for Streamlit Community Cloud and local research workbench.
Phase 7 Expanded-Scope Milestone: Deep Fundamentals & Technical Analysis MVP.
"""
import sys
import io
import json
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from pathlib import Path

# Ensure src directory is available on path
ROOT_DIR = Path(__file__).resolve().parent
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from fundamentals_lens.data_loader import (
    load_companies,
    load_financial_facts,
    load_source_register,
    load_coverage_report,
    load_evidence_register,
    load_discrepancy_ledger,
    load_ohlcv_manifest,
    load_dataset_metadata,
    get_company_by_ticker,
    get_facts_for_company
)
from fundamentals_lens.metrics import (
    compute_derived_metrics_for_company,
    calculate_cagr,
    evaluate_growth_consistency,
    calculate_cumulative_cash_flows,
    calculate_margin_volatility
)
from fundamentals_lens.validator import FundamentalsValidator
from fundamentals_lens.insights import NarrativeEngine
from fundamentals_lens.peers import PeerComparisonEngine, PEER_GROUP_METADATA
from fundamentals_lens.exports import ExportGenerator
from fundamentals_lens.models import ValidationStatus, PriceAdjustmentBasis, OHLCVValidationReport
from fundamentals_lens.technical import (
    validate_ohlcv_dataframe,
    validate_ohlcv_dataframe_with_report,
    compute_technical_indicators,
    compute_technical_summary,
    create_price_candlestick_chart,
    create_rsi_chart,
    create_macd_chart,
    create_benchmark_comparison_chart,
    get_ohlcv_csv_template
)

# Page configuration
st.set_page_config(
    page_title="Fundamentals Lens — Financial Research",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Research Styling (CSS)
st.markdown("""
<style>
    /* Main surface and typography */
    .stApp {
        background-color: #F8FAFC;
        color: #0F172A;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    }
    
    /* Top header */
    .lens-header {
        background-color: #FFFFFF;
        border-bottom: 1px solid #E2E8F0;
        padding: 18px 24px;
        margin-top: -40px;
        margin-bottom: 24px;
        border-radius: 8px;
        box-shadow: 0 1px 2px rgba(0, 0, 0, 0.03);
    }
    
    .lens-title {
        font-size: 1.6rem;
        font-weight: 700;
        color: #0F172A;
        margin: 0;
        display: flex;
        align-items: center;
        gap: 10px;
    }
    
    .lens-subtitle {
        font-size: 0.9rem;
        color: #64748B;
        margin-top: 4px;
    }

    /* KPI Cards */
    .kpi-card {
        background-color: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 8px;
        padding: 16px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.03);
        height: 100%;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
    }
    .kpi-label {
        font-size: 0.78rem;
        font-weight: 600;
        color: #64748B;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    .kpi-val {
        font-size: 1.55rem;
        font-weight: 700;
        color: #0F172A;
        margin: 4px 0;
    }
    .kpi-delta {
        font-size: 0.82rem;
        font-weight: 500;
    }
    .kpi-delta.pos { color: #0D9488; }
    .kpi-delta.neg { color: #E11D48; }
    .kpi-delta.neu { color: #64748B; }

    /* Analytical Insight Boxes */
    .insight-box {
        background-color: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-left: 4px solid #0284C7;
        border-radius: 6px;
        padding: 14px 18px;
        margin-bottom: 14px;
    }
    .insight-cat {
        font-size: 0.72rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        color: #0284C7;
    }
    .insight-headline {
        font-size: 1.05rem;
        font-weight: 700;
        color: #0F172A;
        margin: 4px 0 10px 0;
    }
    .insight-section {
        margin-bottom: 6px;
        font-size: 0.88rem;
        line-height: 1.45;
    }

    /* Warning & Caveat Box */
    .caveat-banner {
        background-color: #FFFBEB;
        border-left: 4px solid #F59E0B;
        border-top: 1px solid #FEF3C7;
        border-right: 1px solid #FEF3C7;
        border-bottom: 1px solid #FEF3C7;
        padding: 14px 18px;
        border-radius: 6px;
        margin-bottom: 18px;
        color: #92400E;
        font-size: 0.88rem;
        line-height: 1.45;
    }

    /* Status Badges */
    .badge-pass {
        background-color: #ECFDF5;
        color: #065F46;
        padding: 3px 8px;
        border-radius: 4px;
        font-size: 0.75rem;
        font-weight: 600;
        border: 1px solid #A7F3D0;
        display: inline-block;
    }
    .badge-code1 {
        background-color: #FEF3C7;
        color: #92400E;
        padding: 3px 8px;
        border-radius: 4px;
        font-size: 0.75rem;
        font-weight: 600;
        border: 1px solid #FDE68A;
        display: inline-block;
    }
    .badge-neutral {
        background-color: #F1F5F9;
        color: #334155;
        padding: 3px 8px;
        border-radius: 4px;
        font-size: 0.75rem;
        font-weight: 600;
        border: 1px solid #CBD5E1;
        display: inline-block;
    }
</style>
""", unsafe_allow_html=True)


@st.cache_data
def get_app_data():
    """Cached loader for canonical bundled datasets."""
    companies = load_companies()
    facts = load_financial_facts()
    sources = load_source_register()
    coverage = load_coverage_report()
    evidence_register = load_evidence_register()
    discrepancy_ledger = load_discrepancy_ledger()
    
    facts_by_ticker = {}
    for f in facts:
        facts_by_ticker.setdefault(f.ticker, []).append(f)
        
    for ticker in facts_by_ticker:
        facts_by_ticker[ticker].sort(key=lambda x: x.fiscal_year)
        
    return companies, facts_by_ticker, sources, coverage, evidence_register, discrepancy_ledger


companies, facts_by_ticker, sources, coverage, evidence_register, discrepancy_ledger = get_app_data()
companies_map = {c.ticker: c for c in companies}
coverage_map = {entry["ticker"]: entry for entry in coverage}
discrepancies_count = len(discrepancy_ledger)
dataset_meta = load_dataset_metadata()
snapshot_date = dataset_meta.get("dataset_snapshot_date") or "Unavailable"

# High-level universe statistics computed dynamically from loaded datasets
total_comps = len(companies)
total_periods = sum(len(facts) for facts in facts_by_ticker.values())
total_datapoints = total_periods * 5
target_verified_count = sum(1 for c in coverage if c.get("target_period_status_code") == 0)
target_pending_count = sum(1 for c in coverage if c.get("target_period_status_code") == 1)

metric_counts = FundamentalsValidator.get_metric_verification_counts(evidence_register)
reconciled_metrics = metric_counts["independently_reconciled"]
source_linked_metrics = metric_counts["source_linked_only"]
unverified_metrics = metric_counts["unverified"]
fcf_derived_count = metric_counts["fcf_derived"]

# --- SIDEBAR NAVIGATION ---
st.sidebar.markdown("### **Fundamentals Lens**")
st.sidebar.caption("Evidence-First Financial & Technical Workbench")
st.sidebar.markdown("<div style='font-size:0.85rem; font-weight:600; color:#334155; margin-bottom:8px;'>Created by Rishika Dangayach</div>", unsafe_allow_html=True)

pages = [
    "Overview",
    "Company Analysis",
    "Peer Comparison",
    "Price & Technical Analysis",
    "Data Integrity & Methodology"
]

query_page = st.query_params.get("page", "")
default_page_idx = 0
if query_page:
    qp = str(query_page).lower().strip()
    if "tech" in qp or "price" in qp:
        default_page_idx = 3
    elif "peer" in qp:
        default_page_idx = 2
    elif "company" in qp or "analysis" in qp:
        default_page_idx = 1
    elif "data" in qp or "integ" in qp or "method" in qp:
        default_page_idx = 4
    elif "over" in qp:
        default_page_idx = 0

selected_page = st.sidebar.radio("Navigation", pages, index=default_page_idx)

st.sidebar.markdown("---")
st.sidebar.markdown(f"**Dataset Snapshot:** `{snapshot_date}`")
st.sidebar.markdown("**Universe:** 15 Companies across 5 Peer Groups")
st.sidebar.markdown(f"**Reconciled Metrics:** {reconciled_metrics} / {total_datapoints} ({reconciled_metrics / total_datapoints * 100:.1f}%)")
st.sidebar.markdown(f"**Source-Linked Only:** {source_linked_metrics} metrics")
st.sidebar.markdown(f"**Derived Invariants:** {fcf_derived_count} FCF metrics")
st.sidebar.markdown("**Architecture:** Zero-Cost Deterministic Engine")
st.sidebar.caption("Not investment advice. For financial research only.")

# --- HELPER FUNCTIONS FOR CHARTS ---
def plot_revenue_and_operating_profit(facts, derived, unit):
    years = [f.fiscal_year_label for f in facts]
    revs = [f.revenue for f in facts]
    op_inc = [f.operating_income for f in facts]
    
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=years,
        y=revs,
        name="Revenue",
        marker_color="#0284C7",
        hovertemplate="<b>%{x}</b><br>Revenue: %{y:,.1f} " + unit + "<extra></extra>"
    ))
    fig.add_trace(go.Bar(
        x=years,
        y=op_inc,
        name="Operating Income",
        marker_color="#0D9488",
        hovertemplate="<b>%{x}</b><br>Operating Income: %{y:,.1f} " + unit + "<extra></extra>"
    ))
    
    fig.update_layout(
        title="5-Year Revenue & Operating Profitability",
        barmode="group",
        plot_bgcolor="#FFFFFF",
        paper_bgcolor="#FFFFFF",
        margin=dict(l=40, r=20, t=50, b=40),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        yaxis=dict(title=f"Amount ({unit})", gridcolor="#F1F5F9"),
        xaxis=dict(gridcolor="#F1F5F9")
    )
    return fig


def plot_margins(derived):
    years = [d.fiscal_year_label for d in derived]
    op_margins = [d.operating_margin for d in derived]
    net_margins = [d.net_margin for d in derived]
    
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=years,
        y=op_margins,
        name="Operating Margin %",
        mode="lines+markers",
        line=dict(color="#0284C7", width=3),
        marker=dict(size=8),
        hovertemplate="<b>%{x}</b><br>Operating Margin: %{y:.2f}%<extra></extra>"
    ))
    fig.add_trace(go.Scatter(
        x=years,
        y=net_margins,
        name="Net Margin %",
        mode="lines+markers",
        line=dict(color="#0D9488", width=3, dash="dot"),
        marker=dict(size=8),
        hovertemplate="<b>%{x}</b><br>Net Margin: %{y:.2f}%<extra></extra>"
    ))
    
    fig.update_layout(
        title="Operating & Net Margin Trends (%)",
        plot_bgcolor="#FFFFFF",
        paper_bgcolor="#FFFFFF",
        margin=dict(l=40, r=20, t=50, b=40),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        yaxis=dict(title="Margin (%)", gridcolor="#F1F5F9", ticksuffix="%"),
        xaxis=dict(gridcolor="#F1F5F9")
    )
    return fig


def plot_cash_flows(facts, derived, unit):
    years = [f.fiscal_year_label for f in facts]
    ocf = [f.operating_cash_flow for f in facts]
    capex = [f.capital_expenditure for f in facts]
    fcf = [d.free_cash_flow for d in derived]
    
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=years,
        y=ocf,
        name="Operating Cash Flow",
        marker_color="#0284C7",
        hovertemplate="<b>%{x}</b><br>Operating Cash Flow: %{y:,.1f} " + unit + "<extra></extra>"
    ))
    fig.add_trace(go.Bar(
        x=years,
        y=capex,
        name="Capital Expenditure",
        marker_color="#F59E0B",
        hovertemplate="<b>%{x}</b><br>Capex: %{y:,.1f} " + unit + "<extra></extra>"
    ))
    fig.add_trace(go.Scatter(
        x=years,
        y=fcf,
        name="Free Cash Flow (OCF - Capex)",
        mode="lines+markers",
        line=dict(color="#0D9488", width=3),
        marker=dict(size=8),
        hovertemplate="<b>%{x}</b><br>Free Cash Flow: %{y:,.1f} " + unit + "<extra></extra>"
    ))
    
    fig.update_layout(
        title="Cash Generation & Free Cash Flow",
        barmode="group",
        plot_bgcolor="#FFFFFF",
        paper_bgcolor="#FFFFFF",
        margin=dict(l=40, r=20, t=50, b=40),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        yaxis=dict(title=f"Amount ({unit})", gridcolor="#F1F5F9"),
        xaxis=dict(gridcolor="#F1F5F9")
    )
    return fig


# ==============================================================================
# PAGE 1: OVERVIEW
# ==============================================================================
if selected_page == "Overview":
    st.markdown("""
    <div class="lens-header">
        <div style="float:right; font-weight:600; color:#1E293B; font-size:0.95rem; background:#F1F5F9; padding:4px 12px; border-radius:6px; border:1px solid #CBD5E1; margin-top:2px;">Created by Rishika Dangayach</div>
        <h1 class="lens-title">🔍 Fundamentals Lens</h1>
        <div class="lens-subtitle">Transparent Five-Year Financial Disclosure Intelligence & Quantitative Research Workbench</div>
    </div>
    """, unsafe_allow_html=True)
    
    st.info("ℹ️ **Historical Research Notice:** Fundamentals Lens provides deterministic financial research based on audited annual filings and quantitative technical indicators. It is not an automated trading feed, stock price prediction tool, or investment advisory service.")

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-label">Candidate Universe</div>
            <div class="kpi-val">{total_comps}</div>
            <div class="kpi-delta neu">5 Peer Groups (US & India)</div>
        </div>
        """, unsafe_allow_html=True)
    with col2:
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-label">Audited Annual Periods</div>
            <div class="kpi-val">{total_periods}</div>
            <div class="kpi-delta pos">5 Consecutive Years Each</div>
        </div>
        """, unsafe_allow_html=True)
    with col3:
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-label">Reconciliation Scope</div>
            <div class="kpi-val">{reconciled_metrics} <span style="font-size:0.85rem;font-weight:400;">/ {total_datapoints}</span></div>
            <div class="kpi-delta pos">{reconciled_metrics / total_datapoints * 100:.1f}% Reconciled ({source_linked_metrics} Source-Linked)</div>
        </div>
        """, unsafe_allow_html=True)
    with col4:
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-label">Target Horizon Coverage</div>
            <div class="kpi-val">{target_verified_count} <span style="font-size:0.85rem;font-weight:400;">Included</span></div>
            <div class="kpi-delta neu">{target_pending_count} Horizon Pending 10-K (AAPL, GOOGL, TGT)</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")

    # Research Inquiry Navigation Cards
    st.markdown("### **Research Inquiry Navigation**")
    inq_c1, inq_c2, inq_c3 = st.columns(3)
    with inq_c1:
        st.markdown("""
        <div class="kpi-card">
            <div class="kpi-label">Company Analysis</div>
            <div class="kpi-val" style="font-size:1.15rem;">📊 Deeper Fundamentals</div>
            <p style="font-size:0.85rem; color:#64748B; margin-top:4px;">
                Explore 4 focused tabs: Growth & Scale, Profitability & Margins, Cash Flow & Reinvestment, and Statements & Evidence.
            </p>
        </div>
        """, unsafe_allow_html=True)
    with inq_c2:
        st.markdown("""
        <div class="kpi-card">
            <div class="kpi-label">Peer Comparison</div>
            <div class="kpi-val" style="font-size:1.15rem;">👥 Guarded Benchmarks</div>
            <p style="font-size:0.85rem; color:#64748B; margin-top:4px;">
                Multi-company trajectory analysis, normalized Base=100 indexing, and accounting comparability caveats across 5 peer groups.
            </p>
        </div>
        """, unsafe_allow_html=True)
    with inq_c3:
        st.markdown("""
        <div class="kpi-card">
            <div class="kpi-label">Price & Technical Analysis</div>
            <div class="kpi-val" style="font-size:1.15rem;">📈 Technical MVP</div>
            <p style="font-size:0.85rem; color:#64748B; margin-top:4px;">
                Pure-Python daily OHLCV charts, SMA(20/50/200), RSI(14), MACD(12,26,9), Bollinger Bands, and benchmark normalization.
            </p>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("### **Explore a Company's Five-Year Financial Story**")
    
    selected_ticker = st.selectbox(
        "Select Company to Preview:",
        options=[c.ticker for c in companies],
        format_func=lambda t: f"{t} — {companies_map[t].name} ({companies_map[t].peer_group_name})"
    )
    
    comp = companies_map[selected_ticker]
    c_facts = facts_by_ticker[selected_ticker]
    c_derived = compute_derived_metrics_for_company(c_facts)
    c_cov = coverage_map[selected_ticker]
    unit = comp.standard_unit_label
    
    latest_fact = c_facts[-1]
    latest_der = c_derived[-1]
    first_fact = c_facts[0]
    
    # 4 Quick Snapshot KPIs
    kpi_c1, kpi_c2, kpi_c3, kpi_c4 = st.columns(4)
    with kpi_c1:
        growth_str = f"{latest_der.revenue_growth_yoy:+.1f}% YoY" if latest_der.revenue_growth_yoy is not None else "Baseline"
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-label">Latest Revenue ({latest_fact.fiscal_year_label})</div>
            <div class="kpi-val">{latest_fact.revenue:,.1f} <span style="font-size:1rem;font-weight:400;">{unit}</span></div>
            <div class="kpi-delta {'pos' if (latest_der.revenue_growth_yoy or 0) >= 0 else 'neg'}">{growth_str}</div>
        </div>
        """, unsafe_allow_html=True)
        
    with kpi_c2:
        op_margin_str = f"{latest_der.operating_margin:.1f}%" if latest_der.operating_margin is not None else "N/A"
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-label">Operating Margin</div>
            <div class="kpi-val">{op_margin_str}</div>
            <div class="kpi-delta neu">EBIT: {latest_fact.operating_income:,.1f} {unit}</div>
        </div>
        """, unsafe_allow_html=True)
        
    with kpi_c3:
        fcf = latest_der.free_cash_flow
        fcf_str = f"{fcf:,.1f} {unit}" if fcf is not None else "N/A"
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-label">Free Cash Flow</div>
            <div class="kpi-val">{fcf_str}</div>
            <div class="kpi-delta pos">OCF: {latest_fact.operating_cash_flow:,.1f} {unit}</div>
        </div>
        """, unsafe_allow_html=True)
        
    with kpi_c4:
        if latest_der.cash_conversion_ratio is not None:
            conv_str = f"{latest_der.cash_conversion_ratio:.2f}x"
            conv_sub = "OCF / Net Income"
        else:
            conv_str = "Suppressed"
            conv_sub = latest_der.cash_conversion_qualified_reason or "Distortion guard"
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-label">Cash Conversion</div>
            <div class="kpi-val">{conv_str}</div>
            <div class="kpi-delta neu">{conv_sub}</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("")
    
    # Overview chart & Narrative Preview
    chart_col, insight_col = st.columns([3, 2])
    with chart_col:
        fig_rev = plot_revenue_and_operating_profit(c_facts, c_derived, unit)
        st.plotly_chart(fig_rev, use_container_width=True)
        
    with insight_col:
        st.markdown("#### **What Changed, Why It Matters & What to Investigate**")
        insights = NarrativeEngine.generate_company_insights(c_facts, c_derived)
        for i in insights[:2]:
            st.markdown(f"""
            <div class="insight-box">
                <div class="insight-cat">{i.category.replace('_', ' ')}</div>
                <div class="insight-headline">{i.headline}</div>
                <div class="insight-section"><strong>What changed:</strong> {i.what_changed}</div>
                <div class="insight-section"><strong>Evidence:</strong> <code>{i.evidence}</code></div>
                <div class="insight-section"><strong>Why it matters:</strong> {i.why_it_matters}</div>
            </div>
            """, unsafe_allow_html=True)
            
        st.caption("👉 Navigate to **Company Analysis** for complete multi-year disclosures, deeper fundamental tabs, and official filing citations.")


# ==============================================================================
# PAGE 2: COMPANY ANALYSIS
# ==============================================================================
elif selected_page == "Company Analysis":
    st.markdown("""
    <div class="lens-header">
        <div style="float:right; font-weight:600; color:#1E293B; font-size:0.95rem; background:#F1F5F9; padding:4px 12px; border-radius:6px; border:1px solid #CBD5E1; margin-top:2px;">Created by Rishika Dangayach</div>
        <h1 class="lens-title">📊 Company Fundamentals Analysis</h1>
        <div class="lens-subtitle">Five-Year Audited Statements, Margin Invariants, and Analytical Inquiries</div>
    </div>
    """, unsafe_allow_html=True)

    ticker_opts = [c.ticker for c in companies]
    q_ticker = str(st.query_params.get("ticker", "")).upper().strip()
    default_t_idx = ticker_opts.index(q_ticker) if q_ticker in ticker_opts else 0

    selected_ticker = st.selectbox(
        "Select Company:",
        options=ticker_opts,
        index=default_t_idx,
        format_func=lambda t: f"{t} — {companies_map[t].name} ({companies_map[t].peer_group_name})"
    )
    
    comp = companies_map[selected_ticker]
    c_facts = facts_by_ticker[selected_ticker]
    c_derived = compute_derived_metrics_for_company(c_facts)
    c_cov = coverage_map[selected_ticker]
    unit = comp.standard_unit_label
    
    latest_fact = c_facts[-1]
    latest_der = c_derived[-1]
    first_fact = c_facts[0]

    # Target Horizon Status Badge
    status_badge = (
        f'<span class="badge-pass">Target Horizon ({c_cov["target_horizon_period"]}): VERIFIED INCLUDED</span>'
        if c_cov["target_period_status_code"] == 0
        else f'<span class="badge-code1">Target Horizon ({c_cov["target_horizon_period"]}): PERIOD ONGOING / 10-K PENDING</span>'
    )

    st.markdown(f"""
    ### **{comp.name} ({comp.ticker})**
    **Exchange:** `{comp.exchange}` | **Peer Group:** `{comp.peer_group_name}` | **Country:** `{comp.country}` | **Currency:** `{comp.reporting_currency}` ({unit})  
    **Latest Verified Period:** `{latest_fact.fiscal_year_label}` &nbsp;|&nbsp; {status_badge}
    """, unsafe_allow_html=True)

    st.caption(f"{comp.business_description} • *Peer Context:* {comp.peer_notes}")
    st.markdown("---")

    # Generate insights once for the company
    insights = NarrativeEngine.generate_company_insights(c_facts, c_derived)
    insights_by_cat = {i.category: i for i in insights}

    # 4 FOCUSED TABS: Growth & Scale, Profitability & Margins, Cash Flow & Reinvestment, Statements & Evidence
    tab_growth, tab_margins, tab_cashflow, tab_evidence = st.tabs([
        "📈 Growth & Scale",
        "📊 Profitability & Margins",
        "💵 Cash Flow & Reinvestment",
        "📑 Statements & Evidence"
    ])

    # --------------------------------------------------------------------------
    # TAB 1: GROWTH & SCALE
    # --------------------------------------------------------------------------
    with tab_growth:
        st.markdown("#### **Top-Line Scale & Growth Trajectory**")
        
        cagr, cagr_reason = calculate_cagr(first_fact.revenue, latest_fact.revenue, len(c_facts) - 1)
        cagr_str = f"{cagr:+.2f}%" if cagr is not None else f"N/A ({cagr_reason})"
        growth_rates = [d.revenue_growth_yoy for d in c_derived[1:]]
        consistency = evaluate_growth_consistency(growth_rates)
        abs_change = latest_fact.revenue - first_fact.revenue
        pct_change = ((latest_fact.revenue / first_fact.revenue) - 1.0) * 100.0 if first_fact.revenue > 0 else 0.0

        g_col1, g_col2, g_col3, g_col4 = st.columns(4)
        with g_col1:
            st.markdown(f"""
            <div class="kpi-card">
                <div class="kpi-label">5-Year Revenue CAGR</div>
                <div class="kpi-val">{cagr_str}</div>
                <div class="kpi-delta neu">{len(c_facts) - 1} Annual Intervals</div>
            </div>
            """, unsafe_allow_html=True)
        with g_col2:
            latest_growth = latest_der.revenue_growth_yoy
            st.markdown(f"""
            <div class="kpi-card">
                <div class="kpi-label">Latest YoY Growth</div>
                <div class="kpi-val">{f"{latest_growth:+.2f}%" if latest_growth is not None else "N/A"}</div>
                <div class="kpi-delta {'pos' if (latest_growth or 0) >= 0 else 'neg'}">{latest_fact.fiscal_year_label} vs {c_facts[-2].fiscal_year_label}</div>
            </div>
            """, unsafe_allow_html=True)
        with g_col3:
            st.markdown(f"""
            <div class="kpi-card">
                <div class="kpi-label">5-Year Absolute Expansion</div>
                <div class="kpi-val">{abs_change:+,.1f} <span style="font-size:0.85rem;font-weight:400;">{unit}</span></div>
                <div class="kpi-delta pos">{pct_change:+.1f}% cumulative change</div>
            </div>
            """, unsafe_allow_html=True)
        with g_col4:
            st.markdown(f"""
            <div class="kpi-card">
                <div class="kpi-label">Growth Consistency</div>
                <div class="kpi-val" style="font-size:1.15rem;">{consistency['label'].replace('_', ' ')}</div>
                <div class="kpi-delta neu">{consistency['positive_years']} of {consistency['total_years']} intervals positive</div>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("")
        st.plotly_chart(plot_revenue_and_operating_profit(c_facts, c_derived, unit), use_container_width=True)

        # Revenue trajectory data table
        rev_table = []
        for i, f in enumerate(c_facts):
            d = c_derived[i]
            prior_rev = c_facts[i-1].revenue if i > 0 else None
            abs_delta = f.revenue - prior_rev if prior_rev is not None else None
            rev_table.append({
                "Fiscal Period": f.fiscal_year_label,
                "Period End": f.period_end,
                f"Revenue ({unit})": f"{f.revenue:,.1f}",
                f"Absolute Change ({unit})": f"{abs_delta:+,.1f}" if abs_delta is not None else "— (Baseline)",
                "YoY Growth Rate": f"{d.revenue_growth_yoy:+.2f}%" if d.revenue_growth_yoy is not None else "— (Baseline)",
            })
        st.dataframe(pd.DataFrame(rev_table), hide_index=True, use_container_width=True)

        # Analytical Insight Card
        if "TOP_LINE_GROWTH" in insights_by_cat:
            i = insights_by_cat["TOP_LINE_GROWTH"]
            st.markdown(f"""
            <div class="insight-box">
                <div class="insight-cat">Top-Line Growth Analysis</div>
                <div class="insight-headline">{i.headline}</div>
                <div class="insight-section"><strong>What changed:</strong> {i.what_changed}</div>
                <div class="insight-section"><strong>Evidence:</strong> <code>{i.evidence}</code></div>
                <div class="insight-section"><strong>Why it matters:</strong> {i.why_it_matters}</div>
                <div class="insight-section"><strong>What to investigate:</strong> {i.what_to_investigate}</div>
            </div>
            """, unsafe_allow_html=True)

    # --------------------------------------------------------------------------
    # TAB 2: PROFITABILITY & MARGINS
    # --------------------------------------------------------------------------
    with tab_margins:
        st.markdown("#### **Operating Efficiency & Profitability Margins**")

        op_bps = latest_der.operating_margin_change_bps
        net_bps = latest_der.net_margin_change_bps
        op_lev = latest_der.operating_leverage
        margins = [d.operating_margin for d in c_derived]
        margin_vol = calculate_margin_volatility(margins)

        m_col1, m_col2, m_col3, m_col4 = st.columns(4)
        with m_col1:
            st.markdown(f"""
            <div class="kpi-card">
                <div class="kpi-label">Operating Margin</div>
                <div class="kpi-val">{latest_der.operating_margin:.2f}%</div>
                <div class="kpi-delta neu">EBIT: {latest_fact.operating_income:,.1f} {unit}</div>
            </div>
            """, unsafe_allow_html=True)
        with m_col2:
            st.markdown(f"""
            <div class="kpi-card">
                <div class="kpi-label">YoY Margin Shift</div>
                <div class="kpi-val">{f"{op_bps:+.1f} bps" if op_bps is not None else "N/A"}</div>
                <div class="kpi-delta {'pos' if (op_bps or 0) >= 0 else 'neg'}">1% = 100 bps</div>
            </div>
            """, unsafe_allow_html=True)
        with m_col3:
            st.markdown(f"""
            <div class="kpi-card">
                <div class="kpi-label">Operating Leverage</div>
                <div class="kpi-val">{f"{op_lev:+.2f}%" if op_lev is not None else "N/A"}</div>
                <div class="kpi-delta neu">EBIT Growth − Revenue Growth</div>
            </div>
            """, unsafe_allow_html=True)
        with m_col4:
            st.markdown(f"""
            <div class="kpi-card">
                <div class="kpi-label">5-Yr Margin Volatility</div>
                <div class="kpi-val">{f"{margin_vol:.2f}%" if margin_vol is not None else "N/A"}</div>
                <div class="kpi-delta neu">Sample Standard Deviation (σ)</div>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("")
        st.plotly_chart(plot_margins(c_derived), use_container_width=True)

        # Margin details table
        margin_table = []
        for i, f in enumerate(c_facts):
            d = c_derived[i]
            margin_table.append({
                "Fiscal Period": f.fiscal_year_label,
                f"Operating Income ({unit})": f"{f.operating_income:,.1f}",
                "Operating Margin (%)": f"{d.operating_margin:.2f}%" if d.operating_margin is not None else "—",
                "Op Margin YoY Shift": f"{d.operating_margin_change_bps:+.1f} bps" if d.operating_margin_change_bps is not None else "— (Baseline)",
                "Operating Leverage Spread": f"{d.operating_leverage:+.2f}%" if d.operating_leverage is not None else "— (Baseline)",
                f"Net Income ({unit})": f"{f.net_income:,.1f}",
                "Net Margin (%)": f"{d.net_margin:.2f}%" if d.net_margin is not None else "—",
                "Net Margin YoY Shift": f"{d.net_margin_change_bps:+.1f} bps" if d.net_margin_change_bps is not None else "— (Baseline)",
            })
        st.dataframe(pd.DataFrame(margin_table), hide_index=True, use_container_width=True)

        # Analytical Insight Card
        if "OPERATING_MARGINS" in insights_by_cat:
            i = insights_by_cat["OPERATING_MARGINS"]
            st.markdown(f"""
            <div class="insight-box">
                <div class="insight-cat">Operating Profitability Analysis</div>
                <div class="insight-headline">{i.headline}</div>
                <div class="insight-section"><strong>What changed:</strong> {i.what_changed}</div>
                <div class="insight-section"><strong>Evidence:</strong> <code>{i.evidence}</code></div>
                <div class="insight-section"><strong>Why it matters:</strong> {i.why_it_matters}</div>
                <div class="insight-section"><strong>What to investigate:</strong> {i.what_to_investigate}</div>
            </div>
            """, unsafe_allow_html=True)

    # --------------------------------------------------------------------------
    # TAB 3: CASH FLOW & REINVESTMENT
    # --------------------------------------------------------------------------
    with tab_cashflow:
        st.markdown("#### **Cash Flow Generation & Capital Reinvestment**")

        cum_flows = calculate_cumulative_cash_flows(c_facts)
        cum_ocf = cum_flows.get("cumulative_ocf", 0.0)
        cum_capex = cum_flows.get("cumulative_capex", 0.0)
        cum_fcf = cum_flows.get("cumulative_fcf", 0.0)
        cum_reinvest = cum_flows.get("cumulative_reinvestment_pct")

        cf_c1, cf_c2, cf_c3, cf_c4 = st.columns(4)
        with cf_c1:
            fcf = latest_der.free_cash_flow
            st.markdown(f"""
            <div class="kpi-card">
                <div class="kpi-label">Free Cash Flow</div>
                <div class="kpi-val">{f"{fcf:,.1f}" if fcf is not None else "N/A"} <span style="font-size:0.85rem;font-weight:400;">{unit}</span></div>
                <div class="kpi-delta {'pos' if (fcf or 0) >= 0 else 'neg'}">OCF − Capex</div>
            </div>
            """, unsafe_allow_html=True)
        with cf_c2:
            st.markdown(f"""
            <div class="kpi-card">
                <div class="kpi-label">FCF Margin</div>
                <div class="kpi-val">{f"{latest_der.fcf_margin:.2f}%" if latest_der.fcf_margin is not None else "N/A"}</div>
                <div class="kpi-delta neu">FCF as % of Revenue</div>
            </div>
            """, unsafe_allow_html=True)
        with cf_c3:
            st.markdown(f"""
            <div class="kpi-card">
                <div class="kpi-label">Capex Intensity</div>
                <div class="kpi-val">{f"{latest_der.capex_intensity:.2f}%" if latest_der.capex_intensity is not None else "N/A"}</div>
                <div class="kpi-delta neu">Capex as % of Revenue</div>
            </div>
            """, unsafe_allow_html=True)
        with cf_c4:
            st.markdown(f"""
            <div class="kpi-card">
                <div class="kpi-label">Reinvestment Rate</div>
                <div class="kpi-val">{f"{latest_der.reinvestment_rate:.1f}%" if latest_der.reinvestment_rate is not None else "N/A"}</div>
                <div class="kpi-delta neu">Capex as % of OCF</div>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("")
        # 5-Year Cumulative Cash Flow Passport
        st.markdown(f"""
        <div class="kpi-card" style="margin-bottom:16px;">
            <div class="kpi-label">5-Year Cumulative Cash Flow Passport ({cum_flows.get('start_period', '')} to {cum_flows.get('end_period', '')})</div>
            <div style="display:flex; justify-content:space-between; align-items:center; margin-top:8px; flex-wrap:wrap; gap:12px;">
                <div><strong>Cumulative OCF:</strong> {cum_ocf:,.1f} {unit}</div>
                <div><strong>Cumulative Capex:</strong> {cum_capex:,.1f} {unit}</div>
                <div><strong>Cumulative FCF:</strong> {cum_fcf:,.1f} {unit}</div>
                <div><strong>Cumulative Reinvestment:</strong> {f"{cum_reinvest:.1f}%" if cum_reinvest is not None else "N/A"} of OCF</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.plotly_chart(plot_cash_flows(c_facts, c_derived, unit), use_container_width=True)

        # Cash flow table
        cf_table = []
        for i, f in enumerate(c_facts):
            d = c_derived[i]
            cf_table.append({
                "Fiscal Period": f.fiscal_year_label,
                f"Operating Cash Flow ({unit})": f"{f.operating_cash_flow:,.1f}",
                f"Capital Expenditure ({unit})": f"{f.capital_expenditure:,.1f}",
                f"Free Cash Flow ({unit})": f"{d.free_cash_flow:,.1f}" if d.free_cash_flow is not None else "—",
                "FCF Margin (%)": f"{d.fcf_margin:.2f}%" if d.fcf_margin is not None else "—",
                "Capex Intensity (%)": f"{d.capex_intensity:.2f}%" if d.capex_intensity is not None else "—",
                "Reinvestment Rate (%)": f"{d.reinvestment_rate:.1f}%" if d.reinvestment_rate is not None else "—",
                "Cash Conversion (x)": f"{d.cash_conversion_ratio:.2f}x" if d.cash_conversion_ratio is not None else f"Suppressed ({d.cash_conversion_qualified_reason or 'Guarded'})"
            })
        st.dataframe(pd.DataFrame(cf_table), hide_index=True, use_container_width=True)

        # Analytical Insight Cards for Cash Flow
        for cat in ["CASH_GENERATION", "CASH_CONVERSION", "CAPITAL_INTENSITY"]:
            if cat in insights_by_cat:
                i = insights_by_cat[cat]
                st.markdown(f"""
                <div class="insight-box">
                    <div class="insight-cat">{cat.replace('_', ' ')}</div>
                    <div class="insight-headline">{i.headline}</div>
                    <div class="insight-section"><strong>What changed:</strong> {i.what_changed}</div>
                    <div class="insight-section"><strong>Evidence:</strong> <code>{i.evidence}</code></div>
                    <div class="insight-section"><strong>Why it matters:</strong> {i.why_it_matters}</div>
                </div>
                """, unsafe_allow_html=True)

    # --------------------------------------------------------------------------
    # TAB 4: STATEMENTS & EVIDENCE
    # --------------------------------------------------------------------------
    with tab_evidence:
        st.markdown(f"#### **Audited Financial Facts & Reconciliation Register (in {unit})**")

        table_rows = []
        derived_map = {d.fiscal_year: d for d in c_derived}
        for f in c_facts:
            d = derived_map.get(f.fiscal_year)
            comp_badge = getattr(f, "comparability_flag", None) or "UNKNOWN"
            tier_label = getattr(f, "reconciliation_tier", None) or "UNVERIFIED"
            table_rows.append({
                "Fiscal Period": f.fiscal_year_label,
                "Period End": f.period_end,
                "Basis": f.statement_basis,
                f"Revenue ({unit})": f"{f.revenue:,.1f}",
                f"Operating Income ({unit})": f"{f.operating_income:,.1f}",
                f"Net Income ({unit})": f"{f.net_income:,.1f}",
                f"Operating Cash Flow ({unit})": f"{f.operating_cash_flow:,.1f}",
                f"Capex ({unit})": f"{f.capital_expenditure:,.1f}",
                f"Free Cash Flow ({unit})": f"{d.free_cash_flow:,.1f}" if d and d.free_cash_flow is not None else "—",
                "Comparability": comp_badge,
                "Reconciliation Tier": tier_label
            })
        df_history = pd.DataFrame(table_rows)
        st.dataframe(df_history, hide_index=True, use_container_width=True)

        if latest_fact.accounting_notes:
            st.info(f"💡 **Accounting Comparability Note:** {latest_fact.accounting_notes}")

        st.markdown("---")
        st.markdown("#### **Primary Source Provenance & Regulatory Filing Links**")
        st.caption("Every observation in Fundamentals Lens is traceable to official, audited annual regulatory filings.")
        prov_rows = []
        for f in c_facts:
            prov_rows.append({
                "Fiscal Period": f.fiscal_year_label,
                "Filing Title": f.source_title,
                "Filing Date": f.filing_date,
                "Statement Location": f.statement_location,
                "Accession / Doc ID": f.accession_id,
                "Reference Type": getattr(f, "reference_type", "SEC_ACCESSION"),
                "Source Link": f.source_url
            })
        st.dataframe(pd.DataFrame(prov_rows), hide_index=True, use_container_width=True)

        # Export Center
        st.markdown("---")
        st.markdown("#### **Research Exports**")
        csv_str = ExportGenerator.generate_company_csv(comp, c_facts, c_derived)
        brief_md = ExportGenerator.generate_research_brief(comp, c_facts, c_derived, insights)
        
        exp_c1, exp_c2 = st.columns(2)
        with exp_c1:
            st.download_button(
                label=f"📥 Download {comp.ticker} 5-Year Financials (CSV)",
                data=csv_str,
                file_name=f"{comp.ticker}_fundamentals_5yr.csv",
                mime="text/csv",
                use_container_width=True
            )
        with exp_c2:
            st.download_button(
                label=f"📄 Download {comp.ticker} Research Brief (Markdown)",
                data=brief_md,
                file_name=f"{comp.ticker}_research_brief.md",
                mime="text/markdown",
                use_container_width=True
            )


# ==============================================================================
# PAGE 3: PEER COMPARISON
# ==============================================================================
elif selected_page == "Peer Comparison":
    st.markdown("""
    <div class="lens-header">
        <div style="float:right; font-weight:600; color:#1E293B; font-size:0.95rem; background:#F1F5F9; padding:4px 12px; border-radius:6px; border:1px solid #CBD5E1; margin-top:2px;">Created by Rishika Dangayach</div>
        <h1 class="lens-title">👥 Guarded Peer Comparison</h1>
        <div class="lens-subtitle">Contextual Peer Performance, Normalized Growth & Structural Caveats</div>
    </div>
    """, unsafe_allow_html=True)

    group_keys = list(PEER_GROUP_METADATA.keys())
    selected_group_id = st.selectbox(
        "Select Peer Group:",
        options=group_keys,
        format_func=lambda gid: PEER_GROUP_METADATA[gid].group_name
    )

    group_meta = PEER_GROUP_METADATA[selected_group_id]
    group_companies = [c for c in companies if c.peer_group_id == selected_group_id]

    # Structural Caveats Box
    caveat_html = "<div class='caveat-banner'><strong>⚠️ Comparability Guidance & Structural Caveats:</strong><br>"
    caveat_html += f"<em>{group_meta.comparability_notes}</em><ul>"
    for c in group_meta.structural_caveats:
        caveat_html += f"<li>{c}</li>"
    caveat_html += "</ul></div>"
    st.markdown(caveat_html, unsafe_allow_html=True)

    # Metric Options
    metric_options = {
        "revenue_growth_yoy": "Revenue Growth YoY (%)",
        "operating_margin": "Operating Margin (%)",
        "net_margin": "Net Margin (%)",
        "free_cash_flow": f"Free Cash Flow ({group_meta.standard_unit})",
        "revenue": f"Revenue ({group_meta.standard_unit})",
        "cash_conversion_ratio": "Cash Conversion Ratio (x)"
    }

    # Metric Selector & View Mode
    col_m1, col_m2 = st.columns([3, 2])
    with col_m1:
        selected_metric = st.selectbox(
            "Select Comparison Metric:",
            options=list(metric_options.keys()),
            format_func=lambda k: metric_options[k]
        )
    with col_m2:
        use_indexing = st.checkbox("📈 Normalized Index View (Base = 100.0)", value=False)

    # Build comparison matrix
    if use_indexing:
        matrix = PeerComparisonEngine.build_indexed_peer_matrix(
            companies, facts_by_ticker, selected_group_id, selected_metric
        )
        st.info(
            f"💡 **Normalized Performance Trajectory ({matrix.get('unit')}):** "
            "Scales performance relative to the base year to highlight compound growth trajectories, "
            "independent of differences in absolute scale. Non-positive base values are automatically suppressed."
        )
    else:
        matrix = PeerComparisonEngine.build_peer_comparison_matrix(
            companies, facts_by_ticker, selected_group_id, selected_metric
        )

    # Analytical Safeguard: Surface explicit suppression warnings
    suppressed_series = [s for s in matrix["series"] if s.get("is_suppressed")]
    if suppressed_series:
        st.warning(
            "⚠️ **Analytical Safeguard Triggered:** The following company series are suppressed from direct ranking and comparative plotting due to structural accounting incompatibilities:\n" +
            "\n".join([f"- **{s['ticker']} ({s['company_name']}):** {s.get('suppress_reason')}" for s in suppressed_series])
        )

    # Multi-line comparative chart
    fig_peer = go.Figure()
    palette = ["#0284C7", "#0D9488", "#F59E0B", "#8B5CF6"]
    
    for idx, s in enumerate(matrix["series"]):
        x_vals = [pt["fiscal_year_label"] for pt in s["data"]]
        y_vals = [pt["value"] for pt in s["data"]]
        is_sup = s.get("is_suppressed", False)
        trace_name = f"{s['ticker']} (Suppressed)" if is_sup else f"{s['ticker']} ({s['company_name']})"
        h_template = f"<b>{s['ticker']} (%{{x}})</b><br>SUPPRESSED: {s.get('suppress_reason')}<extra></extra>" if is_sup else f"<b>{s['ticker']} (%{{x}})</b><br>{matrix['unit']}: %{{y}}<extra></extra>"

        fig_peer.add_trace(go.Scatter(
            x=x_vals,
            y=y_vals,
            name=trace_name,
            mode="lines+markers",
            line=dict(width=3, color=palette[idx % len(palette)], dash="dot" if is_sup else "solid"),
            marker=dict(size=8),
            hovertemplate=h_template
        ))

    if use_indexing:
        fig_peer.add_hline(y=100.0, line_dash="dash", line_color="#94A3B8", annotation_text="Base = 100.0")

    unit_label = matrix["unit"]
    chart_title = f"Peer Comparison: {metric_options[selected_metric]}" + (" (Indexed Base = 100.0)" if use_indexing else "")
    fig_peer.update_layout(
        title=chart_title,
        plot_bgcolor="#FFFFFF",
        paper_bgcolor="#FFFFFF",
        margin=dict(l=40, r=20, t=50, b=40),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        yaxis=dict(title=unit_label, gridcolor="#F1F5F9"),
        xaxis=dict(gridcolor="#F1F5F9")
    )
    st.plotly_chart(fig_peer, use_container_width=True)

    # Side-by-side comparison table
    st.markdown(f"### **Peer Comparison Table: {metric_options[selected_metric]}**")
    if matrix.get("metric_note"):
        st.info(f"💡 **Accounting Definition Note:** {matrix['metric_note']}")
    
    period_year_map = {}
    for s in matrix["series"]:
        for pt in s["data"]:
            yr = pt.get("fiscal_year")
            lbl = pt.get("fiscal_year_label")
            if yr is not None and lbl:
                period_year_map[yr] = lbl

    sorted_yrs = sorted(period_year_map.keys())
    all_period_labels = [period_year_map[y] for y in sorted_yrs]

    pivot_data = {"Fiscal Period": all_period_labels}
    for s in matrix["series"]:
        col_name = f"{s['ticker']} ({s['company_name']})"
        if s.get("is_suppressed"):
            pivot_data[col_name] = [f"Suppressed ({s.get('suppress_reason')})"] * len(all_period_labels)
        else:
            series_points = {pt["fiscal_year"]: pt["value"] for pt in s["data"]}
            val_fmt = "{:.1f}" if use_indexing else "{:,.1f}"
            col_vals = []
            for y in sorted_yrs:
                val = series_points.get(y)
                if val is not None:
                    col_vals.append(f"{val_fmt.format(val)} {unit_label}")
                else:
                    col_vals.append("— (Not Reported / Pending)")
            pivot_data[col_name] = col_vals

    df_pivot = pd.DataFrame(pivot_data)
    st.dataframe(df_pivot, hide_index=True, use_container_width=True)

    # Export peer comparison
    peer_csv = df_pivot.to_csv(index=False)
    file_prefix = f"{selected_group_id}_{selected_metric}" + ("_indexed" if use_indexing else "")
    st.download_button(
        label=f"📥 Download {group_meta.group_name} Comparison (CSV)",
        data=peer_csv,
        file_name=f"{file_prefix}_comparison.csv",
        mime="text/csv"
    )


# ==============================================================================
# PAGE 4: PRICE & TECHNICAL ANALYSIS (MVP)
# ==============================================================================
elif selected_page == "Price & Technical Analysis":
    st.markdown("""
    <div class="lens-header" style="margin-bottom:8px; padding-bottom:4px;">
        <div style="float:right; font-weight:600; color:#1E293B; font-size:0.85rem; background:#F1F5F9; padding:4px 12px; border-radius:6px; border:1px solid #CBD5E1; margin-top:2px;">Created by Rishika Dangayach</div>
        <h1 class="lens-title" style="margin-bottom:2px; font-size:1.6rem;">📈 Price & Technical Analysis</h1>
        <div class="lens-subtitle" style="font-size:0.88rem;">Deterministic Quantitative Analytics: Daily OHLCV, Moving Averages, Momentum & Risk Profile</div>
    </div>
    """, unsafe_allow_html=True)

    clean_df = None
    active_ticker = "DEMO"
    active_currency = "USD"
    bench_df = None
    bench_ticker = None
    selected_basis = PriceAdjustmentBasis.SPLIT_AND_DIVIDEND_ADJUSTED
    is_sim = False

    ohlcv_dir = ROOT_DIR / "datasets" / "fundamentals_lens" / "ohlcv"
    ohlcv_manifest = load_ohlcv_manifest()
    manifest_assets = ohlcv_manifest.get("assets", {})

    # Top Toolbar: Compact 3-Column Control Header
    tool_col1, tool_col2, tool_col3 = st.columns([3, 4, 3])
    with tool_col1:
        source_choice = st.selectbox(
            "Select Price Data Source:",
            [
                "📁 Pre-Packaged Demo Dataset (Generic Synthetic)",
                "📤 Upload Custom Daily OHLCV CSV (In-Memory Only)"
            ]
        )

    if "Pre-Packaged Demo Dataset" in source_choice:
        is_sim = True
        with tool_col2:
            demo_opts = {
                k: v.get("display_name", k)
                for k, v in manifest_assets.items()
                if not k.endswith("BENCHMARK")
            } if manifest_assets else {
                "SIMULATED_TECH_EQUITY": "[SIMULATED] Tech Growth Equity (Illustrative Demo)",
            }
            selected_demo = st.selectbox(
                "Select Simulated Demo Asset:",
                options=list(demo_opts.keys()),
                format_func=lambda k: demo_opts[k]
            )
            active_ticker = selected_demo
            active_currency = manifest_assets.get(selected_demo, {}).get("currency", "USD")
            demo_file = ohlcv_dir / f"{selected_demo}.csv"
            demo_basis = manifest_assets.get(selected_demo, {}).get("price_adjustment_basis", "SYNTHETIC_SIMULATION_NOT_APPLICABLE")
            if demo_file.exists():
                raw_df = pd.read_csv(demo_file)
                valid, err, clean_df, rep = validate_ohlcv_dataframe_with_report(
                    raw_df,
                    ticker=active_ticker,
                    price_adjustment_basis=demo_basis
                )
                if not valid:
                    st.error(f"Error loading demo dataset: {err}")
            else:
                st.warning(f"Demo file {demo_file.name} not found.")

        with tool_col3:
            bm_choice = st.selectbox(
                "Comparative Benchmark:",
                ["None", "SIMULATED_MARKET_BENCHMARK — Market Benchmark (Pre-Packaged)"]
            )
            if "SIMULATED_MARKET_BENCHMARK" in bm_choice:
                bench_ticker = "SIMULATED_MARKET_BENCHMARK"
                bench_basis = manifest_assets.get("SIMULATED_MARKET_BENCHMARK", {}).get("price_adjustment_basis", "SYNTHETIC_SIMULATION_NOT_APPLICABLE")
                bench_file = ohlcv_dir / "SIMULATED_MARKET_BENCHMARK.csv"
                if bench_file.exists():
                    valid_bm, _, bench_df, _ = validate_ohlcv_dataframe_with_report(
                        pd.read_csv(bench_file),
                        ticker=bench_ticker,
                        price_adjustment_basis=bench_basis
                    )

        # Compact synthetic demo badge
        st.markdown(
            """<div style="display:flex; align-items:center; justify-content:space-between; background:#FFFBEB; border:1px solid #FDE68A; padding:6px 12px; border-radius:6px; margin:4px 0 10px 0; font-size:0.83rem; color:#92400E;">
                <div><strong>⚠️ SYNTHETIC DEMONSTRATION DATASET:</strong> Algorithm verification walk; not real equity trading history or investment advice.</div>
                <span style="background:#FEF3C7; border:1px solid #FCD34D; padding:2px 8px; border-radius:4px; font-weight:600; font-size:0.75rem;">DEMO MODE</span>
            </div>""",
            unsafe_allow_html=True
        )

    else:
        # File uploader
        up_col1, up_col2 = st.columns([3, 2])
        with up_col1:
            st.markdown("Upload a daily OHLCV CSV file (headers: `Date`, `Open`, `High`, `Low`, `Close`, `Volume`):")
            uploaded_file = st.file_uploader("Upload OHLCV CSV:", type=["csv"])
            
            c_input1, c_input2 = st.columns(2)
            with c_input1:
                custom_ticker_input = st.text_input("Asset Symbol / Label:", value="CUSTOM_ASSET")
                active_ticker = custom_ticker_input.strip().upper() or "CUSTOM"
                is_sim = active_ticker.startswith("SIMULATED")
            with c_input2:
                curr_select = st.selectbox("Currency:", ["USD ($)", "INR (₹)", "EUR (€)", "GBP (£)", "Custom Code..."])
                if "Custom Code" in curr_select:
                    custom_curr_code = st.text_input("3-Letter Code:", value="USD", max_chars=5)
                    active_currency = custom_curr_code.strip().upper() or "USD"
                elif "INR" in curr_select:
                    active_currency = "INR"
                elif "EUR" in curr_select:
                    active_currency = "EUR"
                elif "GBP" in curr_select:
                    active_currency = "GBP"
                else:
                    active_currency = "USD"

            basis_choice = st.selectbox(
                "Price Adjustment Basis:",
                options=[
                    "Split & Dividend Adjusted (Total Return Basis - Recommended)",
                    "Split Adjusted Only (Ex-Dividend Prices)",
                    "Raw Unadjusted (May contain split/dividend artificial jumps)",
                    "Unknown / Unspecified"
                ]
            )
            if "Split & Dividend Adjusted" in basis_choice:
                selected_basis = PriceAdjustmentBasis.SPLIT_AND_DIVIDEND_ADJUSTED
            elif "Split Adjusted Only" in basis_choice:
                selected_basis = PriceAdjustmentBasis.SPLIT_ADJUSTED_ONLY
            elif "Raw Unadjusted" in basis_choice:
                selected_basis = PriceAdjustmentBasis.RAW_UNADJUSTED
            else:
                selected_basis = PriceAdjustmentBasis.UNKNOWN

            if selected_basis in (PriceAdjustmentBasis.RAW_UNADJUSTED, PriceAdjustmentBasis.UNKNOWN):
                st.warning(
                    "⚠️ **Price Adjustment Caveat:** Technical indicators and returns calculated on unadjusted "
                    "or unknown price series may exhibit artificial price gaps and distorted momentum from stock splits or dividend drops. "
                    "True total return analysis requires split-and-dividend-adjusted prices."
                )
            st.caption("ℹ️ *Note: Adjustment basis is user-declared for uploaded files rather than externally verified by third-party exchange feeds. Uploaded data is processed purely in-memory and is not persisted to disk.*")

            validation_report = None
            if uploaded_file is not None:
                try:
                    raw_df = pd.read_csv(uploaded_file)
                    valid, err, clean_df, validation_report = validate_ohlcv_dataframe_with_report(
                        raw_df,
                        ticker=active_ticker,
                        price_adjustment_basis=selected_basis
                    )
                    if not valid:
                        st.error(f"❌ **Validation Failed:** {err}")
                        clean_df = None
                        with st.expander("🔍 Detailed Invariant Violation Diagnostics", expanded=True):
                            st.write(f"**Total Records Inspected:** {validation_report.total_rows}")
                            st.write(f"**Valid Bars Detected:** {validation_report.valid_rows}")
                            st.write(f"**Violations Encountered:** {len(validation_report.violations)}")
                            for v in validation_report.violations:
                                st.markdown(f"- ❌ `{v}`")
                            st.caption("Required invariants: Date uniqueness/monotonicity, High >= max(Open, Close, Low), Low <= min(Open, Close, High), Volume >= 0.")
                    else:
                        st.success(f"✅ Successfully validated {len(clean_df)} trading observations for `{active_ticker}`.")
                        with st.expander("ℹ️ View Invariants Validation Summary"):
                            st.write(f"**Total Valid Trading Bars:** {validation_report.valid_rows}")
                            st.write(f"**Duplicate Dates Found & Handled:** {validation_report.duplicate_dates_count}")
                            st.write(f"**Date Range:** {validation_report.start_date} to {validation_report.end_date}")
                            st.write(f"**Adjustment Basis Recorded:** `{validation_report.price_adjustment_basis.value}`")
                            st.write("**Invariants Passed:**")
                            for inv in validation_report.invariants_checked:
                                st.markdown(f"- ✅ `{inv}`")
                except Exception as e:
                    st.error(f"❌ Failed to parse CSV: {str(e)}")
                    clean_df = None

        with up_col2:
            st.markdown("**Need a CSV template?**")
            st.caption("Download the standardized template to prepare your OHLCV data:")
            st.download_button(
                label="📥 Download OHLCV CSV Template",
                data=get_ohlcv_csv_template(),
                file_name="ohlcv_template.csv",
                mime="text/csv"
            )

    # Render technical workbench if valid data is present
    if clean_df is not None and not clean_df.empty:
        # Calculate indicators
        clean_df = compute_technical_indicators(clean_df)
        summary = compute_technical_summary(
            clean_df,
            ticker=active_ticker,
            benchmark_df=bench_df,
            benchmark_ticker=bench_ticker,
            price_adjustment_basis=selected_basis,
            is_simulated_demo=is_sim,
            currency=active_currency
        )

        if is_sim:
            badge_html = " <span class='badge-limited' style='background:#FEF3C7; color:#92400E; padding:3px 10px; border-radius:4px; font-size:0.8rem; font-weight:600; border:1px solid #FCD34D;'>⚠️ SIMULATED DEMO DATA</span>"
        else:
            badge_html = " <span style='background:#DCFCE7; color:#166534; padding:3px 10px; border-radius:4px; font-size:0.8rem; font-weight:600; border:1px solid #86EFAC;'>🛡️ USER / RECORDED MARKET DATA</span>"
        st.markdown(f"#### **Quantitative Snapshot — `{active_ticker}`** ({summary.total_bars} bars, `{clean_df['Date_Str'].iloc[0]}` to `{summary.last_date}` | Currency: `{summary.currency}` | Basis: `{summary.price_adjustment_basis}`){badge_html}", unsafe_allow_html=True)

        # 4 Core KPI Cards with integrated indicator telemetry
        tkpi1, tkpi2, tkpi3, tkpi4 = st.columns(4)
        with tkpi1:
            st.markdown(f"""
            <div class="kpi-card" style="padding:10px 14px;">
                <div class="kpi-label">Latest Close Price</div>
                <div class="kpi-val" style="font-size:1.35rem;">{summary.last_close:,.2f} <span style="font-size:0.85rem; font-weight:600; color:#64748B;">{summary.currency}</span></div>
                <div class="kpi-delta neu">As of {summary.last_date}</div>
            </div>
            """, unsafe_allow_html=True)
        with tkpi2:
            if summary.change_1y is not None:
                ret_1y_str = f"{summary.change_1y:+.2f}%"
                ret_label = "1-Year Return"
            elif summary.change_6m is not None:
                ret_1y_str = f"{summary.change_6m:+.2f}% (6M)"
                ret_label = "6-Month Return"
            elif summary.change_3m is not None:
                ret_1y_str = f"{summary.change_3m:+.2f}% (3M)"
                ret_label = "3-Month Return"
            else:
                ret_1y_str = "N/A (<252 bars)"
                ret_label = f"Period Return ({summary.total_bars} bars)"
            rsi_brief = summary.rsi_status.split(" ")[0] if summary.rsi_status else "N/A"
            st.markdown(f"""
            <div class="kpi-card" style="padding:10px 14px;">
                <div class="kpi-label">{ret_label}</div>
                <div class="kpi-val" style="font-size:1.35rem;">{ret_1y_str}</div>
                <div class="kpi-delta neu">RSI(14): <strong>{summary.current_rsi:.1f}</strong> ({rsi_brief})</div>
            </div>
            """, unsafe_allow_html=True)
        with tkpi3:
            range_label = "52-Week Range" if summary.is_full_52w else f"Trading Range ({summary.total_bars} bars)"
            st.markdown(f"""
            <div class="kpi-card" style="padding:10px 14px;">
                <div class="kpi-label">{range_label}</div>
                <div class="kpi-val" style="font-size:1.2rem;">{summary.low_52w:,.1f} — {summary.high_52w:,.1f}</div>
                <div class="kpi-delta neu">SMA 20: {summary.sma_20_status} | 50: {summary.sma_50_status}</div>
            </div>
            """, unsafe_allow_html=True)
        with tkpi4:
            st.markdown(f"""
            <div class="kpi-card" style="padding:10px 14px;">
                <div class="kpi-label">Risk Profile</div>
                <div class="kpi-val" style="font-size:1.25rem;">{f"σ = {summary.annualized_volatility:.1f}%" if summary.annualized_volatility else "N/A"}</div>
                <div class="kpi-delta neg">Max DD: {f"{summary.max_drawdown:.1f}%" if summary.max_drawdown else "N/A"} | 200: {summary.sma_200_status}</div>
            </div>
            """, unsafe_allow_html=True)

        # Technical Tabs
        tech_tab1, tech_tab2, tech_tab3, tech_tab4 = st.tabs([
            "📊 Price Action & Trend",
            "⚡ Momentum & Oscillators",
            "🎯 Benchmark & Relative Return",
            "📑 Technical Data & Exports"
        ])

        with tech_tab1:
            c_hdr, c_chk1, c_chk2 = st.columns([2, 1, 1])
            with c_hdr:
                st.markdown("#### **Price Action, Moving Averages & Volume**")
            with c_chk1:
                show_sma_opt = st.checkbox("SMAs (20 / 50 / 200)", value=True)
            with c_chk2:
                show_bb_opt = st.checkbox("Bollinger Bands (20, 2.0σ)", value=True)

            fig_candle = create_price_candlestick_chart(
                clean_df, 
                ticker=active_ticker,
                show_sma=show_sma_opt,
                show_bb=show_bb_opt,
                is_simulated_demo=is_sim
            )
            if fig_candle:
                st.plotly_chart(fig_candle, use_container_width=True)

        with tech_tab2:
            st.markdown("#### **Relative Strength Index (RSI) & MACD Momentum**")
            fig_rsi = create_rsi_chart(clean_df, ticker=active_ticker, is_simulated_demo=is_sim)
            if fig_rsi:
                st.plotly_chart(fig_rsi, use_container_width=True)

            fig_macd = create_macd_chart(clean_df, ticker=active_ticker, is_simulated_demo=is_sim)
            if fig_macd:
                st.plotly_chart(fig_macd, use_container_width=True)

        with tech_tab3:
            st.markdown("#### **Benchmark Comparison (Normalized Base = 100)**")
            if bench_df is not None and not bench_df.empty:
                fig_comp = create_benchmark_comparison_chart(
                    clean_df,
                    bench_df,
                    asset_ticker=active_ticker,
                    benchmark_ticker=bench_ticker or "BENCHMARK",
                    is_simulated_demo=is_sim
                )
                if fig_comp:
                    st.plotly_chart(fig_comp, use_container_width=True)
                if summary.relative_performance_1y is not None:
                    perf_label = "1-Year Relative Performance" if (summary.common_benchmark_bars or 0) >= 252 else f"Relative Performance ({summary.common_benchmark_bars} bars)"
                    ret_a_str = f"{summary.change_1y:+.1f}%" if summary.change_1y is not None else "N/A"
                    ret_b_str = f"{summary.benchmark_change_1y:+.1f}%" if summary.benchmark_change_1y is not None else "N/A"
                    st.info(
                        f"🎯 **{perf_label}:** `{active_ticker}` cumulative return diverged by "
                        f"**{summary.relative_performance_1y:+.2f}%** points relative to `{bench_ticker}` "
                        f"({ret_a_str} vs {ret_b_str}) over {summary.common_benchmark_bars} common trading days."
                    )
                elif summary.relative_performance_period is not None:
                    st.info(
                        f"🎯 **Relative Performance ({summary.common_benchmark_bars} bars):** `{active_ticker}` cumulative return diverged by "
                        f"**{summary.relative_performance_period:+.2f}%** points relative to `{bench_ticker}` "
                        f"over {summary.common_benchmark_bars} overlapping trading days."
                    )
            else:
                st.info("ℹ️ Select a benchmark above to compare normalized relative returns.")

        with tech_tab4:
            st.markdown("#### **Calculated Technical Indicators Table**")
            cols_to_show = [
                "Date_Str", "Open", "High", "Low", "Close", "Volume",
                "SMA_20", "SMA_50", "SMA_200", "RSI_14", "MACD", "MACD_Hist", "Daily_Return"
            ]
            cols_present = [c for c in cols_to_show if c in clean_df.columns]
            st.dataframe(clean_df[cols_present].tail(100), hide_index=True, use_container_width=True)

            st.markdown("#### **Exports**")
            t_csv_str = ExportGenerator.generate_technical_csv(clean_df, active_ticker, summary=summary)
            t_brief_md = ExportGenerator.generate_technical_brief(summary, clean_df)

            t_exp1, t_exp2 = st.columns(2)
            with t_exp1:
                st.download_button(
                    label=f"📥 Download {active_ticker} Technical Data (CSV)",
                    data=t_csv_str,
                    file_name=f"{active_ticker}_technical_indicators.csv",
                    mime="text/csv",
                    use_container_width=True
                )
            with t_exp2:
                st.download_button(
                    label=f"📄 Download {active_ticker} Technical Brief (Markdown)",
                    data=t_brief_md,
                    file_name=f"{active_ticker}_technical_brief.md",
                    mime="text/markdown",
                    use_container_width=True
                )


# ==============================================================================
# PAGE 5: DATA INTEGRITY & METHODOLOGY
# ==============================================================================
elif selected_page == "Data Integrity & Methodology":
    st.markdown("""
    <div class="lens-header">
        <div style="float:right; font-weight:600; color:#1E293B; font-size:0.95rem; background:#F1F5F9; padding:4px 12px; border-radius:6px; border:1px solid #CBD5E1; margin-top:2px;">Created by Rishika Dangayach</div>
        <h1 class="lens-title">🛡️ Data Integrity, Validation & Methodology</h1>
        <div class="lens-subtitle">Deterministic 7-Gate Validation Suite, Zero-Coercion Policy & Primary Provenance</div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
    ### **Our Data Integrity Philosophy**
    1. **Primary Sources Only:** Every financial observation is sourced directly from audited annual statements filed with the US SEC (Form 10-K) or Indian stock exchanges (BSE/NSE Annual Reports).
    2. **Zero Synthetic Coercion:** Missing data points are never converted into synthetic zeroes (`0.0`). Missing data is preserved as `None` with transparent explanations.
    3. **Consolidated Financial Basis:** Primary reported figures reflect the consolidated operations of the parent company and its subsidiaries.
    4. **Zero Operational Cost:** The product runs without paid APIs, runtime scraping, external cloud databases, or mandatory configuration.

    ### **Verification Status Definitions & Retrieval Transparency**
    - **Offline Audited (`OFFLINE_AUDITED` / `RETRIEVED_OFFLINE_EXTRACT`):** Financial metrics verified against tracked, version-controlled audited statement extracts and official filing documents stored in the repository. Offline execution guarantees 100% deterministic reproducibility without active network calls or token dependencies.
    - **Fresh Online Retrieval (`RETRIEVED_ONLINE_EDGAR` / `RETRIEVED_ONLINE_BSE`):** Strictly emitted ONLY when a live HTTP retrieval to official SEC EDGAR archives or BSE/NSE exchanges succeeded with HTTP 200 during the current execution run. An offline reproducibility run is NEVER counted as fresh online retrieval.
    - **Reconciliation Tiers (`INDEPENDENTLY_RECONCILED` vs `SOURCE_LINKED_ONLY`):** A metric is marked `INDEPENDENTLY_RECONCILED` only when document identity, filing form (Form 10-K), official domain, valid 300–400 day annual duration, specific audited statement locator, and exact numerical alignment (or approved discrepancy entry) are ALL simultaneously proven. If retrieval failed or locators are pending, it is categorized as `SOURCE_LINKED_ONLY`.
    """)

    st.markdown("---")

    # Coverage Report Table
    st.markdown("### **Company-Level Target Reporting Horizon & Period Coverage**")
    st.caption(f"Dataset Snapshot Cutoff: `{snapshot_date}` • Universe: {total_comps} Companies across {total_periods} Completed Annual Periods • {reconciled_metrics} Primary Disclosures Independently Reconciled ({reconciled_metrics / total_datapoints * 100:.1f}%), {source_linked_metrics} Source-Linked Only, {fcf_derived_count} Derived Verified Invariants.")
    
    cov_rows = []
    for c in companies:
        entry = coverage_map.get(c.ticker, {})
        status_code = entry.get("target_period_status_code", 1)
        status_desc = entry.get("target_period_status_desc", "VERIFIED INCLUDED" if status_code == 0 else "PERIOD ONGOING / PENDING 10-K")
        overall_status = entry.get("overall_coverage_status", "5_PERIODS_VERIFIED")
        
        cov_rows.append({
            "Ticker": c.ticker,
            "Company Name": c.name,
            "Country": c.country,
            "Currency": c.reporting_currency,
            "Verified Periods": ", ".join(entry.get("verified_periods", [])),
            "Latest Verified": entry.get("latest_verified_period", "N/A"),
            "Target Horizon": entry.get("target_horizon_period", "N/A"),
            "Target Status": status_desc,
            "Overall Status": overall_status
        })
    df_cov = pd.DataFrame(cov_rows)
    st.dataframe(df_cov, hide_index=True, use_container_width=True)

    st.markdown("---")

    # Source Assurance & Retrieval Telemetry Breakdown (Phase 18 Enhanced)
    inv_file = ROOT_DIR / "datasets" / "fundamentals_lens" / "source_review_inventory.json"
    if inv_file.exists():
        with open(inv_file, "r", encoding="utf-8") as f:
            inventory_data = json.load(f)

        live_sampled_n = sum(1 for e in inventory_data if e.get("is_live_sampled"))
        offline_audited_n = sum(1 for e in inventory_data if not e.get("is_live_sampled"))

        st.markdown("### **Source-Level Assurance & Retrieval Telemetry Breakdown**")
        st.caption("Truthful data-derived verification depth: distinguishes offline-audited extracts from fresh network retrievals without arbitrary sampling claims.")
        s_col1, s_col2, s_col3, s_col4 = st.columns(4)
        with s_col1:
            st.metric("Total Sources Tracked", len(inventory_data))
        with s_col2:
            st.metric("Tracked Offline Extracts", offline_audited_n, help="Validated against repository-tracked audited statements with deterministic offline reproducibility.")
        with s_col3:
            st.metric("Fresh Live Retrievals", live_sampled_n, help="Strictly counts live remote network re-fetches executed during current execution.")
        with s_col4:
            st.metric("Approved Discrepancies", len(discrepancy_ledger), help="Documented accounting taxonomy and restatement entries in ledger.")

        with st.expander("🔍 Expand Source Verification Depth & Limitations Inventory (75 Sources)", expanded=False):
            inv_rows = []
            for e in inventory_data:
                inv_rows.append({
                    "Ticker": e.get("ticker"),
                    "Period": e.get("fiscal_year_label"),
                    "Country": e.get("country"),
                    "Source Title": e.get("source_title"),
                    "Extraction Pathway": e.get("extraction_pathway"),
                    "Format Check": e.get("url_and_accession_format_check"),
                    "Retrieval Status": e.get("retrieval_check_status"),
                    "Verification Depth": e.get("verification_depth"),
                    "Limitations": e.get("remaining_source_limitations")
                })
            st.dataframe(pd.DataFrame(inv_rows), hide_index=True, use_container_width=True)

        st.markdown("---")

    # 7-Gate Validation Engine
    st.markdown("### **Deterministic Multi-Gate Validation Results**")
    
    if st.button("🔄 Re-run Complete Validation Audit", use_container_width=True):
        st.cache_data.clear()
        
    all_validation_results = []
    all_raw_results = []
    total_checks = 0
    passed_checks = 0
    warning_checks = 0
    failed_checks = 0
    unverified_checks = 0
    
    for c in companies:
        c_facts = facts_by_ticker.get(c.ticker, [])
        res = FundamentalsValidator.validate_company_dataset(c, c_facts, sources, coverage=coverage, evidence_register=evidence_register)
        all_raw_results.extend(res)
        for r in res:
            total_checks += 1
            if r.status == ValidationStatus.PASS:
                passed_checks += 1
            elif r.status == ValidationStatus.WARNING:
                warning_checks += 1
            elif r.status == ValidationStatus.FAIL:
                failed_checks += 1
            elif r.status == ValidationStatus.UNVERIFIED:
                unverified_checks += 1

            all_validation_results.append({
                "Ticker": c.ticker,
                "Company": c.name,
                "Dimension": r.dimension,
                "Gate ID": r.rule_id,
                "Gate Name": r.rule_name,
                "Status": r.status.value,
                "Details": r.message
            })

    v_col1, v_col2, v_col3, v_col4 = st.columns(4)
    with v_col1:
        st.metric("Total Validation Checks", total_checks)
    with v_col2:
        st.metric("Checks Passed", passed_checks)
    with v_col3:
        st.metric("Review Warnings", warning_checks)
    with v_col4:
        st.metric("Failed / Unverified", failed_checks + unverified_checks)

    # Dimension Breakdown Passport
    st.markdown("#### **Data Integrity Passport — Multi-Dimensional Quality Gates**")
    st.caption("Distinguishes structural schema verification from factual source reconciliation, non-coercion, and comparability guards.")
    dim_summary = FundamentalsValidator.get_dimension_summary(all_raw_results)
    dim_rows = []
    for dim_name, counts in dim_summary.items():
        total_d = sum(counts.values())
        passed_d = counts.get("PASS", 0)
        warn_d = counts.get("WARNING", 0)
        unver_d = counts.get("UNVERIFIED", 0)
        failed_d = counts.get("FAIL", 0)
        rate = (passed_d / total_d * 100) if total_d > 0 else 0
        dim_rows.append({
            "Validation Dimension": dim_name,
            "Total Rules": total_d,
            "Passed": passed_d,
            "Warnings": warn_d,
            "Unverified": unver_d,
            "Failed": failed_d,
            "Pass Rate": f"{rate:.1f}%"
        })
    df_dims = pd.DataFrame(dim_rows)
    st.dataframe(df_dims, hide_index=True, use_container_width=True)

    df_val = pd.DataFrame(all_validation_results)
    
    # Filter by Ticker or Dimension
    st.markdown("#### **Detailed Rule Evaluation Log**")
    f_col1, f_col2 = st.columns(2)
    with f_col1:
        filter_ticker = st.selectbox("Filter by Company:", ["ALL"] + [c.ticker for c in companies])
    with f_col2:
        filter_dim = st.selectbox("Filter by Dimension:", ["ALL"] + list(dim_summary.keys()))

    if filter_ticker != "ALL":
        df_val = df_val[df_val["Ticker"] == filter_ticker]
    if filter_dim != "ALL":
        df_val = df_val[df_val["Dimension"] == filter_dim]
        
    st.dataframe(df_val, hide_index=True, use_container_width=True)

    st.markdown("---")

    # Regulatory Discrepancy Ledger
    st.markdown(f"### **Regulatory Disclosure Discrepancy & Lineage Ledger ({len(discrepancy_ledger)} Logged)**")
    st.caption("Immutable accounting audit trail of intentional taxonomy differences, proxy disclosures, and financial statement restatements.")
    
    with st.expander("⚖️ Expand Discrepancy & Lineage Ledger Table", expanded=True):
        disc_rows = []
        for d in discrepancy_ledger:
            disc_rows.append({
                "ID": d.get("discrepancy_id"),
                "Ticker": d.get("ticker"),
                "Period": d.get("fiscal_year_label") or d.get("fiscal_year"),
                "Metric": d.get("metric"),
                "Type": d.get("discrepancy_type") or "AUDITED_STATEMENT_RECONCILIATION",
                "Canonical": d.get("initial_dataset_value") if "initial_dataset_value" in d else d.get("canonical_value"),
                "Reported": d.get("primary_reported_value") if "primary_reported_value" in d else d.get("reported_value"),
                "Status": d.get("status") or "RESOLVED",
                "Resolution Note": d.get("resolution") or d.get("resolution_or_reconciliation_note") or d.get("investigation_finding") or d.get("description", "")
            })
        st.dataframe(pd.DataFrame(disc_rows), hide_index=True, use_container_width=True)

    st.markdown("---")

    # Downloadable Evidence Register & Source Register
    st.markdown("### **Primary Evidence Register & Master Source Browser**")
    st.caption("Complete line-item provenance and filing audit trail across all 75 annual observations.")

    d_col1, d_col2 = st.columns(2)
    with d_col1:
        ev_path = ROOT_DIR / "datasets" / "fundamentals_lens" / "evidence_register.csv"
        if ev_path.exists():
            with open(ev_path, "r", encoding="utf-8") as f:
                ev_csv = f.read()
            st.download_button(
                label="📥 Download Complete Evidence Register (CSV)",
                data=ev_csv,
                file_name="fundamentals_lens_evidence_register.csv",
                mime="text/csv",
                use_container_width=True
            )
    with d_col2:
        src_path = ROOT_DIR / "datasets" / "fundamentals_lens" / "source_register.json"
        if src_path.exists():
            with open(src_path, "r", encoding="utf-8") as f:
                src_json = f.read()
            st.download_button(
                label="📥 Download Master Source Register (JSON)",
                data=src_json,
                file_name="fundamentals_lens_source_register.json",
                mime="application/json",
                use_container_width=True
            )

    sources_df = pd.DataFrame(sources)[[
        "ticker", "fiscal_year_label", "source_title", "filing_date", "accession_id", "statement_location", "source_url"
    ]]
    sources_df.columns = [
        "Ticker", "Fiscal Year", "Filing Document", "Filing Date", "Filing Reference ID", "Statement Location", "Source URL"
    ]
    st.dataframe(sources_df, hide_index=True, use_container_width=True)

# Footer
st.markdown("---")
st.markdown("""
<div style="text-align:center; color:#64748B; font-size:0.8rem; padding: 12px 0;">
    Fundamentals Lens • Evidence-First SEC & Indian Corporate Disclosure Intelligence • Created by Rishika Dangayach • Built with Streamlit & Plotly • Verified Public Regulatory Filings
</div>
""", unsafe_allow_html=True)
