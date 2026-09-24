import os
import json
import streamlit as st
import pandas as pd

from financial_radar.store import connect, rows, save_watchlist
from financial_radar.pipeline import load_universe, ingest_company
from financial_radar.core import SECClient

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(page_title="Financial Intelligence Radar", layout="wide")
st.title("Financial Intelligence Radar")
st.caption(
    "Public-disclosure intelligence for analyst attention — not investment advice."
)

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
# Tabs
# ---------------------------------------------------------------------------
portfolio_tab, research_tab = st.tabs(["Portfolio Intelligence", "Research Mode"])

# ===== PORTFOLIO INTELLIGENCE ==============================================
with portfolio_tab:
    st.subheader("Where should an analyst investigate?")

    # --- Watchlist management ---
    with st.expander("Watchlist management", expanded=False):
        selected = st.multiselect(
            "Monitored companies",
            [x["ticker"] for x in universe],
            default=sorted(existing),
        )
        if st.button("Save watchlist"):
            save_watchlist(
                db,
                [{**x, "active": x["ticker"] in selected} for x in universe],
            )
            st.success("Watchlist saved locally.")
            st.rerun()

    # --- Refresh SEC data ---
    with st.expander("Refresh SEC data", expanded=False):
        contact = st.text_input(
            "SEC User-Agent contact email",
            value=os.getenv("SEC_USER_AGENT", ""),
            help="Required by SEC policy; stored only for this session.",
        )
        if st.button("Refresh selected companies"):
            if not selected:
                st.warning("Select at least one company.")
            elif not contact or "@" not in contact:
                st.warning("Provide a valid contact email for SEC User-Agent.")
            else:
                try:
                    client = SECClient(f"Financial Intelligence Radar {contact}")
                    progress = st.progress(0)
                    companies_to_refresh = [
                        x for x in universe if x["ticker"] in selected
                    ]
                    for i, company in enumerate(companies_to_refresh):
                        with st.status(
                            f"Refreshing {company['ticker']}…", expanded=False
                        ):
                            result = ingest_company(client, db, company)
                            st.write(
                                f"✅ {result['observations']} observations, "
                                f"{result['signals']} signals"
                            )
                            if result.get("peer_group"):
                                st.write(
                                    f"👥 Peer group: {result['peer_group']}"
                                )
                            if result.get("events"):
                                st.write(
                                    f"📄 {result['events']} filing events detected"
                                )
                        progress.progress((i + 1) / len(companies_to_refresh))
                    st.success(
                        "Refresh complete. Signals, events, and peer context updated."
                    )
                except Exception as exc:
                    st.error(
                        f"Refresh failed; no values were substituted: {exc}"
                    )

    # --- Active watchlist tickers ---
    active_tickers = sorted(
        {r["ticker"] for r in rows(db, "SELECT ticker FROM watchlist WHERE active=1")}
    )
    if not active_tickers:
        st.info("No companies in watchlist. Add companies above.")
        st.stop()

    # --- Actionable signals ---
    st.subheader("🚨 Actionable signals")
    if active_tickers:
        placeholders = ",".join("?" * len(active_tickers))
        signals = rows(
            db,
            f"SELECT * FROM signals WHERE company IN ({placeholders}) "
            f"AND suppressed IS NULL ORDER BY severity DESC",
            active_tickers,
        )
    else:
        signals = []

    if signals:
        df_sig = pd.DataFrame(signals)
        display_cols = [
            "company", "signal_id", "severity", "confidence",
            "explanation", "version",
        ]
        available_cols = [c for c in display_cols if c in df_sig.columns]
        st.dataframe(
            df_sig[available_cols],
            use_container_width=True,
            hide_index=True,
        )

        with st.expander("Signal definitions", expanded=False):
            st.markdown("""
| Signal | What it measures |
|--------|------------------|
| RECEIVABLES_REVENUE_DIVERGENCE | Receivables growing faster than revenue |
| INVENTORY_SALES_DIVERGENCE | Inventory growing faster than sales |
| GROSS_MARGIN_COMPRESSION | Gross margin declining period-over-period |
| OPERATING_DELEVERAGE | Operating margin deterioration |
| EARNINGS_CASH_CONVERSION_DETERIORATION | OCF/earnings ratio declining |
| FREE_CASH_FLOW_DETERIORATION | Free cash flow declining materially |
| LEVERAGE_INTEREST_BURDEN | Debt/operating-income ratio increasing |
| LIQUIDITY_COMPRESSION | Cash/current-liabilities ratio declining |
| SHARE_COUNT_DILUTION | Diluted share count increasing |
| MULTI_FACTOR_DETERIORATION_CLUSTER | 3+ simultaneous deterioration signals |
""")
    else:
        st.info(
            "No actionable signals detected. Refresh data or expand watchlist."
        )

    # --- Suppressed signals ---
    if active_tickers:
        suppressed = rows(
            db,
            f"SELECT company, signal_id, suppressed AS reason FROM signals "
            f"WHERE company IN ({placeholders}) AND suppressed IS NOT NULL",
            active_tickers,
        )
        if suppressed:
            with st.expander(
                f"Suppressed signals ({len(suppressed)})", expanded=False
            ):
                st.caption(
                    "These signals were suppressed due to missing, "
                    "incomparable, or economically insignificant data."
                )
                st.dataframe(
                    pd.DataFrame(suppressed),
                    use_container_width=True,
                    hide_index=True,
                )

    # --- Filing evidence: linked events + signals ---
    st.subheader("📄 SEC filing evidence")
    st.caption(
        "Filing → event → evidence snippet → other active signals. "
        "Events and signals are presented together; no causal claims are made."
    )
    if active_tickers:
        events = rows(
            db,
            f"SELECT company, type, form, filed, accession, description, source_url, extraction_version "
            f"FROM events WHERE company IN ({placeholders}) "
            f"ORDER BY filed DESC LIMIT 50",
            active_tickers,
        )
    else:
        events = []

    if events:
        df_events = pd.DataFrame(events)
        # Enrich with other active signals for the same company
        for idx, event_row in df_events.iterrows():
            company = event_row["company"]
            company_signals = rows(
                db,
                "SELECT signal_id, severity, confidence, explanation FROM signals "
                "WHERE company=? AND suppressed IS NULL",
                (company,),
            )
            df_events.at[idx, "other_active_signals"] = ", ".join(
                s["signal_id"] for s in company_signals
            ) if company_signals else ""

        display_cols = [
            "company", "type", "form", "filed", "accession",
            "description", "other_active_signals", "extraction_version", "source_url",
        ]
        available = [c for c in display_cols if c in df_events.columns]
        st.dataframe(
            df_events[available],
            use_container_width=True,
            hide_index=True,
            column_config={
                "source_url": st.column_config.LinkColumn(
                    "SEC Filing", display_text="View on SEC"
                ),
            },
        )
    else:
        st.info("No filing events found. Refresh data to extract events.")

    # --- Peer context summary ---
    st.subheader("👥 Peer context")
    if active_tickers:
        peer_data = rows(
            db,
            f"SELECT company, group_id, metric, company_value, peer_median, "
            f"n_peers, version FROM peer_context "
            f"WHERE company IN ({placeholders})",
            active_tickers,
        )
    else:
        peer_data = []

    if peer_data:
        df_peer = pd.DataFrame(peer_data)
        st.dataframe(df_peer, use_container_width=True, hide_index=True)
        st.caption(
            "Peer context provides comparison, not recommendation. "
            "Peer groups are explicitly configured and versioned."
        )
    else:
        st.info(
            "No peer context available. Refresh data for companies "
            "in configured peer groups."
        )

# ===== RESEARCH MODE =======================================================
with research_tab:
    ticker = st.selectbox(
        "Company",
        active_tickers or [x["ticker"] for x in universe],
    )

    if not ticker:
        st.info("Select a company to research.")
        st.stop()

    # --- Company overview ---
    st.subheader(f"🔍 {ticker} — Research")
    company_meta = next(
        (x for x in universe if x["ticker"] == ticker), None
    )
    if company_meta:
        col1, col2, col3 = st.columns(3)
        col1.metric("Ticker", ticker)
        col2.metric("Sector", company_meta.get("sector", "Unknown"))
        col3.metric("CIK", company_meta.get("cik", "Unknown"))

    # --- Financial observations ---
    st.subheader("Financial observations")
    metrics = rows(
        db,
        "SELECT metric, value, unit, period_end, period_type, quality, "
        "comparable, reason, provenance FROM observations "
        "WHERE company=? ORDER BY period_end DESC",
        (ticker,),
    )

    if metrics:
        df_obs = pd.DataFrame(metrics)
        latest_period = df_obs["period_end"].max() if not df_obs.empty else None
        if latest_period:
            latest = df_obs[df_obs["period_end"] == latest_period]
            key_metrics = [
                "revenue", "gross_profit", "operating_income",
                "net_income", "operating_cash_flow",
            ]
            cols = st.columns(min(len(key_metrics), 5))
            for i, km in enumerate(key_metrics):
                row = latest[latest["metric"] == km]
                if not row.empty and row.iloc[0]["value"] is not None:
                    val = row.iloc[0]["value"]
                    unit = row.iloc[0]["unit"]
                    if abs(val) >= 1e9:
                        display = f"{val/1e9:.1f}B {unit}"
                    elif abs(val) >= 1e6:
                        display = f"{val/1e6:.1f}M {unit}"
                    else:
                        display = f"{val:,.0f} {unit}"
                    cols[i].metric(km.replace("_", " ").title(), display)
                else:
                    cols[i].metric(km.replace("_", " ").title(), "N/A")

        with st.expander("All observations", expanded=False):
            display_cols = [
                "metric", "value", "unit", "period_end",
                "period_type", "quality", "comparable", "reason"
            ]
            available = [c for c in display_cols if c in df_obs.columns]
            st.dataframe(
                df_obs[available],
                use_container_width=True,
                hide_index=True,
            )
    else:
        st.info(
            f"No observations for {ticker}. "
            "Use Refresh SEC data in Portfolio tab."
        )

    # --- Signals for this company ---
    st.subheader("Signals")
    company_signals = rows(
        db,
        "SELECT signal_id, severity, confidence, explanation, "
        "suppressed, evidence, version FROM signals WHERE company=?",
        (ticker,),
    )
    if company_signals:
        active_sig = [s for s in company_signals if not s.get("suppressed")]
        suppressed_sig = [s for s in company_signals if s.get("suppressed")]

        if active_sig:
            st.dataframe(
                pd.DataFrame(active_sig)[
                    ["signal_id", "severity", "confidence", "explanation"]
                ],
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info(f"No active signals for {ticker}.")

        if suppressed_sig:
            with st.expander(
                f"Suppressed ({len(suppressed_sig)})", expanded=False
            ):
                st.dataframe(
                    pd.DataFrame(suppressed_sig)[
                        ["signal_id", "suppressed"]
                    ],
                    use_container_width=True,
                    hide_index=True,
                )
    else:
        st.info(f"No signals for {ticker}. Refresh data first.")

    # --- Filing events with evidence ---
    st.subheader("📄 Filing evidence")
    st.caption(
        "Filing → event type → evidence snippet → SEC source. "
        "Events and signals are presented separately; no causal claims are made."
    )
    company_events = rows(
        db,
        "SELECT type, form, filed, accession, description, source_url, extraction_version "
        "FROM events WHERE company=? ORDER BY filed DESC",
        (ticker,),
    )
    if company_events:
        df_events = pd.DataFrame(company_events)
        display_cols = [
            "type", "form", "filed", "accession",
            "description", "extraction_version", "source_url",
        ]
        available = [c for c in display_cols if c in df_events.columns]
        st.dataframe(
            df_events[available],
            use_container_width=True,
            hide_index=True,
            column_config={
                "source_url": st.column_config.LinkColumn(
                    "SEC Filing", display_text="View on SEC"
                ),
                "description": st.column_config.TextColumn(
                    "Evidence Snippet", width="large"
                ),
            },
        )
    else:
        st.info(f"No filing events for {ticker}.")

    # --- Peer context ---
    st.subheader("Peer context")
    company_peers = rows(
        db,
        "SELECT metric, company_value, peer_median, peer_min, peer_max, "
        "n_peers, group_id, version FROM peer_context WHERE company=?",
        (ticker,),
    )
    if company_peers:
        st.dataframe(
            pd.DataFrame(company_peers),
            use_container_width=True,
            hide_index=True,
        )
        st.caption(
            "Peer comparisons provide context only. "
            "Peer groups are versioned and analyst-configured."
        )
    else:
        st.info(
            f"No peer context for {ticker}. "
            "Company may not be in a configured peer group."
        )

    # --- Evidence & provenance trail ---
    st.subheader("Evidence & provenance")
    st.caption(
        "Signal → rule/version → calculation → "
        "normalized observation → raw XBRL fact → SEC filing."
    )
    if metrics:
        provenance_data = []
        for r in metrics[:20]:
            try:
                prov = json.loads(r["provenance"]) if r.get("provenance") else []
            except (json.JSONDecodeError, TypeError):
                prov = []
            for p in prov:
                provenance_data.append(
                    {
                        "metric": r["metric"],
                        "concept": p.get("concept", ""),
                        "accession": p.get("accession", ""),
                        "filing_date": p.get("filing_date", ""),
                        "form": p.get("form", ""),
                        "raw_value": p.get("raw_value"),
                        "source_url": p.get("source_url", ""),
                        "mapping_version": p.get("mapping_version", ""),
                    }
                )
        if provenance_data:
            df_prov = pd.DataFrame(provenance_data)
            st.dataframe(
                df_prov,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "source_url": st.column_config.LinkColumn(
                        "SEC Source", display_text="View"
                    ),
                },
            )
        else:
            st.info("No provenance data available for recent observations.")
    else:
        st.info("No observations to trace provenance from.")
