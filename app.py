import os
import json
import time
import requests
import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime

from financial_radar.store import (
    connect, rows, save_watchlist, save_portfolio,
    save_analyst_review, get_analyst_review, get_all_analyst_reviews,
    generate_alert_fingerprint, save_refresh_history, get_refresh_history,
    get_latest_refresh_time, VALID_REVIEW_STATUSES
)
from financial_radar.pipeline import load_universe, ingest_company, refresh_peer_contexts, calculate_data_readiness, validate_portfolio_csv
from financial_radar.core import SECClient
from financial_radar.intelligence import generate_intelligence, resolve_evidence_pair, group_cluster_evidence_by_metric
from financial_radar.models import ReadinessState
from financial_radar.synthesis import synthesize_company, format_val
from financial_radar.config import get_sec_user_agent, is_public_demo_mode, validate_user_agent

st.set_page_config(page_title="Financial Intelligence Radar", layout="wide", initial_sidebar_state="expanded")
st.title("Financial Intelligence Radar")
st.caption("Public-disclosure intelligence for analyst attention — not investment advice.")

user_agent = get_sec_user_agent()
public_demo = is_public_demo_mode()

if public_demo:
    st.info("ℹ️ **Public Demo Mode Active:** Visitor-specific portfolio holdings, notes, and monitored selections are isolated to your browser session to protect visitor privacy.")

if not user_agent:
    st.warning("⚠️ **Live SEC Ingestion Unavailable:** `SEC_USER_AGENT` is not configured. The dashboard is running in read-only analysis mode on cached disclosures. To enable live SEC ingestion, configure `SEC_USER_AGENT` in Streamlit Community Cloud Secrets (e.g., `SEC_USER_AGENT = \"Your Name your.email@example.com\"`) or set the `SEC_USER_AGENT` environment variable.")

db_path = os.environ.get("DB_PATH", "financial_radar.sqlite")
db = connect(db_path)
try:
    universe = load_universe()
except FileNotFoundError:
    st.error("Universe configuration not found. Cannot load company universe.")
    st.stop()

universe_map = {c["ticker"]: c for c in universe}
import logging
logger = logging.getLogger(__name__)

for cfg_candidate in ("config/sp500_universe_2026.json", "config/sp500_representative_51_2026.json"):
    if os.path.exists(cfg_candidate):
        try:
            peer_refs = json.loads(open(cfg_candidate, encoding="utf-8").read()).get("peer_references", [])
            for c in peer_refs:
                if c["ticker"] not in universe_map:
                    universe_map[c["ticker"]] = c
            break
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.warning("Could not load peer_references from %s: %s", cfg_candidate, e)

db_active_tickers = sorted({r["ticker"] for r in rows(db, "SELECT ticker FROM watchlist WHERE active=1")})
if public_demo and "monitored_tickers" in st.session_state:
    active_tickers = st.session_state["monitored_tickers"]
else:
    active_tickers = db_active_tickers

def test_sec_connectivity(ua):
    results = {'USER_AGENT_CONFIGURED': False, 'SEC_REACHABLE': False, 'SUBMISSIONS_REACHABLE': False, 'XBRL_REACHABLE': False, 'ERRORS': []}
    if not validate_user_agent(ua): 
        results['ERRORS'].append("Invalid or missing SEC_USER_AGENT. It must identify an operator and contact email (e.g., 'AnalystName analyst@example.com').")
        return results
    results['USER_AGENT_CONFIGURED'] = True
    headers = {'User-Agent': ua, 'Accept-Encoding': 'gzip, deflate'}
    
    import requests
    # 1. Test SEC homepage reachability
    try:
        r1 = requests.get('https://www.sec.gov/', headers=headers, timeout=5)
        r1.raise_for_status()
        results['SEC_REACHABLE'] = True
    except requests.exceptions.RequestException as e:
        results['ERRORS'].append(f"SEC home-page unreachable: {e}")
        
    # 2. Test SEC submissions endpoint reachability independently
    try:
        r2 = requests.get('https://data.sec.gov/submissions/CIK0000320193.json', headers=headers, timeout=5)
        r2.raise_for_status()
        results['SUBMISSIONS_REACHABLE'] = True
    except requests.exceptions.RequestException as e:
        results['ERRORS'].append(f"SEC submissions endpoint unreachable: {e}")
        
    # 3. Test SEC XBRL companyfacts endpoint reachability independently
    try:
        r3 = requests.get('https://data.sec.gov/api/xbrl/companyfacts/CIK0000320193.json', headers=headers, timeout=5)
        r3.raise_for_status()
        results['XBRL_REACHABLE'] = True
    except requests.exceptions.RequestException as e:
        results['ERRORS'].append(f"SEC XBRL companyfacts endpoint unreachable: {e}")
        
    return results



tab_setup, tab_portfolio, tab_dashboard, tab_research, tab_data_quality = st.tabs([
    "Setup & Preflight", "Portfolio Sync", "Attention Queue", "Research Mode", "Data Quality & Refresh"
])

with tab_setup:
    st.subheader("1. Company Selection")
    if public_demo:
        st.caption("🔒 Public Demo Mode: Monitored company selections are saved to your current browser session and will not alter the global watchlist.")
    selected_tickers = st.multiselect("Select Companies to Monitor:", options=[u["ticker"] for u in universe], default=active_tickers, format_func=lambda x: f"{x} - {universe_map[x].get('name', 'Unknown')} ({universe_map[x].get('sector', 'Unknown')})")
    if st.button("Save Monitored Companies"):
        if public_demo:
            st.session_state["monitored_tickers"] = selected_tickers
            st.success("Monitored companies saved for your session!")
        else:
            save_watchlist(db, [{"ticker": t, "cik": universe_map[t].get("cik", ""), "active": (t in selected_tickers)} for t in universe_map.keys()])
            st.success("Monitored companies saved!")
        time.sleep(1)
        st.rerun()

    st.subheader("2. SEC Preflight Configuration")
    if st.button("Test SEC Connectivity"):
        with st.spinner("Testing SEC endpoints..."):
            res = test_sec_connectivity(user_agent)
            st.json(res)
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
                    pg = load_peer_groups()
                    for t in active_tickers:
                        gid, peers = find_peer_group(t, pg)
                        for p in peers:
                            if p not in ingest_list:
                                ingest_list.append(p)
                                
                success_count = 0
                for i, ticker in enumerate(ingest_list):
                    if ticker not in universe_map: continue
                    try:
                        res_ingest = ingest_company(client, db, universe_map[ticker])
                        save_refresh_history(db, ticker, "SUCCESS", observations_count=res_ingest.get("observations", 0), signals_count=res_ingest.get("signals", 0), refresh_type="MONITORED_BATCH")
                        status_list.append({"Company": ticker, "Status": "SUCCESS", "Message": ""})
                        success_count += 1
                    except Exception as e:
                        logger.error("Ingestion failed for %s: %s", ticker, e, exc_info=True)
                        save_refresh_history(db, ticker, "FAILED", error_message=str(e), refresh_type="MONITORED_BATCH")
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
    if public_demo:
        st.info("🔒 **Public Demo Mode Active:** Uploaded portfolio holdings are scoped strictly to your current browser session. They are not stored in the shared database or visible to other visitors.")
    uploaded_file = st.file_uploader("Upload Portfolio Holdings (CSV)", type=["csv"])
    if uploaded_file is not None:
        try:
            df_port = pd.read_csv(uploaded_file)
            is_valid, err_msg = validate_portfolio_csv(df_port, [u["ticker"] for u in universe])
            if not is_valid: st.error(f"Validation failed: {err_msg}")
            else:
                if st.button("Apply Portfolio"):
                    if public_demo:
                        records = df_port.to_dict(orient="records")
                        st.session_state["session_portfolio"] = {r["ticker"]: r for r in records}
                        st.success(f"Portfolio saved to your session ({len(records)} positions).")
                    else:
                        save_portfolio(db, df_port.to_dict(orient="records"))
                        st.success("Portfolio saved.")
        except Exception as e:
            st.error(f"Failed to process CSV: {e}")

with tab_dashboard:
    st.subheader("Attention Queue")
    if not active_tickers:
        st.info("No active companies.")
    else:
        if public_demo:
            session_reviews = st.session_state.setdefault("session_reviews", {})
            all_reviews = {**get_all_analyst_reviews(db), **session_reviews}
        else:
            all_reviews = get_all_analyst_reviews(db)
        placeholders = ",".join("?" * len(active_tickers))
        signals = rows(db, f"SELECT s.*, p.weight, p.exposure FROM signals s LEFT JOIN portfolio p ON s.company = p.ticker WHERE s.company IN ({placeholders}) AND s.suppressed IS NULL ORDER BY CASE severity WHEN 'HIGH' THEN 1 WHEN 'MEDIUM' THEN 2 WHEN 'LOW' THEN 3 ELSE 4 END ASC", active_tickers)
        if signals:
            aq_filter = st.radio(
                "Filter Alerts by Review Status:",
                ["Active Alerts (New / Under Review / Acknowledged)", "All Alerts", "Resolved / Dismissed / Expected"],
                horizontal=True,
                key="aq_status_filter"
            )
            visible_count = 0
            for s in signals:
                fprint = generate_alert_fingerprint(s['company'], s['signal_id'], s.get('evidence'), s.get('version', 'v1'))
                rev = all_reviews.get(fprint)
                status_val = rev["status"] if rev else "NEW"
                note_val = rev["note"] if rev and rev["note"] else ""
                updated_val = rev["updated_at"] if rev else None
                
                if aq_filter.startswith("Active") and status_val in ("DISMISSED", "EXPECTED", "RESOLVED"):
                    continue
                if aq_filter.startswith("Resolved") and status_val not in ("DISMISSED", "EXPECTED", "RESOLVED"):
                    continue
                visible_count += 1
                
                if public_demo and "session_portfolio" in st.session_state:
                    sess_pos = st.session_state["session_portfolio"].get(s['company'])
                    if sess_pos and sess_pos.get("weight") is not None and sess_pos.get("exposure") is not None:
                        port_ctx_str = f"**Portfolio Context:** Weight: {float(sess_pos['weight'])*100:.2f}%, Exposure: {format_val(float(sess_pos['exposure']))}"
                    else:
                        port_ctx_str = "**Portfolio Context:** Not held"
                else:
                    port_ctx_str = f"**Portfolio Context:** Weight: {s['weight']*100:.2f}%, Exposure: {format_val(s['exposure'])}" if s.get("weight") is not None and s.get("exposure") is not None else "**Portfolio Context:** Not held"
                with st.expander(f"[{s['severity']}] {s['company']} - {s['signal_id']} (Confidence: {s['confidence']}) - [{status_val}]"):
                    st.markdown(f"{port_ctx_str} | **Explanation:** {s['explanation']}")
                    st.markdown(f"**Investigation:** Review {s['signal_id']} alongside latest 10-Q/10-K disclosures.")
                    
                    st.markdown(f"**Review Status:** `{status_val}`" + (f" *(Last saved: {updated_val[:19].replace('T', ' ')})*" if updated_val else ""))
                    if note_val:
                        st.info(f"**Analyst Note:** {note_val}")
                    
                    with st.form(key=f"review_form_{fprint}"):
                        st.markdown("##### Analyst Review Action")
                        if public_demo:
                            st.caption("🔒 Public Demo Mode: Review actions are session-scoped and private to you.")
                        c_stat, c_note = st.columns([1, 2])
                        stat_opts = ["NEW", "ACKNOWLEDGED", "UNDER_REVIEW", "DISMISSED", "EXPECTED", "RESOLVED"]
                        idx_stat = stat_opts.index(status_val) if status_val in stat_opts else 0
                        chosen_stat = c_stat.selectbox("Status", stat_opts, index=idx_stat, key=f"sel_stat_{fprint}")
                        new_note = c_note.text_input("Investigation Note", value=note_val, key=f"note_inp_{fprint}", placeholder="Add research thesis or dismissal rationale...")
                        if st.form_submit_button("Save Review"):
                            if public_demo:
                                now_iso = datetime.utcnow().isoformat()
                                st.session_state.setdefault("session_reviews", {})[fprint] = {
                                    "status": chosen_stat,
                                    "note": new_note,
                                    "updated_at": now_iso
                                }
                                st.success(f"Review updated for your session ({s['company']} - {s['signal_id']}).")
                            else:
                                save_analyst_review(db, fprint, s['company'], s['signal_id'], chosen_stat, new_note)
                                st.success(f"Review saved for {s['company']} - {s['signal_id']}.")
                            time.sleep(0.5)
                            st.rerun()
                        
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
                                unit_map = {
                                    "gross_margin": "pure", "operating_margin": "pure",
                                    "cash_conversion": "multiple", "debt_operating_income": "multiple", "liquidity_ratio": "multiple",
                                    "receivables_revenue_ratio": "pure", "inventory_revenue_ratio": "pure",
                                    "share_count": "shares", "free_cash_flow": ""
                                }
                                pm_unit = unit_map.get(mapped_metric, "")
                                if mapped_metric == "free_cash_flow" and s.get("evidence"):
                                    try:
                                        ev_json = json.loads(s["evidence"])
                                        if ev_json: pm_unit = ev_json[0].get("unit", "")
                                    except json.JSONDecodeError as e:
                                        logger.warning("Failed to decode evidence for %s: %s", s['company'], e)
                                        
                                pos = ctx.get("position", "Unknown")
                                cov = f"{ctx.get('coverage_count', ctx.get('n_peers'))}/{ctx.get('total_peer_count', ctx.get('n_peers'))}"
                                
                                st.markdown(f"- **Metric:** {mapped_metric.replace('_', ' ').title()}")
                                st.markdown(f"- **Company Value:** {format_val(ctx.get('company_value'), pm_unit)}")
                                st.markdown(f"- **Peer Median:** {format_val(ctx.get('peer_median'), pm_unit)}")
                                st.markdown(f"- **Position:** {pos.replace('_', ' ').title()}")
                                st.markdown(f"- **Coverage:** {cov} peers")
                            else:
                                st.markdown("Peer context unavailable")

                    st.markdown("### Evidence Summary")

                    if s["evidence"]:
                        try:
                            ev_data = json.loads(s["evidence"])
                            if s["signal_id"] == "MULTI_FACTOR_DETERIORATION_CLUSTER":
                                comp_ids = s.get("component_signal_ids")
                                if comp_ids:
                                    if isinstance(comp_ids, str):
                                        try: comp_ids = json.loads(comp_ids)
                                        except Exception: pass
                                    if isinstance(comp_ids, (list, tuple)):
                                        st.markdown(f"**Component Signals ({len(comp_ids)} concurrent):** " + ", ".join(f"`{c.replace('_', ' ').title()}`" for c in comp_ids))

                                grouped = group_cluster_evidence_by_metric(ev_data)
                                for metric_name, m_info in grouped.items():
                                    st.markdown(f"#### Metric: {metric_name.replace('_', ' ').title()}")
                                    curr_o = m_info.get("current")
                                    prior_o = m_info.get("prior")
                                    if curr_o and prior_o:
                                        col_c, col_p = st.columns(2)
                                        with col_c:
                                            st.markdown("##### Current Observation")
                                            st.markdown(f"- **Value:** {format_val(curr_o.get('value'), curr_o.get('unit'))} | **Unit:** {curr_o.get('unit')}")
                                            st.markdown(f"- **Period:** {curr_o.get('period_end')} ({curr_o.get('period_type')}) | **Fiscal:** FY{curr_o.get('fiscal_year', 'N/A')} {curr_o.get('fiscal_period', 'N/A')}")
                                            st.markdown(f"- **Quality:** {curr_o.get('quality')}")
                                        with col_p:
                                            st.markdown("##### Prior Observation")
                                            st.markdown(f"- **Value:** {format_val(prior_o.get('value'), prior_o.get('unit'))} | **Unit:** {prior_o.get('unit')}")
                                            st.markdown(f"- **Period:** {prior_o.get('period_end')} ({prior_o.get('period_type')}) | **Fiscal:** FY{prior_o.get('fiscal_year', 'N/A')} {prior_o.get('fiscal_period', 'N/A')}")
                                            st.markdown(f"- **Quality:** {prior_o.get('quality')}")
                                    elif curr_o:
                                        st.markdown("##### Current Observation")
                                        st.markdown(f"- **Value:** {format_val(curr_o.get('value'), curr_o.get('unit'))} | **Unit:** {curr_o.get('unit')}")
                                        st.markdown(f"- **Period:** {curr_o.get('period_end')} ({curr_o.get('period_type')}) | **Fiscal:** FY{curr_o.get('fiscal_year', 'N/A')} {curr_o.get('fiscal_period', 'N/A')}")
                                        st.markdown(f"- **Quality:** {curr_o.get('quality')}")

                                    for obs in m_info.get("observations", []):
                                        provs = obs.get("provenance", [])
                                        if provs:
                                            st.markdown(f"**SEC Sources ({obs.get('period_end', '')}):**")
                                            for p in provs:
                                                acc = p.get("accession", "N/A")
                                                form = p.get("form", "N/A")
                                                fdate = p.get("filing_date", "N/A")
                                                concept = p.get("concept", "N/A")
                                                url = p.get("source_url", "")
                                                st.markdown(f"- **Form:** {form} | **Filed:** {fdate} | **Accession:** {acc} | **Concept:** {concept}")
                                                if url and url != "#":
                                                    st.markdown(f"  [Open SEC Filing]({url})")
                            else:
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
            if visible_count == 0:
                st.info("No signals matching the selected review status filter.")
        else:
            st.success("No actionable deterioration signals detected.")

with tab_research:
    universe_tickers = [u["ticker"] for u in universe]
    all_obs_comps = {r["company"] for r in rows(db, "SELECT DISTINCT company FROM observations")}
    default_ticker_idx = 0
    if active_tickers:
        for at in active_tickers:
            if at in universe_tickers:
                default_ticker_idx = universe_tickers.index(at)
                break
    elif all_obs_comps:
        for oc in all_obs_comps:
            if oc in universe_tickers:
                default_ticker_idx = universe_tickers.index(oc)
                break

    ticker = st.selectbox(
        "Select Company for Research",
        options=universe_tickers,
        index=default_ticker_idx,
        key="res_company_select"
    )
    company_meta = universe_map.get(ticker, {"ticker": ticker, "cik": ""})
    st.header(f"{ticker} - {company_meta.get('name', 'Unknown')} ({company_meta.get('sector', 'Unknown')})")
    
    obs_count = rows(db, "SELECT count(*) as c FROM observations WHERE company=?", (ticker,))[0]["c"]
    
    if obs_count == 0:
        st.info(f"NOT-YET-LOADED: No historical SEC disclosure data is currently loaded for {ticker} ({company_meta.get('name', 'Unknown')}).")
        st.markdown("This company is part of the supported universe. You can retrieve its disclosures on demand using the action below.")
        if not user_agent:
            st.warning("Cannot fetch data: SEC_USER_AGENT is not configured. Configure SEC_USER_AGENT to enable on-demand SEC ingestion.")
        else:
            if st.button(f"Fetch SEC Disclosure Data for {ticker}", key=f"fetch_single_{ticker}"):
                with st.spinner(f"Ingesting SEC filings and company facts for {ticker}..."):
                    try:
                        client = SECClient(user_agent)
                        res_ing = ingest_company(client, db, company_meta)
                        refresh_peer_contexts(db, [ticker])
                        save_refresh_history(db, ticker, "SUCCESS", observations_count=res_ing.get("observations", 0), signals_count=res_ing.get("signals", 0), refresh_type="SINGLE_RESEARCH")
                        st.success(f"Successfully ingested {res_ing.get('observations', 0)} observations for {ticker}!")
                        time.sleep(1)
                        st.rerun()
                    except Exception as e:
                        logger.error("Single-company fetch failed for %s: %s", ticker, e, exc_info=True)
                        save_refresh_history(db, ticker, "FAILED", error_message=str(e), refresh_type="SINGLE_RESEARCH")
                        st.error(f"Failed to fetch SEC data for {ticker}: {e}")
    else:
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
            rev_unit = next((o['unit'] for o in all_q_obs if o['metric'] == 'revenue' and o['period_end'] == (ref_row['period_end'] if ref_row else '')), "")
            ni_unit = next((o['unit'] for o in all_q_obs if o['metric'] == 'net_income' and o['period_end'] == (ref_row['period_end'] if ref_row else '')), "")
            
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
                            if s["signal_id"] == "MULTI_FACTOR_DETERIORATION_CLUSTER":
                                comp_ids = s.get("component_signal_ids")
                                if comp_ids:
                                    if isinstance(comp_ids, str):
                                        try: comp_ids = json.loads(comp_ids)
                                        except Exception: pass
                                    if isinstance(comp_ids, (list, tuple)):
                                        st.markdown(f"**Component Signals ({len(comp_ids)} concurrent):** " + ", ".join(f"`{c.replace('_', ' ').title()}`" for c in comp_ids))

                                grouped = group_cluster_evidence_by_metric(ev_json)
                                for metric_name, m_info in grouped.items():
                                    st.markdown(f"#### Metric: {metric_name.replace('_', ' ').title()}")
                                    curr_o = m_info.get("current")
                                    prior_o = m_info.get("prior")
                                    if curr_o and prior_o:
                                        col_c, col_p = st.columns(2)
                                        with col_c:
                                            st.markdown("##### Current Observation")
                                            st.markdown(f"- **Value:** {format_val(curr_o.get('value'), curr_o.get('unit'))} | **Unit:** {curr_o.get('unit')}")
                                            st.markdown(f"- **Period:** {curr_o.get('period_end')} ({curr_o.get('period_type')}) | **Fiscal:** FY{curr_o.get('fiscal_year', 'N/A')} {curr_o.get('fiscal_period', 'N/A')}")
                                            st.markdown(f"- **Quality:** {curr_o.get('quality')}")
                                        with col_p:
                                            st.markdown("##### Prior Observation")
                                            st.markdown(f"- **Value:** {format_val(prior_o.get('value'), prior_o.get('unit'))} | **Unit:** {prior_o.get('unit')}")
                                            st.markdown(f"- **Period:** {prior_o.get('period_end')} ({prior_o.get('period_type')}) | **Fiscal:** FY{prior_o.get('fiscal_year', 'N/A')} {prior_o.get('fiscal_period', 'N/A')}")
                                            st.markdown(f"- **Quality:** {prior_o.get('quality')}")
                                    elif curr_o:
                                        st.markdown("##### Current Observation")
                                        st.markdown(f"- **Value:** {format_val(curr_o.get('value'), curr_o.get('unit'))} | **Unit:** {curr_o.get('unit')}")
                                        st.markdown(f"- **Period:** {curr_o.get('period_end')} ({curr_o.get('period_type')}) | **Fiscal:** FY{curr_o.get('fiscal_year', 'N/A')} {curr_o.get('fiscal_period', 'N/A')}")
                                        st.markdown(f"- **Quality:** {curr_o.get('quality')}")

                                    for obs in m_info.get("observations", []):
                                        provs = obs.get("provenance", [])
                                        if provs:
                                            st.markdown(f"**SOURCE ({obs.get('metric')} - {obs.get('period_end', '')}):**")
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
                            else:
                                if len(ev_json) >= 2:
                                    curr, prior = resolve_evidence_pair(ev_json)
                                    if curr and prior:
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

with tab_data_quality:
    st.subheader("Data Quality & Refresh Monitoring")
    
    # 1. High-level metric summary
    all_companies_with_obs = sorted(list({r["company"] for r in rows(db, "SELECT DISTINCT company FROM observations")}))
    total_obs = rows(db, "SELECT count(*) as c FROM observations")[0]["c"]
    total_signals = rows(db, "SELECT count(*) as c FROM signals")[0]["c"]
    latest_refresh = get_latest_refresh_time(db)
    
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Supported Universe", len(universe))
    col2.metric("Active Monitored", len(active_tickers))
    col3.metric("Companies with Data", len(all_companies_with_obs))
    col4.metric("Total Observations", f"{total_obs:,}")
    col5.metric("Latest Refresh", latest_refresh[:19].replace("T", " ") if latest_refresh else "Never")
    
    # 2. Data Readiness Breakdown
    st.markdown("### 1. Monitored & Researched Companies Readiness")
    target_readiness_tickers = sorted(list(set(active_tickers + all_companies_with_obs)))
    if not target_readiness_tickers:
        st.info("No companies currently monitored or loaded.")
    else:
        readiness_records = []
        state_counts = {"READY": 0, "PARTIAL": 0, "NOT_READY": 0, "FAILED": 0}
        for t in target_readiness_tickers:
            r_state, r_msg = calculate_data_readiness(t, db)
            st_str = r_state.value if hasattr(r_state, "value") else str(r_state)
            state_counts[st_str] = state_counts.get(st_str, 0) + 1
            readiness_records.append({
                "Company": t,
                "Name": universe_map.get(t, {}).get("name", "Unknown"),
                "Sector": universe_map.get(t, {}).get("sector", "Unknown"),
                "State": st_str,
                "Details": r_msg,
                "Monitored": "Yes" if t in active_tickers else "No"
            })
            
        r_col1, r_col2, r_col3, r_col4 = st.columns(4)
        r_col1.metric("Ready", state_counts.get("READY", 0))
        r_col2.metric("Partial", state_counts.get("PARTIAL", 0))
        r_col3.metric("Not Ready", state_counts.get("NOT_READY", 0))
        r_col4.metric("Failed", state_counts.get("FAILED", 0))
        
        st.dataframe(pd.DataFrame(readiness_records), use_container_width=True, hide_index=True)
        
    # 3. Refresh Audit History
    st.markdown("### 2. Persisted Refresh History")
    ref_history = get_refresh_history(db, limit=50)
    if not ref_history:
        st.info("No data refreshes have been recorded yet.")
    else:
        df_ref = pd.DataFrame(ref_history)[["id", "timestamp", "ticker", "status", "observations_count", "signals_count", "refresh_type", "error_message"]]
        st.dataframe(df_ref, use_container_width=True, hide_index=True)
        
    # 4. Core Metrics & Fiscal Comparison Diagnostics
    st.markdown("### 3. Core Financial Metrics Diagnostic")
    core_metrics = ["revenue", "gross_margin", "operating_income", "net_income", "operating_cash_flow", "free_cash_flow"]
    if all_companies_with_obs:
        diag_rows = []
        for t in all_companies_with_obs:
            sector = universe_map.get(t, {}).get("sector", "Unknown")
            obs_t = rows(db, "SELECT DISTINCT metric FROM observations WHERE company=? AND period_type='QUARTER'", (t,))
            present_m = {r["metric"] for r in obs_t}
            missing_m = [m for m in core_metrics if m not in present_m]
            
            supps = rows(db, "SELECT signal_id, suppressed FROM signals WHERE company=? AND suppressed IS NOT NULL", (t,))
            supp_info = "; ".join([f"{s['signal_id']}: {s['suppressed']}" for s in supps]) if supps else "None"
            
            diag_rows.append({
                "Company": t,
                "Sector": sector,
                "Quarterly Metrics Present": len(present_m),
                "Missing Core Metrics": ", ".join(missing_m) if missing_m else "All Core Present",
                "Comparison Suppressions": supp_info
            })
        st.dataframe(pd.DataFrame(diag_rows), use_container_width=True, hide_index=True)
    else:
        st.info("No financial observations present in database.")
        
    # 5. Peer Coverage & Unavailability
    st.markdown("### 4. Peer Coverage Integrity")
    peer_rows = rows(db, "SELECT company, metric, n_peers, coverage_count, total_peer_count, availability_state, unavailable_peers FROM peer_context ORDER BY company, metric")
    if peer_rows:
        st.dataframe(pd.DataFrame(peer_rows), use_container_width=True, hide_index=True)
    else:
        st.info("No peer context records computed yet.")
        
    # 5. Regulatory Freshness & Integrity Guidelines
    st.markdown("### 5. Regulatory Freshness & Integrity Guidelines")
    st.markdown("""
    - **10-Q Quarterly Filing Window**: Mandated by the SEC within 40 calendar days (Large Accelerated Filer) or 45 days (Non-accelerated) following fiscal quarter end.
    - **10-K Annual Filing Window**: Mandated within 60 calendar days (Large Accelerated Filer), 75 days (Accelerated), or 90 days following fiscal year end.
    - **Freshness Guidance (Documented Standard)**: Regulatory expectation is that disclosures older than 180 calendar days without a subsequent quarterly update represent aging disclosures (documented analyst guidance; automated stale-tag engine is currently out-of-scope).
    - **Zero Missing Data Protection**: In accordance with system durability invariants, missing line items or XBRL tags are **never** coerced to zero or interpolated.
    - **Fiscal Semantic Precedence**: Year-over-Year (YoY) and sequential comparisons strictly enforce matching fiscal durations (`QUARTER` to `QUARTER`, `ANNUAL` to `ANNUAL`). YTD durations (`YTD_6M`, `YTD_9M`) are never compared directly against standalone quarters.
    """)
