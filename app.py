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
from financial_radar.synthesis import synthesize_company, format_val

st.set_page_config(page_title="Financial Intelligence Radar", layout="wide", initial_sidebar_state="expanded")
st.title("Financial Intelligence Radar")
st.caption("Public-disclosure intelligence for analyst attention — not investment advice.")

db_path = os.environ.get("DB_PATH", "financial_radar.sqlite")
db = connect(db_path)
try:
    universe = load_universe()
except FileNotFoundError:
    st.error("config/sp500_representative_51_2026.json not found. Cannot load company universe.")
    st.stop()

universe_map = {c["ticker"]: c for c in universe}
try:
    peer_refs = json.loads(open("config/sp500_representative_51_2026.json").read()).get("peer_references", [])
    for c in peer_refs:
        universe_map[c["ticker"]] = c
except: pass

active_tickers = sorted({r["ticker"] for r in rows(db, "SELECT ticker FROM watchlist WHERE active=1")})
user_agent = os.environ.get("SEC_USER_AGENT", "")

def test_sec_connectivity(ua):
    results = {'USER_AGENT_CONFIGURED': False, 'SEC_REACHABLE': False, 'SUBMISSIONS_REACHABLE': False, 'XBRL_REACHABLE': False, 'ERRORS': []}
    if not ua or len(ua) < 5: 
        results['ERRORS'].append("Invalid or missing SEC_USER_AGENT environment variable")
        return results
    results['USER_AGENT_CONFIGURED'] = True
    headers = {'User-Agent': ua, 'Accept-Encoding': 'gzip, deflate'}
    
    import requests
    try:
        r1 = requests.get('https://www.sec.gov/', headers=headers, timeout=5)
        r1.raise_for_status()
        results['SEC_REACHABLE'] = True
        
        r2 = requests.get('https://data.sec.gov/submissions/CIK0000320193.json', headers=headers, timeout=5)
        r2.raise_for_status()
        results['SUBMISSIONS_REACHABLE'] = True
        
        r3 = requests.get('https://data.sec.gov/api/xbrl/companyfacts/CIK0000320193.json', headers=headers, timeout=5)
        r3.raise_for_status()
        results['XBRL_REACHABLE'] = True
    except requests.exceptions.RequestException as e:
        results['ERRORS'].append(f"Network or protocol error: {e}")
        
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
            # Success means the 4 booleans are True (and ERRORS can be empty)
            success = all([res.get(k) for k in ('USER_AGENT_CONFIGURED', 'SEC_REACHABLE', 'SUBMISSIONS_REACHABLE', 'XBRL_REACHABLE')])
            if success:
                st.success("All SEC preflight checks passed.")
            else:
                st.error("Some SEC preflight checks failed.")
            
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
        signals = rows(db, f"SELECT s.*, p.weight, p.exposure FROM signals s LEFT JOIN portfolio p ON s.company = p.ticker WHERE s.company IN ({placeholders}) AND s.suppressed IS NULL ORDER BY CASE severity WHEN 'HIGH' THEN 1 WHEN 'MEDIUM' THEN 2 WHEN 'LOW' THEN 3 ELSE 4 END ASC", active_tickers)
        if signals:
            for s in signals:
                sev_color = "red" if s["severity"] == "HIGH" else "orange" if s["severity"] == "MEDIUM" else "blue"
                with st.expander(f"[{s['severity']}] {s['company']} - {s['signal_id']} (Confidence: {s['confidence']})"):
                    st.markdown(f"**Explanation:** {s['explanation']}")
                    st.markdown(f"**Investigation:** Review {s['signal_id']} alongside latest 10-Q/10-K disclosures.")
                    
                    if s.get("weight") is not None and s.get("exposure") is not None:
                        st.markdown(f"**Portfolio Context:** Weight: {s['weight']*100:.2f}%, Exposure: {format_val(s['exposure'])}")
                    else:
                        st.markdown("**Portfolio Context:** Not held")
                        
                    # Peer Context mapping
                    metric_map = {
                        "GROSS_MARGIN_COMPRESSION": "gross_margin",
                        "OPERATING_MARGIN_DETERIORATION": "operating_margin",
                        "EARNINGS_CASH_CONVERSION_DETERIORATION": "cash_conversion",
                        "FREE_CASH_FLOW_DETERIORATION": "free_cash_flow",
                        "DEBT_OPERATING_INCOME_DETERIORATION": "debt_operating_income",
                        "LIQUIDITY_COMPRESSION": "liquidity_ratio",
                        "SHARE_COUNT_DILUTION": "share_count",
                        "RECEIVABLES_REVENUE_DIVERGENCE": "receivables_revenue_ratio",
                        "INVENTORY_SALES_DIVERGENCE": "inventory_revenue_ratio"
                    }
                    mapped_metric = metric_map.get(s['signal_id'])
                    if mapped_metric:
                        peer_ctx = rows(db, "SELECT * FROM peer_context WHERE company=? AND metric=?", (s['company'], mapped_metric))
                        if peer_ctx:
                            ctx = peer_ctx[0]
                            st.markdown("### Peer Context")
                            if ctx.get("peer_median") is not None:
                                pos = ctx.get("position", "Unknown")
                                st.markdown(f"- **Relative Position:** {pos}")
                                unit_map = {
                                    "gross_margin": "pure", "operating_margin": "pure",
                                    "cash_conversion": "multiple", "debt_operating_income": "multiple", "liquidity_ratio": "multiple",
                                    "receivables_revenue_ratio": "pure", "inventory_revenue_ratio": "pure",
                                    "share_count": "shares", "free_cash_flow": s.get("unit", "USD") # We don't have unit in peer_context, but we have it in evidence, but it's not easily accessible here. Let's use USD fallback.
                                }
                                pm_unit = unit_map.get(mapped_metric, "USD")
                                if mapped_metric == "free_cash_flow" and s.get("evidence"):
                                    try:
                                        import json
                                        ev_json = json.loads(s["evidence"])
                                        if ev_json: pm_unit = ev_json[0].get("unit", "USD")
                                    except: pass
                                st.markdown(f"- **Peer Median:** {format_val(ctx.get('peer_median'), pm_unit)}")
                                st.markdown(f"- **Coverage:** {ctx.get('availability_state', str(ctx.get('n_peers')) + ' peers')}")
                            else:
                                st.markdown("Peer context unavailable")

                    st.markdown("### Evidence Summary")

                    if s["evidence"]:
                        try:
                            ev_data = json.loads(s["evidence"])
                            for ev_idx, ev_item in enumerate(ev_data):
                                metric = ev_item.get("metric", "Unknown")
                                val = ev_item.get("value")
                                f_val = format_val(val, ev_item.get("unit", "USD"))
                                pend = ev_item.get("period_end", "")
                                ptype = ev_item.get("period_type", "")
                                fper = ev_item.get("fiscal_period", "N/A")
                                
                                st.markdown(f"**{metric.upper()}** - {f_val} ({pend} {ptype} - FY{ev_item.get('fiscal_year', 'N/A')} {fper})")
                                
                                provs = ev_item.get("provenance", [])
                                if provs:
                                    st.markdown("#### SEC Source")
                                    for p in provs:
                                        acc = p.get("accession", "N/A")
                                        form = p.get("form", "N/A")
                                        fdate = p.get("filing_date", "N/A")
                                        concept = p.get("concept", "N/A")
                                        url = p.get("source_url", "")
                                        
                                        st.markdown(f"- **Form:** {form} | **Filed:** {fdate} | **Accession:** {acc} | **Concept:** {concept}")
                                        if url and url != "#":
                                            st.markdown(f"[Open SEC Filing]({url})")
                                        else:
                                            st.markdown("*SEC source unavailable*")
                                else:
                                    st.markdown("*SEC source unavailable*")
                        except Exception as e:
                            st.error(f"Failed to parse evidence: {e}")
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
            all_q_obs = rows(db, "SELECT metric, value, unit, period_end, period_type, quality, fiscal_year, fiscal_period FROM observations WHERE company=? AND period_type='QUARTER' ORDER BY period_end DESC", (ticker,))
            
            latest_metrics = {}
            latest_meta = {}
            
            # Find the most recent period_end across all metrics
            max_q_end = all_q_obs[0]['period_end'] if all_q_obs else None
            
            for row in all_q_obs:
                if row['period_end'] == max_q_end:
                    if row["metric"] not in latest_metrics:
                        latest_metrics[row["metric"]] = row
                        latest_meta[row["metric"]] = row
            
            # Show period metadata
            ref_row = latest_meta.get("revenue") or (list(latest_meta.values())[0] if latest_meta else None)
            if ref_row:
                fy_label = f"FY{ref_row.get('fiscal_year', 'N/A')}" if ref_row.get('fiscal_year') else ""
                fp_label = ref_row.get('fiscal_period', '') or ''
                st.caption(f"Latest quarterly data: {ref_row['period_end']} {fy_label} {fp_label} | Quality: {ref_row.get('quality', 'N/A')}")
            
            col1, col2, col3, col4 = st.columns(4)
            rev_val = latest_metrics.get("revenue", {}).get("value") if isinstance(latest_metrics.get("revenue"), dict) else latest_metrics.get("revenue")
            gm_val = latest_metrics.get("gross_margin", {}).get("value") if isinstance(latest_metrics.get("gross_margin"), dict) else latest_metrics.get("gross_margin")
            om_val = latest_metrics.get("operating_margin", {}).get("value") if isinstance(latest_metrics.get("operating_margin"), dict) else latest_metrics.get("operating_margin")
            ni_val = latest_metrics.get("net_income", {}).get("value") if isinstance(latest_metrics.get("net_income"), dict) else latest_metrics.get("net_income")

            # We need to find units for rev_val and ni_val
            rev_unit = next((o['unit'] for o in all_q_obs if o['metric'] == 'revenue' and o['period_end'] == (ref_row['period_end'] if ref_row else '')), "USD")
            ni_unit = next((o['unit'] for o in all_q_obs if o['metric'] == 'net_income' and o['period_end'] == (ref_row['period_end'] if ref_row else '')), "USD")
            
            col1.metric("Revenue", format_val(rev_val, rev_unit) if rev_val is not None else "N/A")
            col2.metric("Gross Margin", format_val(gm_val, "pure") if gm_val is not None else "N/A")
            col3.metric("Operating Margin", format_val(om_val, "pure") if om_val is not None else "N/A")
            col4.metric("Net Income", format_val(ni_val, ni_unit) if ni_val is not None else "N/A")
            
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
            if all_q_obs:
                df_trends = pd.DataFrame(all_q_obs).sort_values("period_end")
                
# Chart A: Monetary performance
                df_a = df_trends[df_trends["metric"].isin(["revenue", "net_income", "operating_cash_flow", "free_cash_flow"])]
                if not df_a.empty:
                    units_a = df_a["unit"].unique()
                    if len(units_a) > 1:
                        st.warning("Chart A suppressed due to mixed monetary units (e.g., currency changes).")
                    else:
                        unit_a = units_a[0]
                        fig_a = px.line(df_a, x="period_end", y="value", color="metric", markers=True, title=f"Chart A: Revenue & Cash Flow ({unit_a})", labels={"value": unit_a})
                        st.plotly_chart(fig_a, use_container_width=True)
                    
                # Chart B: Margins
                chart_b_metrics = ["gross_margin", "operating_margin", "net_margin"]
                df_b = df_trends[df_trends["metric"].isin(chart_b_metrics)]
                if not df_b.empty:
                    df_b_copy = df_b.copy()
                    df_b_copy["value"] = df_b_copy["value"] * 100
                    fig_b = px.line(df_b_copy, x="period_end", y="value", color="metric", markers=True, title="Chart B: Margins (%)", labels={"value": "Margin %"})
                    st.plotly_chart(fig_b, use_container_width=True)
                    
                # Chart C: Growth
                chart_c_metrics = ["revenue_growth_yoy"]
                df_c = df_trends[df_trends["metric"].isin(chart_c_metrics)]
                if not df_c.empty:
                    df_c_copy = df_c.copy()
                    df_c_copy["value"] = df_c_copy["value"] * 100
                    fig_c = px.line(df_c_copy, x="period_end", y="value", color="metric", markers=True, title="Chart C: Growth (YoY %)", labels={"value": "Growth %"})
                    st.plotly_chart(fig_c, use_container_width=True)
            else:
                st.info("Insufficient data for trend charts.")
    
            
            st.markdown("## 4. Signals & Evidence")
            company_signals = rows(db, "SELECT * FROM signals WHERE company=? ORDER BY CASE WHEN suppressed IS NOT NULL THEN 5 WHEN severity = 'HIGH' THEN 1 WHEN severity = 'MEDIUM' THEN 2 WHEN severity = 'LOW' THEN 3 ELSE 4 END ASC", (ticker,))
            for s in company_signals:
                if bool(s.get("suppressed")):
                    with st.expander(f"⚠️ SUPPRESSED: {s['signal_id'].replace('_', ' ').title()}", expanded=False):
                        st.info(f"**Suppressed Reason:** {s['suppressed']}")
                else:
                    ev_str = s.get("evidence", "[]")
                    intel = generate_intelligence(s["signal_id"], ticker, company_meta.get("sector"), ev_str)
                    with st.expander(f"📉 {intel['title']} (Severity: {s['severity']})", expanded=True):
                        st.write(f"**WHAT CHANGED:** {intel['what_changed']}")
                        st.write(f"**WHY IT MATTERS:** {intel['why_it_matters']}")
                        st.write("**Evidence Trail:**")
                        try:
                            ev_json = json.loads(ev_str)
                            if len(ev_json) >= 2:
                                curr = ev_json[0]
                                prior = ev_json[1]
                                
                                st.markdown("##### CURRENT OBSERVATION")
                                st.markdown(f"- **Metric:** {curr.get('metric')} | **Value:** {format_val(curr.get('value'), curr.get('unit'))} | **Unit:** {curr.get('unit')}")
                                st.markdown(f"- **Period:** {curr.get('period_end')} ({curr.get('period_type')}) | **Fiscal:** FY{curr.get('fiscal_year', 'N/A')} {curr.get('fiscal_period', 'N/A')} | **Quality:** {curr.get('quality')}")
                                
                                st.markdown("##### PRIOR OBSERVATION")
                                st.markdown(f"- **Metric:** {prior.get('metric')} | **Value:** {format_val(prior.get('value'), prior.get('unit'))} | **Unit:** {prior.get('unit')}")
                                st.markdown(f"- **Period:** {prior.get('period_end')} ({prior.get('period_type')}) | **Fiscal:** FY{prior.get('fiscal_year', 'N/A')} {prior.get('fiscal_period', 'N/A')} | **Quality:** {prior.get('quality')}")
                            elif len(ev_json) == 1:
                                curr = ev_json[0]
                                st.markdown("##### CURRENT OBSERVATION")
                                st.markdown(f"- **Metric:** {curr.get('metric')} | **Value:** {format_val(curr.get('value'), curr.get('unit'))} | **Unit:** {curr.get('unit')}")
                                st.markdown(f"- **Period:** {curr.get('period_end')} ({curr.get('period_type')}) | **Fiscal:** FY{curr.get('fiscal_year', 'N/A')} {curr.get('fiscal_period', 'N/A')} | **Quality:** {curr.get('quality')}")

                            for ev_idx, ev_item in enumerate(ev_json):
                                derived = ev_item.get("derived_from")
                                if derived and isinstance(derived, list) and len(derived) > 0:
                                    st.markdown(f"**DERIVATION ({ev_item.get('metric')}):** {', '.join(derived)}")

                                provs = ev_item.get("provenance", [])
                                if provs:
                                    st.markdown(f"**SOURCE ({ev_item.get('metric')}):**")
                                    for p in provs:
                                        acc = p.get("accession", "N/A")
                                        form = p.get("form", "N/A")
                                        fdate = p.get("filing_date", "N/A")
                                        concept = p.get("concept", "N/A")
                                        raw = p.get("raw_value")
                                        url = p.get("source_url", "")
                                        st.markdown(f"- **Concept:** {concept} | **Raw:** {raw} | **Accession:** {acc} | **Form:** {form} | **Filed:** {fdate}")
                                        if url and url != '#':
                                            st.markdown(f"  - [Open SEC Filing]({url})")
                                        else:
                                            st.markdown("  - *SEC source unavailable*")
                        except Exception as e:
                            st.error(f"Failed to parse evidence trail: {e}")
            
            st.markdown("## 5. Peer Context")
            
            peers_obs = rows(db, "SELECT * FROM peer_context WHERE company=?", (ticker,))
            if not peers_obs:
                st.info("Insufficient peer coverage.")
            else:
                st.dataframe(pd.DataFrame(peers_obs), hide_index=True, use_container_width=True)
                
                # Extract all unavailable peers
                unavails = set()
                for row in peers_obs:
                    up = row.get("unavailable_peers")
                    if up:
                        import json
                        try:
                            for p in json.loads(up):
                                unavails.add(p)
                        except json.JSONDecodeError:
                            pass
                
                if unavails:
                    for p in sorted(list(unavails)):
                        st.warning(f"{p} Peer coverage unavailable")
