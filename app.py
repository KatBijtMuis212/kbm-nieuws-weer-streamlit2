import base64
import streamlit as st

from common import clear_feed_caches
from style import inject_css
from kbm_ui import render_section

APP_TITLE = "KbM Nieuws"
st.set_page_config(page_title=APP_TITLE, page_icon="🗞️", layout="wide")

def require_login():
    pw = st.secrets.get("APP_PASSWORD", "").strip()
    if not pw:
        return
    if "kbm_ok" not in st.session_state:
        st.session_state.kbm_ok = False
    if st.session_state.kbm_ok:
        return
    st.markdown("### 🔒 Privé modus")
    inp = st.text_input("Wachtwoord", type="password")
    if st.button("Inloggen", use_container_width=True):
        st.session_state.kbm_ok = (inp == pw)
    if not st.session_state.kbm_ok:
        st.stop()

def logo_b64() -> str:
    try:
        with open("assets/Kbmnieuwslogo-zwartomrand.png", "rb") as f:
            return base64.b64encode(f.read()).decode("ascii")
    except Exception:
        return ""

require_login()

if "bookmarks" not in st.session_state:
    st.session_state.bookmarks = []

with st.sidebar:
    st.markdown("## ⚙️ Instellingen")
    dark_mode = st.toggle("🌙 Avondstand (dark mode)", value=bool(st.session_state.get("dark_mode", False)))
    st.session_state.dark_mode = dark_mode

    only_recent_hours = st.slider("🕒 Net binnen (max uren oud)", 1, 24, int(st.session_state.get("only_recent_hours", 4)), 1)
    st.session_state.only_recent_hours = only_recent_hours

    auto_refresh = st.toggle("🔔 Auto refresh (RSS)", value=bool(st.session_state.get("auto_refresh", False)))
    st.session_state.auto_refresh = auto_refresh

    interval_sec = st.select_slider("Interval", options=[30, 60, 120, 300], value=int(st.session_state.get("refresh_interval", 60)))
    st.session_state.refresh_interval = interval_sec

    st.divider()
    st.markdown("## ⭐ Lees later")
    if st.session_state.bookmarks:
        for bm in st.session_state.bookmarks[:25]:
            st.markdown(f"- [{bm['title']}](/Artikel?url={bm['link']})")
    else:
        st.caption("Nog leeg. Klik bij een bericht op ⭐.")

inject_css(st, dark=dark_mode)

if auto_refresh:
    try:
        from streamlit_autorefresh import st_autorefresh  # type: ignore
        st_autorefresh(interval=interval_sec * 1000, key="kbm_autorefresh")
    except Exception:
        st.warning("Auto refresh vereist dependency: streamlit-autorefresh. Voeg toe aan requirements.txt.")

st.markdown(
    f"""
<div class="kbm-topbar">
  <div class="kbm-brand">
    <div class="kbm-title">KbM Nieuws</div>
    <div class="kbm-sub">Alles lezen in de app • Klik op titel = Artikel-pagina</div>
  </div>
</div>
""",
    unsafe_allow_html=True,
)

leftc, rightc = st.columns([1.2, 0.8], gap="large")
with leftc:
    query = st.text_input("Zoekterm (optioneel)", placeholder="bijv. Huizen, politiek, muziek…").strip() or None
with rightc:
    if st.button("🔁 Ververs nu (RSS)", use_container_width=True):
        clear_feed_caches()
        st.rerun()

hrs = st.session_state.only_recent_hours
st.markdown("## Net binnen")
render_section("Net binnen", hours_limit=hrs, query=query)

st.markdown("## Categorieën")
g1, g2 = st.columns(2, gap="large")
with g1:
    render_section("Binnenland", hours_limit=hrs, query=query)
    render_section("Show", hours_limit=hrs, query=query)
    render_section("Sport", hours_limit=hrs, query=query)
with g2:
    render_section("Buitenland", hours_limit=hrs, query=query)
    render_section("Lokaal", hours_limit=hrs, query=query)
    render_section("Tech", hours_limit=hrs, query=query)
render_section("Opmerkelijk", hours_limit=hrs, query=query)

st.caption("Je blijft in Streamlit. Externe bronlink staat alleen klein onderaan (optioneel).")
