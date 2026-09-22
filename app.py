import streamlit as st
import pandas as pd
st.set_page_config(page_title="Financial Intelligence Radar",layout="wide")
st.title("Financial Intelligence Radar")
st.caption("Public-disclosure intelligence for analyst attention — not investment advice.")
portfolio,research=st.tabs(["Portfolio Intelligence","Research Mode"])
with portfolio:
    st.subheader("What changed?")
    st.info("Load SEC observations through the pipeline. Low-quality or incomparable data is suppressed, not silently scored.")
    st.dataframe(pd.DataFrame(columns=["Company","Filing","Signal","Severity","Confidence","Source evidence"]),hide_index=True)
with research:
    st.subheader("Company research")
    st.code("Alert → rule/version → calculation → observation → raw XBRL fact → filing → SEC source")