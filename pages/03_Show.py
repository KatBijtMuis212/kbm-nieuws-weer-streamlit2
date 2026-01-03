import streamlit as st
from kbm_ui import render_section

st.set_page_config(page_title="Show", page_icon="🗞️", layout="wide")
st.markdown("# Show")

query = st.text_input("Zoekterm (optioneel)", placeholder="bijv. Huizen, politiek, muziek…").strip() or None
hours = st.slider("Max uren oud (hard filter)", 1, 24, 4, 1)

render_section("Show", hours_limit=hours, query=query, max_items=120, thumbs_n=6)
