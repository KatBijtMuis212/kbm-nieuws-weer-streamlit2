import streamlit as st
from kbm_ui import render_section

st.set_page_config(page_title="Regionaal", page_icon="🧭", layout="wide")
st.markdown("# Regionaal")

query = st.text_input("Zoekterm (optioneel)", placeholder="bijv. Den Haag, Gouda, Westland…").strip() or None
hours = st.slider("Max uren oud (hard filter)", 1, 72, 24, 1)

render_section("Regionaal", hours_limit=hours, query=query, max_items=140, thumbs_n=6)
