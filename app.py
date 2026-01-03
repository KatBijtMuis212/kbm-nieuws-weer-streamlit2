import base64
import streamlit as st

from common import CATEGORY_FEEDS, collect_items, within_hours, host
from style import inject_css

APP_TITLE = "KbM Nieuws"
st.set_page_config(page_title=APP_TITLE, page_icon="🗞️", layout="wide")
inject_css(st)

# Page map as global (avoids indentation gremlins inside functions)
PAGE_MAP = {
    "Net binnen": "pages/00_Net_binnen.py",
    "Binnenland": "pages/01_Binnenland.py",
    "Buitenland": "pages/02_Buitenland.py",
    "Show": "pages/03_Show.py",
    "Lokaal": "pages/04_Lokaal.py",
    "Sport": "pages/06_Sport.py",
    "Tech": "pages/07_Tech.py",
    "Opmerkelijk": "pages/08_Opmerkelijk.py",
    "Weer": "pages/05_Weer.py",
}


def require_login():
    """Optional private password via Streamlit Secrets (APP_PASSWORD)."""
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


def logo_b64() -> str:
    """Inline logo for header."""
    try:
        with open("assets/Kbmnieuwslogo-zwartomrand.png", "rb") as f:
            return base64.b64encode(f.read()).decode("ascii")
    except Exception:
        return ""


st.markdown(
    f"""
<div class="kbm-topbar">
  <div class="kbm-brand">
    <img src="data:image/png;base64,{logo_b64()}" />
    <div>
      <div class="kbm-title">KbM Nieuws</div>
      <div class="kbm-sub">Net binnen = max 4 uur geleden. Per blok: 1 hero + 4 thumbnails + “Meer …”.</div>
    </div>
  </div>
</div>
""",
    unsafe_allow_html=True,
)

# Controls
leftc, rightc = st.columns([1.2, 0.8], gap="large")
with leftc:
    query = st.text_input("Zoekterm (optioneel)", placeholder="bijv. Huizen, politiek, muziek…")
with rightc:
    force_fetch = st.toggle("Betere samenvatting (artikel ophalen)", value=True)
    if st.button("🔁 Ververs nu", use_container_width=True):
        st.cache_data.clear()


def render_section(cat_name: str, only_recent_hours: int | None):
    feed_labels = CATEGORY_FEEDS.get(cat_name, [])
    items, _ = collect_items(
        feed_labels,
        query=query or None,
        max_per_feed=25,
        force_fetch=force_fetch,
    )

    if only_recent_hours is not None:
        items = [x for x in items if within_hours(x.get("dt"), only_recent_hours)]

    if not items:
        st.info(f"Geen berichten voor **{cat_name}** (nu).")
        return

    # Hero: preferably with image
    hero = next((x for x in items if x.get("img")), items[0])
    rest = [x for x in items if x is not hero]
    thumbs = rest[:4]

    st.markdown("<div class='kbm-card' style='margin-top:12px'>", unsafe_allow_html=True)
    st.markdown(f"### {cat_name}")

    colA, colB = st.columns([1.25, 0.75], gap="large")

    # HERO
    with colA:
        if hero.get("img"):
            st.image(hero["img"], use_container_width=True)

        st.markdown(f"#### [{hero['title']}]({hero['link']})")

        dt_txt = hero["dt"].astimezone().strftime("%d-%m %H:%M") if hero.get("dt") else ""
        meta = f"{host(hero['link'])}{' • ' + dt_txt if dt_txt else ''}"
        st.markdown(f"<div class='kbm-meta'>{meta}</div>", unsafe_allow_html=True)

        if hero.get("summary"):
            st.write(hero["summary"])

    # THUMBS (HTML rows => mobile-friendly, no giant stacked images)
    with colB:
        st.markdown("<div class='kbm-thumbs'>", unsafe_allow_html=True)

        for t in thumbs:
            dt_small = t["dt"].astimezone().strftime("%H:%M") if t.get("dt") else ""
            meta2 = f"{dt_small}{' • ' if dt_small else ''}{host(t['link'])}"

            img = t.get("img") or ""
            img_tag = (
                f"<img class='kbm-thumbimg' src='{img}' alt='' />"
                if img
                else "<div class='kbm-thumbimg' aria-hidden='true'></div>"
            )

            st.markdown(
                f"""
                <div class="kbm-thumbrow">
                  {img_tag}
                  <div class="kbm-thumbtext">
                    <p class="kbm-thumbtitle"><a href="{t['link']}" target="_blank" rel="noopener">{t['title']}</a></p>
                    <div class="kbm-thumbmeta">{meta2}</div>
                  </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        st.markdown("</div>", unsafe_allow_html=True)

    target = PAGE_MAP.get(cat_name)
    if target:
        st.page_link(target, label=f"Meer {cat_name}", icon="➡️")

    st.markdown("</div>", unsafe_allow_html=True)


# Home layout
st.markdown("## Net binnen")
render_section("Net binnen", only_recent_hours=4)

st.markdown("## Categorieën")
g1, g2 = st.columns(2, gap="large")

with g1:
    render_section("Binnenland", None)
    render_section("Show", None)
    render_section("Sport", None)

with g2:
    render_section("Buitenland", None)
    render_section("Lokaal", None)
    render_section("Tech", None)

render_section("Opmerkelijk", None)

st.caption("Weer staat als aparte pagina in het menu (🌦️ Weer).")
