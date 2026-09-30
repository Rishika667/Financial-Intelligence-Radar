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
    st.error("config/sp500_representative_51_2026.json not found. Cannot load company universe.")
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
        include_peers = st.checkbox("Also fetch SEC data for unmonitored peers to build peer context", value=True)
        if st.button("Refresh Selected Data"):
            if not user_agent:
                st.error("Cannot refresh without SEC_USER_AGENT.")
            else:
                progress = st.progress(0)
                status_list = []
                client = SECClient(user_agent)
                
                # Determine ingestion list
                ingest_list = list(active_tickers)
                if include_peers:
                    from financial_radar.peers import load_peer_groups, find_peer_group
                    pg = load_peer_groups("config/sp500_representative_51_2026.json")
                    for t in active_tickers:
                        gid, peers = find_peer_group(t, pg)
                        for p in peers:
                            if p not in ingest_list:
                                ingest_list.append(p)
                                
                success_count = 0
                for i, ticker in enumerate(ingest_list):
                    if ticker not in universe_map: continue
                    try:
                        ingest_company(client, db, universe_map[ticker])
                        status_list.append({"Company": ticker, "Status": "SUCCESS", "Message": ""})
                        success_count += 1
                    except Exception as e:
                        import traceback
                        traceback.print_exc()
                        status_list.append({"Company": ticker, "Status": "FAILED", "Message": str(e)})
                    progress.progress((i + 1) / len(ingest_list))
                
                # Refresh peer contexts for active tickers
                refresh_peer_contexts(db, active_tickers)
                
                total = len(ingest_list)
                failed = total - success_count
                
                if failed == 0:
                    st.success(f"SUCCESS: Data refresh completed successfully for all {total} companies.")
                elif success_count == 0:
                    st.error(f"FAILED: Data refresh failed for all {total} companies.")
                else:
                    st.warning(f"PARTIAL SUCCESS: Refresh completed with {success_count}/{total} companies successful. {failed} failed.")
                
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
        signals = rows(db, f"SELECT s.*, p.weight, p.exposure FROM signals s LEFT JOIN portfolio p ON s.company = p.ticker WHERE s.company IN ({placeholders}) AND s.suppressed IS NULL ORDER BY CASE severity WHEN 'HIGH' THEN 1 WHEN 'MODERATE' THEN 2 WHEN 'LOW' THEN 3 ELSE 4 END ASC", active_tickers)
        if signals:
            for s in signals:
                sev_color = "red" if s["severity"] == "HIGH" else "orange" if s["severity"] == "MODERATE" else "blue"
                with st.expander(f"[{s['severity']}] {s['company']} - {s['signal_id']} (Confidence: {s['confidence']})"):
                    st.markdown(f"**Explanation:** {s['explanation']}")
                    st.markdown(f"**Investigation:** Review {s['signal_id']} alongside latest 10-Q/10-K disclosures.")
                    
                    if s.get("weight") is not None:
                        st.markdown(f"**Portfolio Context:** Weight: {s['weight']*100:.2f}%, Exposure: ")
                    st.markdown("### Evidence")

                    if s["evidence"]:
                        try:
                            ev_data = json.loads(s["evidence"])
                            st.json(ev_data)
                        except:
                            st.write(s["evidence"])
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
            all_q_obs = rows(db, "SELECT metric, value, unit, period_end, quality FROM observations WHERE company=? AND period_type='QUARTER' ORDER BY period_end DESC", (ticker,))
            
            latest_metrics = {}
            for row in all_q_obs:
                if row["metric"] not in latest_metrics:
                    latest_metrics[row["metric"]] = row["value"]
            
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Revenue", "$" + f"{latest_metrics['revenue']:,.0f}" if latest_metrics.get('revenue') is not None else "N/A")
            col2.metric("Gross Margin", f"{latest_metrics['gross_margin']*100:.1f}%" if latest_metrics.get('gross_margin') is not None else "N/A")
            col3.metric("Operating Margin", f"{latest_metrics['operating_margin']*100:.1f}%" if latest_metrics.get('operating_margin') is not None else "N/A")
            col4.metric("Net Income", "$" + f"{latest_metrics['net_income']:,.0f}" if latest_metrics.get('net_income') is not None else "N/A")
            
            st.markdown("## 2. Analyst Synthesis")
            synth = synthesize_company(ticker, db)
            st.write("**OBSERVED:**")
            for item in synth['observed']: st.write(f"- {item}")
            st.write("**CONTEXT:**")
            for item in synth['context']: st.write(f"- {item}")
            st.write("**INVESTIGATE:**")
            for item in synth['investigate']: st.write(f"- {item}")
            
            st.markdown("## 3. Financial Performance")
            
            st.markdown("### Historical Series")
            hist_metrics = ("revenue", "gross_margin", "operating_margin", "operating_cash_flow", "free_cash_flow", "revenue_growth_yoy")
            hist_obs = [r for r in all_q_obs if r["metric"] in hist_metrics]
            if hist_obs:
                df_trends = pd.DataFrame(hist_obs)
                # Ensure it's sorted historically
                df_trends = df_trends.sort_values("period_end")
                fig = px.line(df_trends, x="period_end", y="value", color="metric", markers=True, title="Quarterly Historical Trends")
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Insufficient data for trend charts.")
    
            
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
            
            peers_obs = rows(db, "SELECT * FROM peer_context WHERE company=?", (ticker,))
            if not peers_obs:
                st.info("Insufficient peer coverage.")
            else:
                st.dataframe(pd.DataFrame(peers_obs), hide_index=True, use_container_width=True)
