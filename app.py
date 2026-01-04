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
    if st.button("🔄 Ververs nu", width="stretch"):
        clear_feed_caches()
        st.rerun()

st.markdown("# 🗞️ KbM Nieuws")

# Render progressively with spinners so you SEE progress instead of endless white loader
with st.spinner("Net binnen laden…"):
    try:
        render_section(
            "Net binnen",
            hours_limit=hrs,
            query=query,
            max_items=80,
            thumbs_n=6,
            view="home"
        )
    except Exception as e:
        st.error(e)
    
# Als er een artikel is aangeklikt (via ?section=...&open=...), toon alleen die sectie (artikelview) en stop.
try:
    _qp = st.query_params
    _qp_section = (_qp.get("section") or "").strip().lower()
    _qp_open = (_qp.get("open") or "").strip()
except Exception:
    _qp_section, _qp_open = "", ""

def _slug(s: str) -> str:
    import re as _re
    return _re.sub(r"[^a-z0-9]+", "_", (s or "").lower()).strip("_")

if _qp_open and _qp_section:
    # bekende home-secties + extra
    _titles = ["Net binnen","Binnenland","Buitenland","Show","Lokaal","Sport","Tech","Opmerkelijk","Economie"]
    hit_title = None
    for t in _titles:
        if _slug(t) == _qp_section:
            hit_title = t
            break
    if hit_title:
        render_section(hit_title, hours_limit=hrs, query=query, max_items=200, thumbs_n=6, view="full")
        st.stop()


render_section("Net binnen", hours_limit=hrs, query=query, max_items=80, thumbs_n=6, view="home")

with st.spinner("Binnenland laden…"):
    render_section("Binnenland", hours_limit=hrs, query=query, max_items=60, thumbs_n=4, view="home")

with st.spinner("Buitenland laden…"):
    render_section("Buitenland", hours_limit=hrs, query=query, max_items=60, thumbs_n=4, view="home")

if not safe_mode:
    with st.spinner("Show laden…"):
        render_section("Show", hours_limit=hrs, query=query, max_items=60, thumbs_n=4, view="home")
    with st.spinner("Lokaal laden…"):
        render_section("Lokaal", hours_limit=72, query=query, max_items=60, thumbs_n=4, view="home")
    with st.spinner("Sport laden…"):
        render_section("Sport", hours_limit=hrs, query=query, max_items=60, thumbs_n=4, view="home")
    with st.spinner("Tech laden…"):
        render_section("Tech", hours_limit=24, query=query, max_items=60, thumbs_n=4, view="home")
    with st.spinner("Opmerkelijk laden…"):
        render_section("Opmerkelijk", hours_limit=24, query=query, max_items=60, thumbs_n=4, view="home")
    with st.spinner("Economie laden…"):
        render_section("Economie", hours_limit=24, query=query, max_items=60, thumbs_n=4, view="home")
