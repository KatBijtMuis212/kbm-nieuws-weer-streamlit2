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

    safe_mode = st.toggle("🛟 Safe mode (sneller starten)", value=False,
                          help="Laadt minder secties op de home. Handig als Cloud traag is.")
    if st.button("🔄 Ververs nu", use_container_width=True):
        clear_feed_caches()
        st.rerun()

st.markdown("# 🗞️ KbM Nieuws")

# Render progressively with spinners so you SEE progress instead of endless white loader
with st.spinner("Net binnen laden…"):
    render_section("Net binnen", hours_limit=hrs, query=query, max_items=80, thumbs_n=6)

with st.spinner("Binnenland laden…"):
    render_section("Binnenland", hours_limit=hrs, query=query, max_items=60, thumbs_n=4)

with st.spinner("Buitenland laden…"):
    render_section("Buitenland", hours_limit=hrs, query=query, max_items=60, thumbs_n=4)

if not safe_mode:
    with st.spinner("Show laden…"):
        render_section("Show", hours_limit=hrs, query=query, max_items=60, thumbs_n=4)
    with st.spinner("Lokaal laden…"):
        render_section("Lokaal", hours_limit=72, query=query, max_items=60, thumbs_n=4)
    with st.spinner("Sport laden…"):
        render_section("Sport", hours_limit=hrs, query=query, max_items=60, thumbs_n=4)
    with st.spinner("Tech laden…"):
        render_section("Tech", hours_limit=24, query=query, max_items=60, thumbs_n=4)
    with st.spinner("Opmerkelijk laden…"):
        render_section("Opmerkelijk", hours_limit=24, query=query, max_items=60, thumbs_n=4)
    with st.spinner("Economie laden…"):
        render_section("Economie", hours_limit=24, query=query, max_items=60, thumbs_n=4)
