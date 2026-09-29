import os
import json
import streamlit as st
import pandas as pd
import plotly.express as px

from financial_radar.store import connect, rows, save_watchlist, save_portfolio
from financial_radar.pipeline import load_universe, ingest_company
from financial_radar.core import SECClient
from financial_radar.intelligence import generate_intelligence

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(page_title="Financial Intelligence Radar", layout="wide")
st.title("Financial Intelligence Radar")
st.caption("Public-disclosure intelligence for analyst attention — not investment advice.")

# ---------------------------------------------------------------------------
# Persistent state
# ---------------------------------------------------------------------------
db = connect()
try:
    universe = load_universe()
except FileNotFoundError:
    st.error("config/universe.json not found. Cannot load company universe.")
    st.stop()

existing = {r["ticker"] for r in rows(db, "SELECT ticker FROM watchlist WHERE active=1")}
if not existing:
    save_watchlist(db, universe)
    existing = {x["ticker"] for x in universe}

sector_map = {x["ticker"]: x.get("sector", "Other") for x in universe}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _format_value(val):
    if val is None:
        return "N/A"
    if val == 0:
        return "$0"
    if abs(val) >= 1e9:
        return f"${val/1e9:.1f}B"
    elif abs(val) >= 1e6:
        return f"${val/1e6:.1f}M"
    return f"${val:,.0f}"

def validate_portfolio_csv(df_port, universe_tickers):
    if "ticker" not in df_port.columns:
        return False, "CSV must contain 'ticker' column."
    if not df_port["ticker"].isin(universe_tickers).all():
        return False, "Some tickers are not in the 50-company representative universe."
    if df_port["ticker"].duplicated().any():
        return False, "Duplicate tickers found in CSV."
        
    for col in ["shares", "weight", "cost_basis"]:
        if col in df_port.columns:
            df_port[col] = pd.to_numeric(df_port[col], errors='coerce')
            if df_port[col].isna().any():
                return False, f"Column '{col}' must contain valid numeric values."
            if col in ["shares", "cost_basis"] and (df_port[col] < 0).any():
                return False, f"Column '{col}' cannot contain negative values."
            if col == "weight" and ((df_port[col] < 0).any() or (df_port[col] > 1).any()):
                return False, "Column 'weight' must be between 0 and 1 (decimal format)."
    return True, ""


# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------
tab_portfolio, tab_dashboard, tab_research = st.tabs([
    "Portfolio Intelligence", "Attention Queue", "Research Mode"
])

active_tickers = sorted({r["ticker"] for r in rows(db, "SELECT ticker FROM watchlist WHERE active=1")})

with tab_portfolio:
    st.subheader("Manage Universe & Holdings")
    
    col_w, col_p = st.columns(2)
    with col_w:
        with st.expander("Watchlist Management", expanded=True):
            selected = st.multiselect(
                "Monitored companies",
                [x["ticker"] for x in universe],
                default=active_tickers,
            )
            if st.button("Save Watchlist"):
                save_watchlist(db, [{**x, "active": x["ticker"] in selected} for x in universe])
                st.success("Watchlist saved locally.")
                st.rerun()
                
    with col_p:
        with st.expander("Import Portfolio Holdings (CSV)", expanded=True):
            st.caption("Portfolio exposure is based on imported portfolio fields; live market-value exposure is not available.")
            uploaded_file = st.file_uploader("Upload CSV (Required: ticker. Optional: shares, weight, cost_basis)", type="csv")
            if uploaded_file is not None:
                try:
                    df_port = pd.read_csv(uploaded_file)
                    valid, err_msg = validate_portfolio_csv(df_port, [x["ticker"] for x in universe])
                    if not valid:
                        st.error(err_msg)
                    else:
                        st.dataframe(df_port, use_container_width=True, hide_index=True)
                        if st.button("Apply Portfolio"):
                            selected = df_port["ticker"].tolist()
                            save_watchlist(db, [{**x, "active": x["ticker"] in selected} for x in universe])
                            
                            # Actual portfolio persistence
                            records = df_port.to_dict(orient="records")
                            save_portfolio(db, records)
                            st.success("Portfolio persisted and applied to active watchlist.")
                            st.rerun()
                except Exception as e:
                    st.error(f"Error parsing CSV: {e}")
                    
        # Clean portfolio summary
        port_rows = rows(db, "SELECT * FROM portfolio")
        if port_rows:
            st.markdown("### Portfolio Summary")
            df_curr_port = pd.DataFrame(port_rows)
            st.dataframe(df_curr_port, use_container_width=True, hide_index=True)

    with st.expander("Refresh SEC Data", expanded=False):
        contact = st.text_input("SEC User-Agent contact email", value=os.getenv("SEC_USER_AGENT", ""), help="Required by SEC policy.")
        if st.button("Refresh Active Companies"):
            if not active_tickers:
                st.warning("Select at least one company in the watchlist.")
            elif not contact or "@" not in contact:
                st.warning("Provide a valid contact email for SEC User-Agent.")
            else:
                os.environ["SEC_USER_AGENT"] = f"Financial Intelligence Radar {contact}"
                try:
                    client = SECClient(os.environ["SEC_USER_AGENT"])
                    progress = st.progress(0)
                    successes = 0
                    failures = 0
                    
                    for i, ticker in enumerate(active_tickers):
                        company_meta = next((c for c in universe if c["ticker"] == ticker), {"ticker": ticker, "cik": "0000000000"})
                        with st.status(f"Refreshing {ticker}...", expanded=False) as status:
                            try:
                                res = ingest_company(client, db, company_meta)
                                st.write(f"✓ {res['observations']} observations, {res['signals']} signals")
                                status.update(label=f"✓ {ticker} refreshed", state="complete")
                                successes += 1
                            except Exception as e:
                                st.write(f"❌ Failed: {e}")
                                status.update(label=f"❌ {ticker} failed", state="error")
                                failures += 1
                        progress.progress((i + 1) / len(active_tickers))
                    
                    with st.status("Computing Peer Contexts...", expanded=True) as status:
                        from financial_radar.pipeline import refresh_peer_contexts
                        try:
                            refresh_peer_contexts(db, active_tickers)
                            status.update(label="✓ Peer contexts computed", state="complete")
                        except Exception as e:
                            st.write(f"❌ Peer calculation failed: {e}")
                            status.update(label="❌ Peer calculation failed", state="error")
                    
                    if failures == 0:
                        st.success(f"Refresh successful for {successes} companies.")
                    else:
                        st.warning(f"Refresh partial: {successes} succeeded, {failures} failed.")
                except Exception as exc:
                    st.error(f"Refresh aborted: {exc}")

with tab_dashboard:
    st.subheader("Attention Queue")
    if not active_tickers:
        st.info("No active companies. Add to watchlist or portfolio.")
    else:
        placeholders = ",".join("?" * len(active_tickers))
        signals = rows(
            db,
            f"SELECT * FROM signals WHERE company IN ({placeholders}) AND suppressed IS NULL ORDER BY CASE severity WHEN 'HIGH' THEN 1 WHEN 'MODERATE' THEN 2 WHEN 'LOW' THEN 3 ELSE 4 END ASC",
            active_tickers,
        )
        
        if signals:
            queue_data = []
            for s in signals:
                comp = next((x for x in universe if x["ticker"] == s["company"]), {})
                sector = comp.get("sector", "Unknown")
                intel = generate_intelligence(s["signal_id"], s["company"], sector, s.get("evidence", ""))
                
                queue_data.append({
                    "Company": s["company"],
                    "Priority": s["severity"],
                    "Signal": intel["title"],
                    "What Changed": intel["what_changed"],
                    "Confidence": s["confidence"]
                })
            
            df_queue = pd.DataFrame(queue_data)
            st.dataframe(df_queue, use_container_width=True, hide_index=True)
            
            st.markdown("### Portfolio Attention Summary")
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Active Holdings", len(active_tickers))
            col2.metric("Total Signals", len(signals))
            col3.metric("High Priority", len([s for s in signals if s["severity"] == "HIGH"]))
            col4.metric("Companies with Signals", len(set(s["company"] for s in signals)))
        else:
            st.info("No actionable signals in the queue. All clear.")

with tab_research:
    ticker = st.selectbox("Select Company for Research", active_tickers if active_tickers else [x["ticker"] for x in universe])
    
    if ticker:
        company_meta = next((x for x in universe if x["ticker"] == ticker), None)
        st.subheader(f"🔎 {ticker} — {company_meta.get('title', 'Unknown')} ({company_meta.get('sector', 'Unknown')})")
        
        obs = rows(db, "SELECT * FROM observations WHERE company=? ORDER BY period_end DESC", (ticker,))
        if obs:
            df_obs = pd.DataFrame(obs)
            
            # Latest Valid Financial Period logic
            valid_qualities = ["REPORTED", "DERIVED", "AMENDED"]
            valid_obs = df_obs[df_obs["quality"].astype(str).apply(lambda x: str(x).split(".")[-1] in valid_qualities)]
            
            if not valid_obs.empty:
                latest_period = valid_obs["period_end"].max()
                st.caption(f"**Latest Valid Financial Period:** {latest_period}")
                
                st.markdown("### Executive Snapshot")
                latest = df_obs[df_obs["period_end"] == latest_period]
                metrics = ["revenue", "gross_profit", "operating_income", "operating_cash_flow"]
                cols = st.columns(len(metrics))
                for i, m in enumerate(metrics):
                    row = latest[latest["metric"] == m]
                    val = row.iloc[0]["value"] if not row.empty else None
                    cols[i].metric(m.replace("_", " ").title(), _format_value(val))
                        
                st.markdown("### Historical Trends")
                hist_df = df_obs[df_obs["period_type"] == "QUARTER"]
                if not hist_df.empty:
                    metric_sel = st.selectbox("Select Metric", hist_df["metric"].unique().tolist())
                    filtered_hist = hist_df[hist_df["metric"] == metric_sel]
                    if not filtered_hist.empty:
                        fig = px.line(filtered_hist, x="period_end", y="value", title=f"{metric_sel.replace('_', ' ').title()} (Quarterly)")
                        st.plotly_chart(fig, use_container_width=True)
            else:
                st.error("No valid financial period available.")
                
            st.markdown("### What Changed? & Investigation")
            company_signals = rows(db, "SELECT * FROM signals WHERE company=? AND suppressed IS NULL ORDER BY CASE severity WHEN 'HIGH' THEN 1 WHEN 'MODERATE' THEN 2 WHEN 'LOW' THEN 3 ELSE 4 END ASC", (ticker,))
            if company_signals:
                for s in company_signals:
                    ev_str = s.get("evidence", "")
                    intel = generate_intelligence(s["signal_id"], ticker, company_meta.get("sector"), ev_str)
                    
                    with st.expander(f"🚨 {intel['title']} (Priority: {s['severity']})", expanded=True):
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
                                    # True Analyst Evidence Drill-Down
                                    prov = ev_item.get("provenance", [])
                                    
                                    cols_ev = st.columns([1, 1])
                                    with cols_ev[0]:
                                        st.caption("OBSERVATION")
                                        st.write(f"**Metric:** {ev_item.get('metric', 'N/A')}")
                                        val = ev_item.get('value')
                                        st.write(f"**Value:** {'$0' if val == 0 else val}")
                                        st.write(f"**Unit:** {ev_item.get('unit', 'N/A')}")
                                        st.write(f"**Period End:** {ev_item.get('period_end', 'N/A')}")
                                        st.write(f"**Period Type:** {ev_item.get('period_type', 'N/A')}")
                                        st.write(f"**Quality:** {ev_item.get('quality', 'N/A')}")
                                        st.write(f"**Comparable:** {ev_item.get('comparable', 'N/A')}")
                                        st.write(f"**Derived From:** {ev_item.get('derived_from', 'N/A')}")
                                    
                                    with cols_ev[1]:
                                        st.caption("PROVENANCE (SOURCE)")
                                        if prov and len(prov) > 0:
                                            p = prov[0]
                                            st.write(f"**XBRL Concept:** {p.get('xbrl_concept', 'N/A')}")
                                            st.write(f"**Accession:** {p.get('accession', 'N/A')}")
                                            st.write(f"**Form:** {p.get('form', 'N/A')}")
                                            st.write(f"**Filing Date:** {p.get('filing_date', 'N/A')}")
                                            st.write(f"**Raw Value:** {p.get('raw_value', 'N/A')}")
                                            st.write(f"**Mapping Version:** {p.get('mapping_version', 'N/A')}")
                                            url = p.get('source_url', '#')
                                            st.markdown(f"**[SEC URL]({url})**")
                                        else:
                                            st.write("No direct provenance available (e.g., derived metric).")
                                    st.divider()
                            else:
                                st.caption("No evidence objects provided.")
                        except Exception as e:
                            st.caption(f"Could not parse evidence: {e}")
            else:
                st.success("No critical deterioration signals detected.")
                
            st.markdown("### Peer Context")
            company_peers = rows(db, "SELECT metric, company_value, peer_median, peer_min, peer_max, n_peers, group_id FROM peer_context WHERE company=?", (ticker,))
            if company_peers:
                n_peers = company_peers[0]["n_peers"] if company_peers else 0
                if n_peers < 2:
                    st.info(f"Peer group exists ({company_peers[0]['group_id']}), but fewer than 2 comparable peer observations exist.")
                else:
                    st.write(f"**Peer group:** {company_peers[0]['group_id']} | **Peer count:** {n_peers}")
                    st.dataframe(pd.DataFrame(company_peers)[['metric', 'company_value', 'peer_median', 'peer_min', 'peer_max']], use_container_width=True, hide_index=True)
            else:
                # Need to determine if they even have a peer group
                group = company_meta.get('sector')
                if not group:
                    st.info("No qualifying peer group exists for this company.")
                else:
                    st.info(f"Peer group exists ({group}) but peer observations are unavailable.")
                
            st.markdown("### Corporate Events")
            events = rows(db, "SELECT type, filed, description, source_url, accession, form FROM events WHERE company=? ORDER BY filed DESC LIMIT 10", (ticker,))
            if events:
                for e in events:
                    # Removed Completed heuristic, label explicitly
                    st.write(f"**{e['filed']} - {e['type'].upper()}**")
                    st.write(f"*{e['description']}* (Heuristic extraction)")
                    st.caption(f"Form: {e.get('form', 'Unknown')} | Accession: {e.get('accession', 'Unknown')} | [SEC Source]({e.get('source_url', '#')})")
                    st.divider()
            else:
                st.info("No recent material events extracted.")
        else:
            st.info("No data available. Refresh the company in the Portfolio tab.")