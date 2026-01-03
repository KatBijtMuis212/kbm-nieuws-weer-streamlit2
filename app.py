import streamlit as st
from style import inject_css
from common import clear_feed_caches
from kbm_ui import render_section

st.set_page_config(page_title="KbM Nieuws", page_icon="🗞️", layout="wide")
inject_css()

with st.sidebar:
    st.markdown("## KbM Nieuws")
    hrs = st.slider("Max uren oud (hard)", 1, 24, 4, 1)
    query = st.text_input("Zoeken", placeholder="bijv. Huizen, Maduro, darts…").strip() or None
    if st.button("🔄 Ververs nu", use_container_width=True):
        clear_feed_caches()
        st.rerun()

st.markdown("# 🗞️ KbM Nieuws")
render_section("Net binnen", hours_limit=hrs, query=query, max_items=80, thumbs_n=6)
render_section("Binnenland", hours_limit=hrs, query=query, max_items=60, thumbs_n=4)
render_section("Buitenland", hours_limit=hrs, query=query, max_items=60, thumbs_n=4)
render_section("Show", hours_limit=hrs, query=query, max_items=60, thumbs_n=4)
render_section("Lokaal", hours_limit=24, query=query, max_items=60, thumbs_n=4)
render_section("Sport", hours_limit=hrs, query=query, max_items=60, thumbs_n=4)
render_section("Tech", hours_limit=24, query=query, max_items=60, thumbs_n=4)
render_section("Opmerkelijk", hours_limit=24, query=query, max_items=60, thumbs_n=4)
render_section("Economie", hours_limit=24, query=query, max_items=60, thumbs_n=4)
