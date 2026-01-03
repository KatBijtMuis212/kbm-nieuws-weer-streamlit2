import streamlit as st
from streamlit_autorefresh import st_autorefresh

from style import inject_css
from common import clear_feed_caches
from kbm_ui import render_section

st.set_page_config(page_title="KbM Nieuws", page_icon="🗞️", layout="wide")

inject_css()

st.markdown("<div class='kbm-shell'>", unsafe_allow_html=True)

# Topbar
colL, colR = st.columns([0.72, 0.28], gap="small")
with colL:
    st.markdown("<div class='kbm-topbar'>", unsafe_allow_html=True)
    st.markdown("<div class='kbm-brand'><img src='https://katbijtmuis.nl/kbmnieuws/wp-content/uploads/2025/12/Kbmnieuwslogo.png' alt='KbM Nieuws'></div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

with colR:
    st.caption("⚡ Auto-refresh")
    freq = st.select_slider("Interval", options=[0, 30, 60, 120, 300], value=60, help="0 = uit")
    if freq and freq > 0:
        st_autorefresh(interval=freq*1000, key="kbm_autorefresh")
    if st.button("🔄 Ververs nu", use_container_width=True):
        clear_feed_caches()
        st.rerun()

st.markdown("## Net binnen")
query = st.text_input("Zoeken", placeholder="bijv. Huizen, politiek, muziek…").strip() or None
hrs = st.slider("Max uren oud (hard filter)", 1, 24, 4, 1)

render_section("Net binnen", hours_limit=hrs, query=query, max_items=80, thumbs_n=5)

st.markdown("## Categorieën")
render_section("Binnenland", hours_limit=hrs, query=query, max_items=60, thumbs_n=4)
render_section("Buitenland", hours_limit=hrs, query=query, max_items=60, thumbs_n=4)
render_section("Show", hours_limit=hrs, query=query, max_items=60, thumbs_n=4)
render_section("Lokaal", hours_limit=hrs, query=query, max_items=60, thumbs_n=4)
render_section("Sport", hours_limit=hrs, query=query, max_items=60, thumbs_n=4)
render_section("Tech", hours_limit=hrs, query=query, max_items=60, thumbs_n=4)
render_section("Opmerkelijk", hours_limit=hrs, query=query, max_items=60, thumbs_n=4)

st.markdown("</div>", unsafe_allow_html=True)
