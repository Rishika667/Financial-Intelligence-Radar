import os
import json
import time
import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime

from financial_radar.store import connect, rows, save_watchlist, save_portfolio
from financial_radar.pipeline import load_universe, ingest_company, refresh_peer_contexts
from financial_radar.core import SECClient
from financial_radar.intelligence import generate_intelligence
from financial_radar.models import ReadinessState

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(page_title="Financial Intelligence Radar", layout="wide", initial_sidebar_state="expanded")
st.title("Financial Intelligence Radar")
st.caption("Public-disclosure intelligence for analyst attention — not investment advice.")

# ---------------------------------------------------------------------------
# Persistent state
# ---------------------------------------------------------------------------
db = connect()
try:
    universe = load_universe()
except FileNotFoundError:
    st.error("config/sp500_representative_50_2026.json not found. Cannot load company universe.")
    st.stop()

# Build useful mappings
universe_map = {c["ticker"]: c for c in universe}

def format_readiness(r):
    if r == "READY": return "✅ Ready"
    if r == "PARTIAL": return "⚠️ Partial"
    if r == "FAILED": return "❌ Failed"
    return "⏳ Not Ready"

# Calculate active tickers
active_tickers = sorted({r["ticker"] for r in rows(db, "SELECT ticker FROM watchlist WHERE active=1")})

# Setup SEC Client for validation
user_agent = os.environ.get("SEC_USER_AGENT", "")

# ---------------------------------------------------------------------------
# Tab Navigation
# ---------------------------------------------------------------------------
tab_setup, tab_portfolio, tab_dashboard, tab_research = st.tabs([
    "Setup & Preflight", "Portfolio Sync", "Attention Queue", "Research Mode"
])

# ---------------------------------------------------------------------------
# Tab 1: Setup & Preflight (First-Run Requirement)
# ---------------------------------------------------------------------------
with tab_setup:
    st.subheader("1. Company Selection & Preflight")
    
    selected_tickers = st.multiselect(
        "Select Companies to Monitor:", 
        options=[u["ticker"] for u in universe],
        default=active_tickers,
        format_func=lambda x: f"{x} - {universe_map[x].get('name', 'Unknown')} ({universe_map[x].get('sector', 'Unknown')})"
    )
    
    if st.button("Save Monitored Companies"):
        save_watchlist(db, [{"ticker": t, "cik": universe_map[t].get("cik", ""), "active": (t in selected_tickers)} for t in universe_map.keys()])
        st.success("Monitored companies saved!")
        time.sleep(1)
        st.rerun()

    st.subheader("2. SEC Connectivity & Data Refresh")
    st.write(f"**SEC User-Agent Environment Variable:** {'Configured' if user_agent else 'MISSING'}")
    if not user_agent:
        st.warning("Please configure SEC_USER_AGENT in your environment to fetch from EDGAR.")
        
    if active_tickers:
        if st.button("Initialize & Refresh Selected Data"):
            if not user_agent:
                st.error("Cannot refresh without SEC_USER_AGENT.")
            else:
                st.write("Refreshing data from SEC EDGAR...")
                progress = st.progress(0)
                status_list = []
                client = SECClient(user_agent)
                
                for i, ticker in enumerate(active_tickers):
                    try:
                        res = ingest_company(ticker, universe_map[ticker]["cik"], db, client)
                        status_list.append({"Company": ticker, "SEC Access": "✅", "Submissions": "✅", "XBRL Data": "✅", "Events": "✅", "Status": "READY"})
                    except Exception as exc:
                        st.error(f"Failed to ingest {ticker}: {exc}")
                        status_list.append({"Company": ticker, "SEC Access": "❌", "Submissions": "-", "XBRL Data": "-", "Events": "-", "Status": "FAILED"})
                    progress.progress((i + 1) / len(active_tickers))
                
                with st.spinner("Computing peer contexts..."):
                    refresh_peer_contexts(db, active_tickers)
                st.success("Data refresh complete.")
                st.dataframe(pd.DataFrame(status_list), use_container_width=True, hide_index=True)

# ---------------------------------------------------------------------------
# Tab 2: Portfolio Sync (Portfolio CSV separate from Watchlist)
# ---------------------------------------------------------------------------
with tab_portfolio:
    st.subheader("Portfolio Sync")
    st.write("Upload a portfolio CSV (ticker, shares, weight, cost_basis) to overlay your holdings. Portfolio companies are distinct from Monitored Companies.")
    
    from financial_radar.pipeline import validate_portfolio_csv
    uploaded_file = st.file_uploader("Upload Portfolio Holdings (CSV)", type=["csv"])
    if uploaded_file is not None:
        try:
            df_port = pd.read_csv(uploaded_file)
            is_valid, err_msg = validate_portfolio_csv(df_port, [u["ticker"] for u in universe])
            if not is_valid:
                st.error(f"Validation failed: {err_msg}")
            else:
                st.success("Portfolio validated successfully.")
                if st.button("Apply Portfolio"):
                    save_portfolio(db, df_port.to_dict(orient="records"))
                    st.success("Portfolio saved.")
        except Exception as e:
            st.error(f"Failed to process CSV: {e}")

# ---------------------------------------------------------------------------
# Tab 3: Attention Queue (Analyst Triage)
# ---------------------------------------------------------------------------
with tab_dashboard:
    st.subheader("Attention Queue")
    if not active_tickers:
        st.info("No active companies. Go to Setup & Preflight to configure companies.")
    else:
        placeholders = ",".join("?" * len(active_tickers))
        signals = rows(
            db,
            f"SELECT company as Company, signal_id as Signal, severity as Severity FROM signals WHERE company IN ({placeholders}) AND suppressed IS NULL ORDER BY CASE severity WHEN 'HIGH' THEN 1 WHEN 'MODERATE' THEN 2 WHEN 'LOW' THEN 3 ELSE 4 END ASC",
            active_tickers,
        )
        if signals:
            df_sig = pd.DataFrame(signals)
            st.dataframe(df_sig, use_container_width=True, hide_index=True)
        else:
            st.success("No actionable deterioration signals detected.")

# ---------------------------------------------------------------------------
# Tab 4: Research Mode (Cross-Metric Synthesis & Evidence)
# ---------------------------------------------------------------------------
with tab_research:
    if not active_tickers:
        st.info("No active companies available for research.")
    else:
        ticker = st.selectbox("Select Company for Research", active_tickers)
        company_meta = universe_map.get(ticker, {})
        
        st.header(f"{ticker} - {company_meta.get('name', 'Unknown')} ({company_meta.get('sector', 'Unknown')})")
        
        # We need to compute readiness state
        obs_count = rows(db, "SELECT count(*) as c FROM observations WHERE company=?", (ticker,))[0]["c"]
        if obs_count == 0:
            st.error("NOT READY: No data exists for this company. Please refresh from the Setup tab.")
        else:
            st.success(f"READY: {obs_count} data points available.")
            
            # --- Executive Snapshot ---
            st.markdown("## 1. Executive Snapshot")
            latest_obs = rows(db, "SELECT metric, value, unit, period_end FROM observations WHERE company=? AND period_type='QUARTER' AND quality IN ('REPORTED', 'DERIVED', 'AMENDED') ORDER BY period_end DESC", (ticker,))
            
            # Build simple dict for latest metrics
            latest_metrics = {}
            for row in latest_obs:
                m = row["metric"]
                if m not in latest_metrics:
                    latest_metrics[m] = row["value"]
            
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Revenue", f"" if 'revenue' in latest_metrics else "N/A")
            col2.metric("Gross Profit", f"" if 'gross_profit' in latest_metrics else "N/A")
            col3.metric("Operating Income", f"" if 'operating_income' in latest_metrics else "N/A")
            col4.metric("Free Cash Flow", f"" if 'free_cash_flow' in latest_metrics else "N/A")
            
            # --- Cross-Metric Synthesis ---
            st.markdown("## 2. Analyst Synthesis")
            company_signals = rows(db, "SELECT * FROM signals WHERE company=? ORDER BY CASE WHEN suppressed IS NOT NULL THEN 5 WHEN severity = 'HIGH' THEN 1 WHEN severity = 'MODERATE' THEN 2 WHEN severity = 'LOW' THEN 3 ELSE 4 END ASC", (ticker,))
            
            if not company_signals:
                st.write("No signals detected.")
            else:
                for s in company_signals:
                    is_suppressed = bool(s.get("suppressed"))
                    if is_suppressed:
                        with st.expander(f"⚠️ SUPPRESSED: {s['signal_id'].replace('_', ' ').title()}", expanded=False):
                            st.info(f"**Suppressed Reason:** {s['suppressed_reason']}")
                            st.write(s.get("explanation", ""))
                    else:
                        ev_str = s.get("evidence", "[]")
                        intel = generate_intelligence(s["signal_id"], ticker, company_meta.get("sector"), ev_str)
                        with st.expander(f"📉 {intel['title']} (Severity: {s['severity']})", expanded=True):
                            st.write(f"**WHAT CHANGED:** {intel['what_changed']}")
                            st.write(f"**WHY IT MATTERS:** {intel['why_it_matters']}")
                            st.write("**INVESTIGATE:**")
                            for item in intel["investigate"]:
                                st.write(f"- {item}")
                                
                            st.write("**Evidence Trail:**")
                            try:
                                ev_json = json.loads(ev_str)
                                if isinstance(ev_json, list) and ev_json:
                                    for ev_item in ev_json:
                                        prov = ev_item.get("provenance", [])
                                        cols_ev = st.columns([1, 1])
                                        with cols_ev[0]:
                                            st.caption("OBSERVATION")
                                            st.write(f"**Metric:** {ev_item.get('metric', 'N/A')}")
                                            val = ev_item.get('value')
                                            st.write(f"**Value:** {'' if val == 0 else val}")
                                            st.write(f"**Unit:** {ev_item.get('unit', 'N/A')}")
                                            st.write(f"**Period End:** {ev_item.get('period_end', 'N/A')}")
                                        with cols_ev[1]:
                                            st.caption("PROVENANCE (SOURCE)")
                                            if prov and len(prov) > 0:
                                                p = prov[0]
                                                st.write(f"**XBRL Concept:** {p.get('concept', 'N/A')}")
                                                st.write(f"**Accession:** {p.get('accession', 'N/A')}")
                                                st.write(f"**Filing Date:** {p.get('filing_date', 'N/A')}")
                                                st.write(f"**Retrieval Time:** {p.get('retrieval_timestamp', 'N/A')}")
                                                st.markdown(f"**[SEC URL]({p.get('source_url', '#')})**")
                                            else:
                                                st.write("No direct provenance available.")
                                        st.divider()
                            except Exception as e:
                                st.caption(f"Could not parse evidence: {e}")
                                
            # --- Historical Trends ---
            st.markdown("## 3. Financial Performance (Historical)")
            hist_df = pd.DataFrame(rows(db, "SELECT metric, value, period_end, period_type FROM observations WHERE company=? AND period_type='QUARTER'", (ticker,)))
            if not hist_df.empty:
                metric_sel = st.selectbox("Select Metric", hist_df["metric"].unique().tolist())
                filtered_hist = hist_df[hist_df["metric"] == metric_sel].sort_values("period_end")
                if not filtered_hist.empty:
                    fig = px.line(filtered_hist, x="period_end", y="value", title=f"{metric_sel.replace('_', ' ').title()} (Quarterly)")
                    st.plotly_chart(fig, use_container_width=True)

            # --- Peer Comparison ---
            st.markdown("## 4. Peer Comparison")
            company_peers = rows(db, "SELECT metric, company_value, peer_median, peer_min, peer_max, n_peers, group_id FROM peer_context WHERE company=?", (ticker,))
            if company_peers:
                n_peers = company_peers[0]["n_peers"] if company_peers else 0
                if n_peers < 2:
                    st.info("Insufficient peer coverage.")
                else:
                    st.write(f"**Peer group:** {company_peers[0]['group_id']} | **Peer count:** {n_peers}")
                    st.dataframe(pd.DataFrame(company_peers)[['metric', 'company_value', 'peer_median', 'peer_min', 'peer_max']], use_container_width=True, hide_index=True)
            else:
                st.info("Insufficient peer coverage.")
                
            # --- Corporate Events ---
            st.markdown("## 5. Corporate Events (Recent 5 Filings Only)")
            events = rows(db, "SELECT type, filed, description, source_url, accession, form FROM events WHERE company=? ORDER BY filed DESC LIMIT 10", (ticker,))
            if events:
                for e in events:
                    st.write(f"**{e['filed']} - {e['type'].upper()}**")
                    st.write(f"*{e['description']}* (Heuristic extraction - may not capture full exhibit text)")
                    st.caption(f"Form: {e.get('form', 'Unknown')} | Accession: {e.get('accession', 'Unknown')} | [SEC Source]({e.get('source_url', '#')})")
                    st.divider()
            else:
                st.info("No recent material events extracted.")
