import base64
import streamlit as st

from common import CATEGORY_FEEDS, collect_items, within_hours, host, item_id, pretty_dt, clear_feed_caches
from style import inject_css

APP_TITLE = "KbM Nieuws"
st.set_page_config(page_title=APP_TITLE, page_icon="🗞️", layout="wide")

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
    "Artikel": "pages/99_Artikel.py",
}

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

def article_url(src_url: str) -> str:
    # Internal page route (multipage): /Artikel
    return f"/Artikel?url={src_url}"

require_login()

if "bookmarks" not in st.session_state:
    st.session_state.bookmarks = []
if "seen_ids" not in st.session_state:
    st.session_state.seen_ids = set()

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
            st.markdown(f"- [{bm['title']}]({article_url(bm['link'])})")
        if st.button("🧹 Wis bookmarks", use_container_width=True):
            st.session_state.bookmarks = []
            st.rerun()
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
    <img src="data:image/png;base64,{logo_b64()}" />
    <div>
      <div class="kbm-title">KbM Nieuws</div>
      <div class="kbm-sub">Alles lezen in de app • AI-samenvatting op artikelpagina • lees later ⭐</div>
    </div>
  </div>
</div>
""",
    unsafe_allow_html=True,
)

leftc, rightc = st.columns([1.2, 0.8], gap="large")
with leftc:
    query = st.text_input("Zoekterm (optioneel)", placeholder="bijv. Huizen, politiek, muziek…")
with rightc:
    if st.button("🔁 Ververs nu (RSS)", use_container_width=True):
        clear_feed_caches()
        st.rerun()

st.caption("Klik altijd op **🔎 Open** (of op de titel) om het artikel + samenvatting **in Streamlit** te lezen.")

def add_bookmark(it: dict):
    ids = {b.get("id") for b in st.session_state.bookmarks}
    if it.get("id") in ids:
        return
    st.session_state.bookmarks.insert(0, {
        "id": it.get("id"),
        "title": it.get("title"),
        "link": it.get("link"),
        "dt": it.get("dt"),
    })

def render_item_expander(it: dict, compact: bool = False):
    title = it.get("title") or "Bericht"
    new_badge = " <span class='kbm-new'>NEW</span>" if it.get("is_new") else ""
    st.markdown(f"""<div class="kbm-exp-title">{title}{new_badge}</div>""", unsafe_allow_html=True)

    cols = st.columns([0.62, 0.38], gap="small")
    with cols[0]:
        st.caption(f"{host(it.get('link',''))} • {pretty_dt(it.get('dt'))}")
    with cols[1]:
        b1, b2 = st.columns(2, gap="small")
        with b1:
            if st.button("⭐", key=f"bm_{it['id']}", use_container_width=True):
                add_bookmark(it)
                st.toast("Toegevoegd aan lees later ⭐")
        with b2:
            st.link_button("🔎 Open", url=article_url(it.get("link","")), use_container_width=True)

    if it.get("img") and not compact:
        st.image(it["img"], use_container_width=True)

    if it.get("rss_summary"):
        st.markdown("**Korte preview (RSS):**")
        st.write(it["rss_summary"])

    # External source link stays available, but secondary
    st.markdown(f"<div class='kbm-meta'><a href='{it.get('link','')}' target='_blank' rel='noopener'>Open origineel artikel</a></div>", unsafe_allow_html=True)

def render_section(cat_name: str, hours_limit: int | None):
    feed_labels = CATEGORY_FEEDS.get(cat_name, [])
    items, _ = collect_items(
        feed_labels,
        query=(query or None),
        max_per_feed=25,
        force_fetch=False,
        ai_on=False,
    )

    if hours_limit is not None:
        items = [x for x in items if within_hours(x.get("dt"), hours_limit)]

    if not items:
        st.info(f"Geen berichten voor **{cat_name}** (nu).")
        return

    for it in items:
        it["id"] = item_id(it)
        it["is_new"] = it["id"] not in st.session_state.seen_ids

    hero = next((x for x in items if x.get("img")), items[0])
    rest = [x for x in items if x is not hero]
    thumbs = rest[:4]

    st.markdown("<div class='kbm-card' style='margin-top:12px'>", unsafe_allow_html=True)
    st.markdown(f"### {cat_name}")

    colA, colB = st.columns([1.25, 0.75], gap="large")

    with colA:
        if hero.get("img"):
            st.image(hero["img"], use_container_width=True)
        # Title links to internal Artikel page
        st.markdown(f"#### <a href='{article_url(hero['link'])}'>{hero['title']}</a>", unsafe_allow_html=True)
        st.markdown(f"<div class='kbm-meta'>{host(hero['link'])} • {pretty_dt(hero.get('dt'))}</div>", unsafe_allow_html=True)
        btns = st.columns([0.5, 0.5], gap="small")
        with btns[0]:
            st.link_button("🔎 Open in KbM", url=article_url(hero["link"]), use_container_width=True)
        with btns[1]:
            if st.button("⭐ Lees later", key=f"bm_hero_{hero['id']}", use_container_width=True):
                add_bookmark(hero)
                st.toast("Toegevoegd aan lees later ⭐")
        with st.expander("Lees preview", expanded=False):
            render_item_expander(hero, compact=True)

    with colB:
        st.markdown("<div class='kbm-thumbs'>", unsafe_allow_html=True)
        for t in thumbs:
            dt_small = t["dt"].astimezone().strftime("%H:%M") if t.get("dt") else ""
            meta2 = f"{dt_small}{' • ' if dt_small else ''}{host(t['link'])}"
            img = t.get("img") or ""
            img_tag = f"<img class='kbm-thumbimg' src='{img}' alt='' />" if img else "<div class='kbm-thumbimg' aria-hidden='true'></div>"
            new_badge = "<span class='kbm-new'>NEW</span>" if t.get("is_new") else ""
            # IMPORTANT: link goes to internal Artikel page
            st.markdown(
                f"""
                <div class="kbm-thumbrow">
                  {img_tag}
                  <div class="kbm-thumbtext">
                    <p class="kbm-thumbtitle">{new_badge}<a href="{article_url(t['link'])}">{t['title']}</a></p>
                    <div class="kbm-thumbmeta">{meta2}</div>
                  </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            with st.expander("Lees preview", expanded=False):
                render_item_expander(t, compact=True)
        st.markdown("</div>", unsafe_allow_html=True)

    target = PAGE_MAP.get(cat_name)
    if target:
        st.page_link(target, label=f"Meer {cat_name}", icon="➡️")

    st.markdown("</div>", unsafe_allow_html=True)

    for it in items[:30]:
        st.session_state.seen_ids.add(it["id"])

hrs = st.session_state.only_recent_hours

st.markdown("## Net binnen")
render_section("Net binnen", hours_limit=hrs)

st.markdown("## Categorieën")
g1, g2 = st.columns(2, gap="large")
with g1:
    render_section("Binnenland", hours_limit=hrs)
    render_section("Show", hours_limit=hrs)
    render_section("Sport", hours_limit=hrs)
with g2:
    render_section("Buitenland", hours_limit=hrs)
    render_section("Lokaal", hours_limit=hrs)
    render_section("Tech", hours_limit=hrs)
render_section("Opmerkelijk", hours_limit=hrs)

st.caption("Voor de volledige (AI) samenvatting: open een bericht via 🔎 Open of klik op de titel.")
