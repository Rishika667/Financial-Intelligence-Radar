import os
import json
import streamlit as st
import pandas as pd
import plotly.express as px

from financial_radar.store import connect, rows, save_watchlist
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

# Ensure we have active watchlist tracker
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
    if abs(val) >= 1e9:
        return f"${val/1e9:.1f}B"
    elif abs(val) >= 1e6:
        return f"${val/1e6:.1f}M"
    return f"${val:,.0f}"

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
                    if "ticker" not in df_port.columns:
                        st.error("CSV must contain 'ticker' column.")
                    elif not df_port["ticker"].isin([x["ticker"] for x in universe]).all():
                        st.error("Some tickers are not in the 50-company representative universe.")
                    elif df_port["ticker"].duplicated().any():
                        st.error("Duplicate tickers found in CSV.")
                    else:
                        st.dataframe(df_port, use_container_width=True, hide_index=True)
                        if st.button("Apply Portfolio"):
                            # Simple update of watchlist to active ones
                            selected = df_port["ticker"].tolist()
                            save_watchlist(db, [{**x, "active": x["ticker"] in selected} for x in universe])
                            st.success("Portfolio applied to active watchlist.")
                            st.rerun()
                except Exception as e:
                    st.error(f"Error parsing CSV: {e}")

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
        # Ensure HIGH > MODERATE > LOW via CASE statement
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
        st.subheader(f"🔍 {ticker} — {company_meta.get('title', 'Unknown')} ({company_meta.get('sector', 'Unknown')})")
        
        obs = rows(db, "SELECT * FROM observations WHERE company=? ORDER BY period_end DESC", (ticker,))
        if obs:
            df_obs = pd.DataFrame(obs)
            
            # Latest Valid Financial Period
            valid_qualities = ["REPORTED", "DERIVED", "AMENDED"]
            # Exclude enum prefixes if present
            valid_obs = df_obs[df_obs["quality"].astype(str).apply(lambda x: x.split(".")[-1] in valid_qualities)]
            
            if not valid_obs.empty:
                latest_period = valid_obs["period_end"].max()
            else:
                latest_period = df_obs["period_end"].max()
            
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
                metric_sel = st.multiselect("Select Metrics", hist_df["metric"].unique().tolist(), default=["revenue", "gross_profit", "operating_income"])
                filtered_hist = hist_df[hist_df["metric"].isin(metric_sel)]
                if not filtered_hist.empty:
                    fig = px.line(filtered_hist, x="period_end", y="value", color="metric", title="Financial Trajectory (Quarterly)")
                    st.plotly_chart(fig, use_container_width=True)
                
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
                            
                        # Evidence Drill-down
                        st.write("**Evidence Trail:**")
                        try:
                            ev_json = json.loads(ev_str)
                            if isinstance(ev_json, list) and ev_json:
                                ev_df = pd.DataFrame(ev_json)
                                st.dataframe(ev_df, use_container_width=True, hide_index=True)
                            else:
                                st.caption("No tabular evidence provided.")
                        except Exception:
                            st.caption("Could not parse evidence JSON.")
            else:
                st.success("No critical deterioration signals detected.")
                
            st.markdown("### Peer Context")
            company_peers = rows(db, "SELECT metric, company_value, peer_median, peer_min, peer_max, n_peers, group_id FROM peer_context WHERE company=?", (ticker,))
            if company_peers:
                st.dataframe(pd.DataFrame(company_peers), use_container_width=True, hide_index=True)
            else:
                # Need to determine why it's missing
                # If they are in universe but no peers have been ingested
                st.info("Peer context unavailable — peer financial observations have not been refreshed or insufficient peers exist.")
                
            st.markdown("### Corporate Events")
            events = rows(db, "SELECT type, filed, description, source_url, accession, form FROM events WHERE company=? ORDER BY filed DESC LIMIT 10", (ticker,))
            if events:
                for e in events:
                    # Removed Completed heuristic, label explicitly
                    st.write(f"**{e['filed']} - {e['type'].upper()}**")
                    st.write(f"*{e['description']}*")
                    st.caption(f"Form: {e.get('form', 'Unknown')} | Accession: {e.get('accession', 'Unknown')} | [SEC Source]({e.get('source_url', '#')})")
                    st.divider()
            else:
                st.info("No recent 8-K material events extracted.")
        else:
            st.info("No data available. Refresh the company in the Portfolio tab.")
