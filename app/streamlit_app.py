"""The Quiet Map — interactive explorer.

Phase 4 deliverable. Run with:
    streamlit run app/streamlit_app.py
"""
import streamlit as st

st.set_page_config(page_title="Which Airport Cost", layout="wide")

st.title("Which Airport Cost")
st.subheader("Mapping who lives under America's airport noise")

st.info(
    "Phase 1 in progress — the explorer goes live once the "
    "tract x contour overlay dataset exists. See README.md for the roadmap."
)
