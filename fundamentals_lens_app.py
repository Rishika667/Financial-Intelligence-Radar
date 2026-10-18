"""
Fundamentals Lens: Evidence-First Financial Intelligence & Research Application
Entry point for Streamlit Community Cloud and local research workflows.
"""
import sys
import io
import streamlit as st
import pandas as pd
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
    get_company_by_ticker,
    get_facts_for_company
)
from fundamentals_lens.metrics import compute_derived_metrics_for_company
from fundamentals_lens.validator import FundamentalsValidator
from fundamentals_lens.insights import NarrativeEngine
from fundamentals_lens.peers import PeerComparisonEngine, PEER_GROUP_METADATA
from fundamentals_lens.exports import ExportGenerator
from fundamentals_lens.models import ValidationStatus

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
        font-size: 1.6rem;
        font-weight: 700;
        color: #0F172A;
        margin: 4px 0;
    }
    .kpi-delta {
        font-size: 0.82rem;
        font-weight: 600;
    }
    .kpi-delta.pos { color: #0D9488; }
    .kpi-delta.neg { color: #E11D48; }
    .kpi-delta.neu { color: #64748B; }

    /* Narrative Insight Box */
    .insight-box {
        background-color: #FFFFFF;
        border-left: 4px solid #0EA5E9;
        border-top: 1px solid #E2E8F0;
        border-right: 1px solid #E2E8F0;
        border-bottom: 1px solid #E2E8F0;
        border-radius: 6px;
        padding: 16px 20px;
        margin-bottom: 14px;
        box-shadow: 0 1px 2px rgba(0,0,0,0.02);
    }
    .insight-cat {
        font-size: 0.75rem;
        font-weight: 700;
        color: #0284C7;
        text-transform: uppercase;
        letter-spacing: 0.05em;
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
    
    facts_by_ticker = {}
    for f in facts:
        facts_by_ticker.setdefault(f.ticker, []).append(f)
        
    for ticker in facts_by_ticker:
        facts_by_ticker[ticker].sort(key=lambda x: x.fiscal_year)
        
    return companies, facts_by_ticker, sources, coverage, evidence_register


companies, facts_by_ticker, sources, coverage, evidence_register = get_app_data()
companies_map = {c.ticker: c for c in companies}
coverage_map = {entry["ticker"]: entry for entry in coverage}

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
st.sidebar.caption("Evidence-First Financial Research")

pages = [
    "Overview",
    "Company Analysis",
    "Peer Comparison",
    "Data Integrity & Methodology"
]

query_page = st.query_params.get("page", "")
default_page_idx = 0
if query_page:
    qp = str(query_page).lower().strip()
    if "peer" in qp:
        default_page_idx = 2
    elif "company" in qp or "analysis" in qp:
        default_page_idx = 1
    elif "data" in qp or "integ" in qp or "method" in qp:
        default_page_idx = 3
    elif "over" in qp:
        default_page_idx = 0

selected_page = st.sidebar.radio("Navigation", pages, index=default_page_idx)

st.sidebar.markdown("---")
st.sidebar.markdown("**Dataset Snapshot:** `2026-10-18`")
st.sidebar.markdown("**Universe:** 15 Companies across 5 Peer Groups")
st.sidebar.markdown("**Architecture:** Zero-Cost Deterministic Engine (Primary Disclosures)")
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
        <h1 class="lens-title">🔍 Fundamentals Lens</h1>
        <div class="lens-subtitle">Transparent Five-Year Financial Disclosure Intelligence & Analytical Research</div>
    </div>
    """, unsafe_allow_html=True)
    
    st.info("ℹ️ **Historical Research Notice:** This application provides historical financial analysis based on audited annual disclosures. It is not a live trading feed, stock price prediction tool, or investment advisory service.")

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
            <div class="kpi-val">{reconciled_metrics} <span style="font-size:0.9rem;font-weight:400;">/ {total_datapoints}</span></div>
            <div class="kpi-delta pos">{reconciled_metrics / total_datapoints * 100:.1f}% Reconciled ({unverified_metrics} Sourced / Discrepancy Log)</div>
        </div>
        """, unsafe_allow_html=True)
    with col4:
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-label">Target Reporting Horizon</div>
            <div class="kpi-val">{target_verified_count} <span style="font-size:0.9rem;font-weight:400;">Included</span></div>
            <div class="kpi-delta neu">{target_pending_count} Horizon Pending 10-K (AAPL, GOOGL, TGT)</div>
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
    prior_fact = c_facts[-2] if len(c_facts) >= 2 else None
    
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
        fcf_str = f"{latest_der.free_cash_flow:,.1f} {unit}" if latest_der.free_cash_flow is not None else "N/A"
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
        for i in insights[:2]: # Show top 2 insights on landing page
            st.markdown(f"""
            <div class="insight-box">
                <div class="insight-cat">{i.category.replace('_', ' ')}</div>
                <div class="insight-headline">{i.headline}</div>
                <div class="insight-section"><strong>What changed:</strong> {i.what_changed}</div>
                <div class="insight-section"><strong>Evidence:</strong> <code>{i.evidence}</code></div>
                <div class="insight-section"><strong>Why it matters:</strong> {i.why_it_matters}</div>
            </div>
            """, unsafe_allow_html=True)
            
        st.caption("👉 Navigate to **Company Analysis** for complete multi-year disclosures, all analytical insights, and official filing citations.")


# ==============================================================================
# PAGE 2: COMPANY ANALYSIS
# ==============================================================================
elif selected_page == "Company Analysis":
    st.markdown("""
    <div class="lens-header">
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

    # 6 Core KPI Cards
    r1_col1, r1_col2, r1_col3 = st.columns(3)
    with r1_col1:
        growth_str = f"{latest_der.revenue_growth_yoy:+.1f}% YoY" if latest_der.revenue_growth_yoy is not None else "N/A"
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-label">Revenue ({latest_fact.fiscal_year_label})</div>
            <div class="kpi-val">{latest_fact.revenue:,.1f} <span style="font-size:0.9rem;font-weight:400;">{unit}</span></div>
            <div class="kpi-delta {'pos' if (latest_der.revenue_growth_yoy or 0) >= 0 else 'neg'}">YoY Growth: {growth_str}</div>
        </div>
        """, unsafe_allow_html=True)
    with r1_col2:
        op_m_str = f"{latest_der.operating_margin:.2f}%" if latest_der.operating_margin is not None else "N/A"
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-label">Operating Income / EBIT</div>
            <div class="kpi-val">{latest_fact.operating_income:,.1f} <span style="font-size:0.9rem;font-weight:400;">{unit}</span></div>
            <div class="kpi-delta neu">Operating Margin: {op_m_str}</div>
        </div>
        """, unsafe_allow_html=True)
    with r1_col3:
        net_m_str = f"{latest_der.net_margin:.2f}%" if latest_der.net_margin is not None else "N/A"
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-label">Net Income (Consolidated)</div>
            <div class="kpi-val">{latest_fact.net_income:,.1f} <span style="font-size:0.9rem;font-weight:400;">{unit}</span></div>
            <div class="kpi-delta neu">Net Margin: {net_m_str}</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("")
    r2_col1, r2_col2, r2_col3 = st.columns(3)
    with r2_col1:
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-label">Operating Cash Flow</div>
            <div class="kpi-val">{latest_fact.operating_cash_flow:,.1f} <span style="font-size:0.9rem;font-weight:400;">{unit}</span></div>
            <div class="kpi-delta pos">Cash from operations</div>
        </div>
        """, unsafe_allow_html=True)
    with r2_col2:
        capex_ratio = round((latest_fact.capital_expenditure / latest_fact.revenue) * 100.0, 1) if latest_fact.revenue > 0 else 0
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-label">Capital Expenditure (Capex)</div>
            <div class="kpi-val">{latest_fact.capital_expenditure:,.1f} <span style="font-size:0.9rem;font-weight:400;">{unit}</span></div>
            <div class="kpi-delta neu">Capex Intensity: {capex_ratio:.1f}% of revenue</div>
        </div>
        """, unsafe_allow_html=True)
    with r2_col3:
        fcf = latest_der.free_cash_flow
        fcf_str = f"{fcf:,.1f} {unit}" if fcf is not None else "N/A"
        if latest_der.cash_conversion_ratio is not None:
            conv_str = f"Cash Conversion: {latest_der.cash_conversion_ratio:.2f}x"
        else:
            conv_str = f"Conversion: {latest_der.cash_conversion_qualified_reason}"
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-label">Free Cash Flow (OCF - Capex)</div>
            <div class="kpi-val">{fcf_str}</div>
            <div class="kpi-delta {'pos' if (fcf or 0) >= 0 else 'neg'}">{conv_str}</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")

    # Visual Charts
    tab_chart1, tab_chart2, tab_chart3 = st.tabs([
        "📈 Revenue & Operating Profit",
        "📊 Profitability Margins (%)",
        "💵 Cash Generation & FCF"
    ])
    with tab_chart1:
        st.plotly_chart(plot_revenue_and_operating_profit(c_facts, c_derived, unit), use_container_width=True)
    with tab_chart2:
        st.plotly_chart(plot_margins(c_derived), use_container_width=True)
    with tab_chart3:
        st.plotly_chart(plot_cash_flows(c_facts, c_derived, unit), use_container_width=True)

    st.markdown("---")

    # Historical Disclosures Table
    st.markdown(f"### **Audited Multi-Year Financial Disclosures (in {unit})**")
    
    table_rows = []
    derived_map = {d.fiscal_year: d for d in c_derived}
    for f in c_facts:
        d = derived_map.get(f.fiscal_year)
        comp_badge = getattr(f, "comparability_flag", "DIRECT")
        tier_label = getattr(f, "reconciliation_tier", "INDEPENDENTLY_RECONCILED")
        table_rows.append({
            "Fiscal Period": f.fiscal_year_label,
            "Period End": f.period_end,
            "Basis": f.statement_basis,
            f"Revenue ({unit})": f"{f.revenue:,.1f}",
            "YoY Growth": f"{d.revenue_growth_yoy:+.1f}%" if d and d.revenue_growth_yoy is not None else "—",
            f"Operating Income ({unit})": f"{f.operating_income:,.1f}",
            "Operating Margin": f"{d.operating_margin:.2f}%" if d and d.operating_margin is not None else "—",
            f"Net Income ({unit})": f"{f.net_income:,.1f}",
            "Net Margin": f"{d.net_margin:.2f}%" if d and d.net_margin is not None else "—",
            f"Operating Cash Flow ({unit})": f"{f.operating_cash_flow:,.1f}",
            f"Capex ({unit})": f"{f.capital_expenditure:,.1f}",
            f"Free Cash Flow ({unit})": f"{d.free_cash_flow:,.1f}" if d and d.free_cash_flow is not None else "—",
            "Cash Conversion (x)": f"{d.cash_conversion_ratio:.2f}x" if d and d.cash_conversion_ratio is not None else f"Suppressed ({d.cash_conversion_qualified_reason or 'Guarded'})",
            "Comparability": comp_badge,
            "Reconciliation": "Reconciled" if tier_label == "INDEPENDENTLY_RECONCILED" else "Source-Linked"
        })
    df_history = pd.DataFrame(table_rows)
    st.dataframe(df_history, hide_index=True, use_container_width=True)

    if latest_fact.accounting_notes:
        st.info(f"💡 **Accounting Comparability Note:** {latest_fact.accounting_notes}")

    st.markdown("---")

    # Analytical Section: What changed, why it matters, what to investigate
    st.markdown("### **What Changed, Why It Matters, and What to Investigate**")
    st.caption("Deterministic, rule-based analytical insights grounded exclusively in audited numerical observations.")
    
    insights = NarrativeEngine.generate_company_insights(c_facts, c_derived)
    for idx, insight in enumerate(insights, 1):
        with st.expander(f"**{idx}. {insight.headline}**", expanded=(idx <= 2)):
            st.markdown(f"""
            <div class="insight-box">
                <div class="insight-cat">{insight.category.replace('_', ' ')}</div>
                <div class="insight-section"><strong>What changed:</strong> {insight.what_changed}</div>
                <div class="insight-section"><strong>Numerical Evidence:</strong> <code>{insight.evidence}</code></div>
                <div class="insight-section"><strong>Why it matters:</strong> {insight.why_it_matters}</div>
                <div class="insight-section"><strong>What to investigate:</strong> {insight.what_to_investigate}</div>
                <div class="insight-section" style="color:#64748B;"><em>Analytical limitations:</em> {insight.limitations}</div>
            </div>
            """, unsafe_allow_html=True)

    st.markdown("---")

    # Primary Source Provenance Audit
    with st.expander("🔍 **Primary Source Provenance & Regulatory Filing Links**", expanded=False):
        st.markdown("Every observation in Fundamentals Lens is traceable to official, audited annual regulatory filings.")
        prov_rows = []
        for f in c_facts:
            prov_rows.append({
                "Fiscal Period": f.fiscal_year_label,
                "Filing Title": f.source_title,
                "Filing Date": f.filing_date,
                "Statement Location": f.statement_location,
                "Accession ID": f.accession_id,
                "Source Link": f.source_url
            })
        st.dataframe(pd.DataFrame(prov_rows), hide_index=True, use_container_width=True)

    # Export Center
    st.markdown("### **Research Exports**")
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

    # Multi-line comparative chart
    fig_peer = go.Figure()
    palette = ["#0284C7", "#0D9488", "#F59E0B", "#8B5CF6"]
    
    for idx, s in enumerate(matrix["series"]):
        x_vals = [pt["fiscal_year_label"] for pt in s["data"]]
        y_vals = [pt["value"] for pt in s["data"]]
        fig_peer.add_trace(go.Scatter(
            x=x_vals,
            y=y_vals,
            name=f"{s['ticker']} ({s['company_name']})",
            mode="lines+markers",
            line=dict(width=3, color=palette[idx % len(palette)]),
            marker=dict(size=8),
            hovertemplate=f"<b>{s['ticker']} (%{{x}})</b><br>{matrix['unit']}: %{{y}}<extra></extra>"
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
    
    # Build pivoted dataframe safely supporting differing fiscal years
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
# PAGE 4: DATA INTEGRITY & METHODOLOGY
# ==============================================================================
elif selected_page == "Data Integrity & Methodology":
    st.markdown("""
    <div class="lens-header">
        <h1 class="lens-title">🛡️ Data Integrity, Validation & Methodology</h1>
        <div class="lens-subtitle">Deterministic 7-Gate Validation Suite, Zero-Coercion Policy & Primary Provenance</div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
    ### **Our Data Integrity Philosophy**
    1. **Primary Sources Only:** Every financial observation is sourced directly from audited annual statements filed with the US SEC or Indian stock exchanges (BSE/NSE).
    2. **Zero Synthetic Coercion:** Missing data points are never converted into synthetic zeroes (`0.0`). Missing data is preserved as `None` with transparent explanations.
    3. **Consolidated Financial Basis:** Primary reported figures reflect the consolidated operations of the parent company and its subsidiaries.
    4. **Zero Operational Cost:** The product runs without paid APIs, runtime scraping, external cloud databases, or mandatory configuration.
    """)

    st.markdown("---")

    # Coverage Report Table
    st.markdown("### **Company-Level Target Reporting Horizon & Period Coverage**")
    st.caption(f"Dataset Snapshot Cutoff: `2026-10-18` • Universe: {total_comps} Companies across {total_periods} Completed Annual Periods • {reconciled_metrics} Primary Disclosures Independently Reconciled ({reconciled_metrics / total_datapoints * 100:.1f}%), {unverified_metrics} Sourced / Discrepancy Log.")
    
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
    Fundamentals Lens • Evidence-First SEC & Indian Corporate Disclosure Intelligence • Built with Streamlit & Plotly • Verified Public Regulatory Filings
</div>
""", unsafe_allow_html=True)
