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

# Freshness: show last SEC refresh timestamp and latest processed filing
try:
    _latest_filing = rows(db, "SELECT MAX(filed) as latest FROM filings")
    _latest_event = rows(db, "SELECT MAX(filed) as latest FROM events")
    _fresh_parts = []
    if _latest_filing and _latest_filing[0]["latest"]:
        _fresh_parts.append(f"Latest processed filing: {_latest_filing[0]['latest']}")
    if _latest_event and _latest_event[0]["latest"]:
        _fresh_parts.append(f"Latest filing event: {_latest_event[0]['latest']}")
    if _fresh_parts:
        st.caption(" | ".join(_fresh_parts))
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

    # --- 1. Portfolio Signals (active watchlist only) ---
    wl = rows(db, "SELECT ticker, active FROM watchlist")
    wl_dict = {w["ticker"]: bool(w["active"]) for w in wl}
    active_tickers = [t for t, a in wl_dict.items() if a]

    if active_tickers:
        ph = ",".join("?" * len(active_tickers))
        active_signals = rows(
            db,
            f"SELECT company, signal_id, severity, confidence, explanation, version "
            f"FROM signals WHERE suppressed IS NULL AND company IN ({ph}) ORDER BY company",
            tuple(active_tickers),
        )
    else:
        active_signals = []

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
        st.info("No active signals for watched companies.")

    # --- 2. Watchlist and refresh ---
    st.subheader("Portfolio Watchlist")

    df_wl = pd.DataFrame(
        [
            {
                "Ticker": x["ticker"],
                "Sector": x.get("sector", ""),
                "Active": wl_dict.get(x["ticker"], False),
            }
            for x in universe
        ]
    )

    edited_df = st.data_editor(
        df_wl,
        hide_index=True,
        use_container_width=True,
        column_config={"Active": st.column_config.CheckboxColumn(required=True)},
        key="watchlist_editor",
    )

    # Only persist watchlist when the user clicks the save button
    if st.button("Save Watchlist"):
        save_watchlist(
            db,
            [
                {
                    "ticker": r["Ticker"],
                    "active": r["Active"],
                    "cik": next(
                        (c["cik"] for c in universe if c["ticker"] == r["Ticker"]),
                        "",
                    ),
                }
                for _, r in edited_df.iterrows()
            ],
        )
        st.success("Watchlist saved.")
        st.rerun()

    if st.button("Refresh SEC Data for Active Portfolio"):
        active_companies = [
            x
            for x in universe
            if edited_df[edited_df["Ticker"] == x["ticker"]].iloc[0]["Active"]
        ]
        if not active_companies:
            st.warning("No active companies selected.")
        else:
            sec_ua = os.environ.get("SEC_USER_AGENT", "")
            if not sec_ua or "@" not in sec_ua:
                st.error(
                    "Set the SEC_USER_AGENT environment variable to "
                    "'YourAppName your-email@example.com' before refreshing. "
                    "SEC requires operator identification."
                )
            else:
                with st.spinner(
                    "Fetching XBRL facts and 8-K filings from SEC EDGAR..."
                ):
                    client = SECClient(user_agent=sec_ua)
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
            "in configured peer groups.\n"
            "4. **Historical Coverage:** Ingestion uses the SEC 'recent' submissions index, covering "
            "approximately the most recent 1,000 filings per company.\n"
            "5. **Deterministic Thresholds:** Signal severity is determined by fixed thresholds, not "
            "accounting materiality judgments. They indicate analyst attention priority only."
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
    st.subheader(f"{ticker} — Research")
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
        valid_mask = (
            ~df_obs["quality"].isin(
                ["NOT_REPORTED", "DataQuality.NOT_REPORTED", "CALCULATION_INVALID"]
            )
            & (df_obs["comparable"] == 1)
        )
        latest_period = (
            df_obs.loc[valid_mask, "period_end"].max()
            if valid_mask.any()
            else None
        )
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
                    u = row.iloc[0]["unit"]
                    if abs(val) >= 1e9:
                        display = f"{val/1e9:.1f}B {u}"
                    elif abs(val) >= 1e6:
                        display = f"{val/1e6:.1f}M {u}"
                    else:
                        display = f"{val:,.0f} {u}"
                    cols[i].metric(km.replace("_", " ").title(), display)
                else:
                    cols[i].metric(km.replace("_", " ").title(), "N/A")

        with st.expander("All observations", expanded=False):
            display_cols = [
                "metric", "value", "unit", "period_end",
                "period_type", "quality", "comparable", "reason",
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

    # --- Signals for this company with drill-down ---
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
                column_config={
                    "severity": st.column_config.TextColumn(
                        "Analyst Attention Priority"
                    ),
                },
            )

            # Signal evidence drill-down
            for sig in active_sig:
                with st.expander(
                    f"Evidence: {sig['signal_id']} ({sig['severity']})",
                    expanded=False,
                ):
                    st.markdown(f"**Explanation:** {sig['explanation']}")
                    st.markdown(
                        f"**Confidence:** {sig['confidence']} | "
                        f"**Version:** {sig['version']}"
                    )
                    try:
                        ev = json.loads(sig["evidence"]) if sig.get("evidence") else []
                    except (json.JSONDecodeError, TypeError):
                        ev = []
                    if ev:
                        for obs in ev:
                            der = obs.get("derived_from", [])
                            der_str = f" (derived from: {', '.join(der)})" if der else ""
                            st.markdown(
                                f"- **{obs.get('metric')}** = {obs.get('value')} {obs.get('unit')} "
                                f"| period_end={obs.get('period_end')} | type={obs.get('period_type')} "
                                f"| quality={obs.get('quality')}{der_str}"
                            )
                            for p in obs.get("provenance", []):
                                st.markdown(
                                    f"  - concept=`{p.get('concept')}` | "
                                    f"accession={p.get('accession')} | "
                                    f"form={p.get('form')} | "
                                    f"filed={p.get('filing_date')} | "
                                    f"raw={p.get('raw_value')} | "
                                    f"[SEC source]({p.get('source_url', '')})"
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
    st.subheader("Filing evidence")
    st.caption(
        "Filing \u2192 event type \u2192 evidence snippet \u2192 SEC source. "
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
        "Signal \u2192 rule/version \u2192 calculation \u2192 "
        "normalized observation \u2192 raw XBRL fact \u2192 SEC filing."
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
