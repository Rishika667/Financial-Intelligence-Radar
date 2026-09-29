import os
import json
import time
import requests
import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime

from financial_radar.store import connect, rows, save_watchlist, save_portfolio
from financial_radar.pipeline import load_universe, ingest_company, refresh_peer_contexts, calculate_data_readiness, validate_portfolio_csv
from financial_radar.core import SECClient
from financial_radar.intelligence import generate_intelligence
from financial_radar.models import ReadinessState
from financial_radar.synthesis import synthesize_company

st.set_page_config(page_title="Financial Intelligence Radar", layout="wide", initial_sidebar_state="expanded")
st.title("Financial Intelligence Radar")
st.caption("Public-disclosure intelligence for analyst attention — not investment advice.")

db = connect()
try:
    universe = load_universe()
except FileNotFoundError:
    st.error("config/sp500_representative_50_2026.json not found. Cannot load company universe.")
    st.stop()

universe_map = {c["ticker"]: c for c in universe}

active_tickers = sorted({r["ticker"] for r in rows(db, "SELECT ticker FROM watchlist WHERE active=1")})
user_agent = os.environ.get("SEC_USER_AGENT", "")

def test_sec_connectivity(ua):
    results = {'USER_AGENT_CONFIGURED': False, 'SEC_REACHABLE': False, 'SUBMISSIONS_REACHABLE': False, 'XBRL_REACHABLE': False}
    if not ua or len(ua) < 5: return results
    results['USER_AGENT_CONFIGURED'] = True
    headers = {'User-Agent': ua}
    try:
        if requests.get('https://www.sec.gov/', headers=headers, timeout=5).status_code == 200:
            results['SEC_REACHABLE'] = True
        if requests.get('https://data.sec.gov/submissions/CIK0000320193.json', headers=headers, timeout=5).status_code == 200:
            results['SUBMISSIONS_REACHABLE'] = True
        if requests.get('https://data.sec.gov/api/xbrl/companyfacts/CIK0000320193.json', headers=headers, timeout=5).status_code == 200:
            results['XBRL_REACHABLE'] = True
    except Exception:
        pass
    return results

tab_setup, tab_portfolio, tab_dashboard, tab_research = st.tabs([
    "Setup & Preflight", "Portfolio Sync", "Attention Queue", "Research Mode"
])

with tab_setup:
    st.subheader("1. Company Selection")
    selected_tickers = st.multiselect("Select Companies to Monitor:", options=[u["ticker"] for u in universe], default=active_tickers, format_func=lambda x: f"{x} - {universe_map[x].get('name', 'Unknown')} ({universe_map[x].get('sector', 'Unknown')})")
    if st.button("Save Monitored Companies"):
        save_watchlist(db, [{"ticker": t, "cik": universe_map[t].get("cik", ""), "active": (t in selected_tickers)} for t in universe_map.keys()])
        st.success("Monitored companies saved!")
        time.sleep(1)
        st.rerun()

    st.subheader("2. SEC Preflight Configuration")
    if st.button("Test SEC Connectivity"):
        with st.spinner("Testing SEC endpoints..."):
            res = test_sec_connectivity(user_agent)
            st.json(res)
            if all(res.values()): st.success("All SEC preflight checks passed.")
            else: st.error("Some SEC preflight checks failed.")
            
    if active_tickers:
        if st.button("Refresh Selected Data"):
            if not user_agent:
                st.error("Cannot refresh without SEC_USER_AGENT.")
            else:
                progress = st.progress(0)
                status_list = []
                client = SECClient(user_agent)
                for i, ticker in enumerate(active_tickers):
                    try:
                        ingest_company(ticker, universe_map[ticker]["cik"], db, client)
                        status_list.append({"Company": ticker, "Status": "SUCCESS"})
                    except Exception as exc:
                        st.error(f"Failed to ingest {ticker}: {exc}")
                        status_list.append({"Company": ticker, "Status": "FAILED"})
                    progress.progress((i + 1) / len(active_tickers))
                with st.spinner("Computing peer contexts..."):
                    refresh_peer_contexts(db, active_tickers)
                st.success("Data refresh complete.")
                st.dataframe(pd.DataFrame(status_list), use_container_width=True, hide_index=True)
                
    st.subheader("3. Data Readiness")
    if active_tickers:
        readiness_list = []
        for t in active_tickers:
            r_state, r_msg = calculate_data_readiness(t, db)
            readiness_list.append({"Company": t, "State": r_state, "Details": r_msg})
        st.dataframe(pd.DataFrame(readiness_list), use_container_width=True, hide_index=True)

with tab_portfolio:
    st.subheader("Portfolio Sync")
    uploaded_file = st.file_uploader("Upload Portfolio Holdings (CSV)", type=["csv"])
    if uploaded_file is not None:
        try:
            df_port = pd.read_csv(uploaded_file)
            is_valid, err_msg = validate_portfolio_csv(df_port, [u["ticker"] for u in universe])
            if not is_valid: st.error(f"Validation failed: {err_msg}")
            else:
                if st.button("Apply Portfolio"):
                    save_portfolio(db, df_port.to_dict(orient="records"))
                    st.success("Portfolio saved.")
        except Exception as e:
            st.error(f"Failed to process CSV: {e}")

with tab_dashboard:
    st.subheader("Attention Queue")
    if not active_tickers:
        st.info("No active companies.")
    else:
        placeholders = ",".join("?" * len(active_tickers))
        signals = rows(db, f"SELECT company as Company, signal_id as Signal, severity as Severity FROM signals WHERE company IN ({placeholders}) AND suppressed IS NULL ORDER BY CASE severity WHEN 'HIGH' THEN 1 WHEN 'MODERATE' THEN 2 WHEN 'LOW' THEN 3 ELSE 4 END ASC", active_tickers)
        if signals:
            st.dataframe(pd.DataFrame(signals), use_container_width=True, hide_index=True)
        else:
            st.success("No actionable deterioration signals detected.")

with tab_research:
    if not active_tickers:
        st.info("No active companies.")
    else:
        ticker = st.selectbox("Select Company for Research", active_tickers)
        company_meta = universe_map.get(ticker, {})
        st.header(f"{ticker} - {company_meta.get('name', 'Unknown')} ({company_meta.get('sector', 'Unknown')})")
        
        r_state, r_msg = calculate_data_readiness(ticker, db)
        if r_state == ReadinessState.NOT_READY:
            st.error(f"NOT READY: {r_msg}")
        elif r_state == ReadinessState.FAILED:
            st.error(f"FAILED: {r_msg}")
        else:
            if r_state == ReadinessState.PARTIAL: st.warning(f"PARTIAL: {r_msg}")
            else: st.success("READY")
            
            st.markdown("## 1. Executive Snapshot")
            latest_obs = rows(db, "SELECT metric, value, unit, period_end FROM observations WHERE company=? AND period_type='QUARTER' ORDER BY period_end DESC", (ticker,))
            latest_metrics = {row["metric"]: row["value"] for row in latest_obs}
            
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Revenue", f"${latest_metrics.get('revenue', 0):,.0f}" if 'revenue' in latest_metrics else "N/A")
            col2.metric("Gross Margin", f"{latest_metrics.get('gross_margin', 0)*100:.1f}%" if 'gross_margin' in latest_metrics else "N/A")
            col3.metric("Operating Margin", f"{latest_metrics.get('operating_margin', 0)*100:.1f}%" if 'operating_margin' in latest_metrics else "N/A")
            col4.metric("Net Income", f"${latest_metrics.get('net_income', 0):,.0f}" if 'net_income' in latest_metrics else "N/A")
            
            st.markdown("## 2. Analyst Synthesis")
            synth = synthesize_company(ticker, db)
            st.write("**OBSERVED:**")
            for item in synth['observed']: st.write(f"- {item}")
            st.write("**CONTEXT:**")
            for item in synth['context']: st.write(f"- {item}")
            st.write("**INVESTIGATE:**")
            for item in synth['investigate']: st.write(f"- {item}")
            
            st.markdown("## 3. Financial Performance")
            st.info("Trend charts disabled in basic view.")
            
            st.markdown("## 4. Signals & Evidence")
            company_signals = rows(db, "SELECT * FROM signals WHERE company=? ORDER BY CASE WHEN suppressed IS NOT NULL THEN 5 WHEN severity = 'HIGH' THEN 1 WHEN severity = 'MODERATE' THEN 2 WHEN severity = 'LOW' THEN 3 ELSE 4 END ASC", (ticker,))
            for s in company_signals:
                if bool(s.get("suppressed")):
                    with st.expander(f"⚠️ SUPPRESSED: {s['signal_id'].replace('_', ' ').title()}", expanded=False):
                        st.info(f"**Suppressed Reason:** {s['suppressed_reason']}")
                else:
                    ev_str = s.get("evidence", "[]")
                    intel = generate_intelligence(s["signal_id"], ticker, company_meta.get("sector"), ev_str)
                    with st.expander(f"📉 {intel['title']} (Severity: {s['severity']})", expanded=True):
                        st.write(f"**WHAT CHANGED:** {intel['what_changed']}")
                        st.write(f"**WHY IT MATTERS:** {intel['why_it_matters']}")
                        st.write("**Evidence Trail:**")
                        try:
                            ev_json = json.loads(ev_str)
                            for ev_item in ev_json:
                                prov = ev_item.get("provenance", [])
                                if prov:
                                    p = prov[0]
                                    st.caption(f"OBSERVATION: {ev_item.get('metric')} = {ev_item.get('value')} | SEC Source: [EDGAR]({p.get('source_url', '#')})")
                        except: pass
            
            st.markdown("## 5. Peer Context")
            st.info("Peer context disabled in basic view.")
