import streamlit as st
import pandas as pd
from financial_radar.store import connect,rows
from financial_radar.pipeline import load_universe
st.set_page_config(page_title="Financial Intelligence Radar",layout="wide")
st.title("Financial Intelligence Radar")
st.caption("Public-disclosure intelligence for analyst attention — not investment advice.")
db=connect()
universe=load_universe()
existing={r["ticker"] for r in rows(db,"SELECT ticker FROM watchlist WHERE active=1")}
if not existing:
 from financial_radar.store import save_watchlist
 save_watchlist(db,universe);existing={x["ticker"] for x in universe}
portfolio,research=st.tabs(["Portfolio Intelligence","Research Mode"])
with portfolio:
 st.subheader("Where should an analyst investigate?")
 selected=st.multiselect("Monitored companies",[x["ticker"] for x in universe],default=sorted(existing))
 signals=rows(db,"SELECT * FROM signals WHERE company IN (%s) ORDER BY severity DESC"%(",".join("?"*len(selected)) if selected else "''"),selected) if selected else []
 st.dataframe(pd.DataFrame(signals) if signals else pd.DataFrame(columns=["company","signal_id","severity","confidence","explanation","evidence"]))
 events=rows(db,"SELECT * FROM events WHERE company IN (%s) ORDER BY filed DESC"%(",".join("?"*len(selected)) if selected else "''"),selected) if selected else []
 st.subheader("Recent filing events");st.dataframe(pd.DataFrame(events) if events else pd.DataFrame())
with research:
 ticker=st.selectbox("Company",sorted(existing) or [x["ticker"] for x in universe])
 metrics=rows(db,"SELECT metric,value,unit,period_end,period_type,quality,provenance FROM observations WHERE company=? ORDER BY period_end DESC",(ticker,))
 st.subheader("Financial observations");st.dataframe(pd.DataFrame(metrics))
 st.subheader("Evidence path");st.caption("Signal → rule calculation → normalized observation → provenance → SEC filing URL.")
 st.json([r["provenance"] for r in metrics[:5]])