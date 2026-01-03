import streamlit as st
from common import CATEGORY_FEEDS, collect_items, host, within_hours
from style import inject_css

st.set_page_config(page_title="Binnenland • KbM Nieuws", page_icon="🗞️", layout="wide")
inject_css(st)

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

require_login()

st.title("Binnenland")
st.caption("NOS / NU.nl / AD (selectie).")

query = st.text_input("Zoekterm (optioneel)", placeholder="bijv. Huizen, politiek, muziek…")
force_fetch = st.toggle("Betere samenvatting (artikel ophalen)", value=True)

if st.button("🔁 Ververs nu", use_container_width=True):
    st.cache_data.clear()

items, _ = collect_items(CATEGORY_FEEDS.get("Binnenland", []), query=query or None, max_per_feed=60, force_fetch=force_fetch)


if not items:
    st.info("Geen resultaten.")
else:
    for it in items[:200]:
        st.markdown("<div class='kbm-card' style='margin-top:12px'>", unsafe_allow_html=True)
        st.markdown(f"<span class='kbm-chip'>{it['source']}</span>", unsafe_allow_html=True)
        st.markdown(f"### [{it['title']}]({it['link']})")
        dt_txt = it["dt"].astimezone().strftime("%d-%m %H:%M") if it.get("dt") else ""
        st.markdown(f"<div class='kbm-meta'>{host(it['link'])}{' • ' + dt_txt if dt_txt else ''}</div>", unsafe_allow_html=True)
        if it.get("img"):
            st.image(it["img"], use_container_width=True)
        if it.get("summary"):
            st.write(it["summary"])
        st.markdown("</div>", unsafe_allow_html=True)

st.page_link("app.py", label="⬅️ Terug naar Home")
