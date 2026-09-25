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
    "Public-disclosure intelligence for analyst triage / attention priority — not investment advice."
)

# ---------------------------------------------------------------------------
# Persistent state
# ---------------------------------------------------------------------------
db = connect()
try:
    latest_event = rows(db, "SELECT MAX(filed) as latest FROM events")
    if latest_event and latest_event[0]["latest"]:
        st.caption(f"Data AS OF (most recent filing event): {latest_event[0]['latest']}")
except Exception:
    pass

# ---------------------------------------------------------------------------
# UI layout: Two modes
# ---------------------------------------------------------------------------
portfolio_tab, research_tab = st.tabs(["Portfolio Mode", "Research Mode"])
universe = load_universe()

# ===== PORTFOLIO MODE ======================================================
with portfolio_tab:
    st.subheader("Where should an analyst investigate?")

    # --- 1. Portfolio Signals ---
    active_signals = rows(
        db,
        "SELECT company, signal_id, severity, confidence, explanation, version "
        "FROM signals WHERE suppressed IS NULL ORDER BY company",
    )
    if active_signals:
        df_sig = pd.DataFrame(active_signals)
        st.dataframe(
            df_sig,
            use_container_width=True,
            hide_index=True,
            column_config={
                "severity": st.column_config.TextColumn(
                    "Analyst Attention Priority"
                ),
            },
        )
    else:
        st.info("No active signals in portfolio.")

    # --- 2. Other Active Signals ---
    st.subheader("Other Active Signals (Non-Core)")
    # Not yet implemented. Placeholder for signals that fired but
    # are below the confidence/severity threshold for top-level triage.
    st.info("No other active signals.")

    # --- 3. Watchlist and refresh ---
    st.subheader("Portfolio Watchlist")
    wl = rows(db, "SELECT ticker, active FROM watchlist")
    wl_dict = {w["ticker"]: bool(w["active"]) for w in wl}

    df_wl = pd.DataFrame(
        [
            {
                "Ticker": x["ticker"],
                "Sector": x.get("sector", ""),
                "Active": wl_dict.get(x["ticker"], True),
            }
            for x in universe
        ]
    )

    edited_df = st.data_editor(
        df_wl,
        hide_index=True,
        use_container_width=True,
        column_config={"Active": st.column_config.CheckboxColumn(required=True)},
    )
    save_watchlist(
        db,
        [
            {
                "ticker": r["Ticker"],
                "active": r["Active"],
                "cik": next((c["cik"] for c in universe if c["ticker"] == r["Ticker"]), ""),
            }
            for _, r in edited_df.iterrows()
        ],
    )

    if st.button("Refresh SEC Data for Active Portfolio"):
        active_companies = [
            x
            for x in universe
            if edited_df[edited_df["Ticker"] == x["ticker"]].iloc[0]["Active"]
        ]
        if not active_companies:
            st.warning("No active companies selected.")
        else:
            with st.spinner("Fetching XBRL facts and 8-K filings from SEC EDGAR..."):
                client = SECClient(
                    user_agent=os.environ.get(
                        "SEC_USER_AGENT", "FinancialRadarApp contact@example.com"
                    )
                )
                progress = st.progress(0)
                for i, c in enumerate(active_companies):
                    try:
                        ingest_company(client, db, c)
                    except Exception as e:
                        st.error(f"Failed to ingest {c['ticker']}: {e}")
                    progress.progress((i + 1) / len(active_companies))
                st.success("Refresh complete!")
                st.rerun()

    with st.expander("Methodology Notes", expanded=False):
        st.markdown(
            "1. **Strict Provenance:** Every signal observation traces to a specific SEC accession, "
            "form, and filing date. \n"
            "2. **Evidence Linking:** Financial signals are completely independent of filing events. "
            "A company may have an 8-K 'restructuring' event and an 'operating margin deterioration' "
            "signal. The analyst must determine causation.\n"
            "3. **Peer Groups:** Peer comparisons require strictly compatible metrics and are only computed "
            "in configured peer groups."
        )

# ===== RESEARCH MODE =======================================================
with research_tab:
    ticker = st.selectbox(
        "Company",
        [x["ticker"] for x in universe],
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
        latest_period = df_obs[~df_obs["quality"].isin(["NOT_REPORTED", "DataQuality.NOT_REPORTED", "CALCULATION_INVALID"]) & (df_obs["comparable"] == 1)]["period_end"].max() if not df_obs[~df_obs["quality"].isin(["NOT_REPORTED", "DataQuality.NOT_REPORTED", "CALCULATION_INVALID"]) & (df_obs["comparable"] == 1)].empty else None
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
