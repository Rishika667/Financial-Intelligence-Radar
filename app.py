import os
import json
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import io

from financial_radar.store import connect, rows, save_watchlist, save_portfolio, load_portfolio
from financial_radar.pipeline import ingest_company
from financial_radar.core import SECClient
from financial_radar.intelligence import generate_intelligence

st.set_page_config(page_title="Financial Intelligence Radar", layout="wide")
st.title("Financial Intelligence Radar")
st.caption("Public-disclosure intelligence for analyst attention — not investment advice.")

@st.cache_resource
def get_db():
    return connect()

db = get_db()

try:
    with open("config/universe.json", "r", encoding="utf-8") as f:
        universe_data = json.load(f)
        universe = universe_data.get("companies", [])
except FileNotFoundError:
    st.error("config/universe.json not found. Cannot load company universe.")
    st.stop()

existing_watchlist = {r["ticker"] for r in rows(db, "SELECT ticker FROM watchlist WHERE active=1")}
try:
    portfolio_rows = load_portfolio(db)
    portfolio_tickers = {r["ticker"] for r in portfolio_rows}
except Exception:
    portfolio_rows = []
    portfolio_tickers = set()

active_tickers = sorted(existing_watchlist.union(portfolio_tickers))

tab_portfolio, tab_dashboard, tab_research = st.tabs(["Portfolio & Watchlist", "Attention Queue", "Research Mode"])

with tab_portfolio:
    st.subheader("Manage Universe & Holdings")
    
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("### Watchlist")
        selected = st.multiselect(
            "Monitored companies",
            [x["ticker"] for x in universe],
            default=sorted(existing_watchlist),
        )
        if st.button("Save Watchlist"):
            save_watchlist(
                db,
                [{**x, "active": x["ticker"] in selected} for x in universe],
            )
            st.success("Watchlist updated.")
            st.rerun()

    with col2:
        st.markdown("### Portfolio Import")
        st.caption("Upload CSV with columns: ticker, shares, weight, cost_basis")
        uploaded_file = st.file_uploader("Choose a CSV file", type="csv")
        if uploaded_file is not None:
            try:
                df = pd.read_csv(uploaded_file)
                df.columns = [c.lower() for c in df.columns]
                if "ticker" in df.columns:
                    save_portfolio(db, df.to_dict("records"))
                    st.success("Portfolio imported successfully.")
                    st.rerun()
                else:
                    st.error("CSV must contain a 'ticker' column.")
            except Exception as e:
                st.error(f"Error parsing CSV: {e}")
                
    st.divider()
    st.markdown("### Data Refresh")
    contact = st.text_input("SEC User-Agent contact email", value=os.getenv("SEC_USER_AGENT", ""))
    if st.button("Refresh Active Companies (Watchlist + Portfolio)"):
        if not active_tickers:
            st.warning("No companies active.")
        elif not contact or "@" not in contact:
            st.warning("Provide a valid contact email for SEC User-Agent.")
        else:
            try:
                client = SECClient(f"Financial Intelligence Radar {contact}")
                progress = st.progress(0)
                
                successes, failures = 0, 0
                for i, ticker in enumerate(active_tickers):
                    company_meta = next((c for c in universe if c["ticker"] == ticker), {"ticker": ticker, "cik": "0000000000"})
                    with st.status(f"Refreshing {ticker}...", expanded=False) as status:
                        try:
                            res = ingest_company(client, db, company_meta)
                            st.write(f"✅ {res['observations']} observations, {res['signals']} signals")
                            status.update(label=f"✅ {ticker} refreshed", state="complete")
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
                        status.update(label="✅ Peer contexts computed", state="complete")
                    except ImportError:
                        st.write("refresh_peer_contexts not fully implemented yet in pipeline, skipping.")
                        status.update(label="⚠️ Peer context batch skip", state="complete")
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
            f"SELECT * FROM signals WHERE company IN ({placeholders}) AND suppressed IS NULL ORDER BY severity DESC",
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
            
            st.markdown("### Visual Insights")
            col_v1, col_v2 = st.columns(2)
            
            with col_v1:
                sector_counts = df_queue.merge(pd.DataFrame(universe)[["ticker", "sector"]], left_on="Company", right_on="ticker", how="left")
                fig_pie = px.pie(sector_counts, names="sector", title="Attention by Sector")
                st.plotly_chart(fig_pie, use_container_width=True)
                
            with col_v2:
                heatmap_data = df_queue.groupby(["Company", "Signal"]).size().reset_index(name="count")
                if not heatmap_data.empty:
                    fig_heat = px.density_heatmap(heatmap_data, x="Company", y="Signal", title="Signal Heatmap")
                    st.plotly_chart(fig_heat, use_container_width=True)
                
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
            latest_period = df_obs["period_end"].max()
            st.caption(f"**Latest Valid Financial Period:** {latest_period}")
            
            st.markdown("### Executive Snapshot")
            latest = df_obs[df_obs["period_end"] == latest_period]
            metrics = ["revenue", "gross_profit", "operating_income", "operating_cash_flow"]
            cols = st.columns(len(metrics))
            for i, m in enumerate(metrics):
                row = latest[latest["metric"] == m]
                val = row.iloc[0]["value"] if not row.empty else None
                if val:
                    display = f"${val/1e9:.1f}B" if abs(val) >= 1e9 else f"${val/1e6:.1f}M"
                    cols[i].metric(m.replace("_", " ").title(), display)
                else:
                    cols[i].metric(m.replace("_", " ").title(), "N/A")
                    
            st.markdown("### Historical Trends")
            hist_df = df_obs[df_obs["period_type"] == "QUARTER"]
            if not hist_df.empty:
                fig = px.line(hist_df, x="period_end", y="value", color="metric", title="Financial Trajectory (Quarterly)")
                st.plotly_chart(fig, use_container_width=True)
                
            st.markdown("### What Changed? & Investigation")
            company_signals = rows(db, "SELECT * FROM signals WHERE company=? AND suppressed IS NULL", (ticker,))
            if company_signals:
                for s in company_signals:
                    intel = generate_intelligence(s["signal_id"], ticker, company_meta.get("sector"), s.get("evidence", ""))
                    with st.expander(f"🚨 {intel['title']} (Priority: {s['severity']})", expanded=True):
                        st.write(f"**What Changed:** {intel['what_changed']}")
                        st.write("**Investigate:**")
                        for item in intel["investigate"]:
                            st.write(f"- {item}")
            else:
                st.success("No critical deterioration signals detected.")
                
            st.markdown("### Peer Context")
            company_peers = rows(db, "SELECT metric, company_value, peer_median, peer_min, peer_max, n_peers, group_id FROM peer_context WHERE company=?", (ticker,))
            if company_peers:
                st.dataframe(pd.DataFrame(company_peers), use_container_width=True, hide_index=True)
            else:
                st.info("No peer context calculated.")
                
            st.markdown("### Corporate Events & Evidence")
            events = rows(db, "SELECT type, filed, description, source_url FROM events WHERE company=? ORDER BY filed DESC LIMIT 10", (ticker,))
            if events:
                for e in events:
                    status = "Completed" if "completed" in str(e["description"]).lower() else "Proposed/Pending"
                    st.write(f"**{e['filed']} - {e['type'].upper()} ({status})**")
                    st.write(f"{e['description']} [Source]({e['source_url']})")
                    st.divider()
            else:
                st.info("No recent 8-K material events extracted.")
        else:
            st.info("No data available. Refresh the company in the Portfolio tab.")
