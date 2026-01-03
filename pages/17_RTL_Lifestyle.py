import streamlit as st
from kbm_ui import render_section

st.set_page_config(page_title="RTL Lifestyle", page_icon="🍃", layout="wide")
st.markdown("# RTL Lifestyle")

query = st.text_input("Zoekterm (optioneel)", placeholder="bijv. Huizen, politiek, muziek…").strip() or None
hours = st.slider("Max uren oud (hard filter)", 1, 240, 240, 1)

render_section("RTL Lifestyle", hours_limit=hours, query=query, max_items=200, thumbs_n=6)
