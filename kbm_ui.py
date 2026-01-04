import html
import streamlit as st
from common import CATEGORY_FEEDS, collect_items, within_hours, host, item_id, pretty_dt

def article_url(src_url: str) -> str:
    return f"/Artikel?url={src_url}"

def _render_rss_html(s: str) -> None:
    """Render RSS summary as HTML inside Streamlit (best-effort).
    Many feeds include HTML tags; we unescape entities first.
    """
    if not s:
        return
    s = html.unescape(s)
    # Streamlit markdown accepts a subset of HTML when unsafe_allow_html=True.
    st.markdown(s, unsafe_allow_html=True)

def add_bookmark(it: dict):
    if "bookmarks" not in st.session_state:
        st.session_state.bookmarks = []
    ids = {b.get("id") for b in st.session_state.bookmarks}
    if it.get("id") in ids:
        return
    st.session_state.bookmarks.insert(0, {
        "id": it.get("id"),
        "title": it.get("title"),
        "link": it.get("link"),
        "dt": it.get("dt"),
    })

def render_item_preview(it: dict):
    cols = st.columns([0.62, 0.38], gap="small")

    with cols[0]:
        st.caption(f"{host(it.get('link',''))} • {pretty_dt(it.get('dt'))}")

    with cols[1]:
        b1, b2 = st.columns(2, gap="small")

        with b1:
            if st.button(
                "⭐ Lees later",
                key=f"bm_prev_{it['id']}_{it.get('source_label','')}_{it.get('dt','')}",
                use_container_width=True,
            ):
                add_bookmark(it)
                st.toast("Toegevoegd aan lees later ⭐")

        with b2:
            st.link_button(
                "🔎 Open",
                url=article_url(it.get("link", "")),
                use_container_width=True,
            )

    if it.get("img"):
        st.image(it["img"], use_container_width=True)

    if it.get("rss_summary"):
        st.markdown("**Korte preview (RSS):**")
        _render_rss_html(it["rss_summary"])
def render_section(cat_name: str, hours_limit: int | None, query: str | None, max_items: int = 40, thumbs_n: int = 4):
    feed_labels = CATEGORY_FEEDS.get(cat_name, [])
    items, _ = collect_items(feed_labels, query=query, max_per_feed=30)

    if hours_limit is not None:
        items = [x for x in items if within_hours(x.get("dt"), hours_limit)]

    if not items:
        st.info(f"Geen berichten voor **{cat_name}** (nu).") 
        return

    for it in items:
        it["id"] = item_id(it)

    hero = next((x for x in items if x.get("img")), items[0])
    rest = [x for x in items if x is not hero]
    thumbs = rest[:thumbs_n]
    more = rest[thumbs_n:max_items]

    st.markdown("<div class='kbm-card' style='margin-top:12px'>", unsafe_allow_html=True)
    st.markdown(f"### {cat_name}")

    colA, colB = st.columns([1.25, 0.75], gap="large")    

    with colA:
        if hero.get("img"):
            st.image(hero["img"], use_container_width=True)
        st.markdown(f"#### <a href='{article_url(hero['link'])}'>{hero['title']}</a>", unsafe_allow_html=True)
        st.markdown(f"<div class='kbm-meta'>{host(hero['link'])} • {pretty_dt(hero.get('dt'))}</div>", unsafe_allow_html=True)
        st.link_button("🔎 Open in KbM", url=article_url(hero["link"]), use_container_width=True)
        with st.expander("Lees preview", expanded=False):
            render_item_preview(hero)

    with colB:
        st.markdown("<div class='kbm-thumbs'>", unsafe_allow_html=True)
        for t in thumbs:
            dt_small = t["dt"].astimezone().strftime("%H:%M") if t.get("dt") else ""
            meta2 = f"{dt_small}{' • ' if dt_small else ''}{host(t['link'])}"
            img = t.get("img") or ""
            img_tag = f"<img class='kbm-thumbimg' src='{img}' alt='' />" if img else "<div class='kbm-thumbimg' aria-hidden='true'></div>"
            st.markdown(
                f"""
                <div class="kbm-thumbrow">
                  {img_tag}
                  <div class="kbm-thumbtext">
                    <p class="kbm-thumbtitle"><a href="{article_url(t['link'])}">{t['title']}</a></p>
                    <div class="kbm-thumbmeta">{meta2}</div>
                  </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            with st.expander("Lees preview", expanded=False):
                render_item_preview(t)
        st.markdown("</div>", unsafe_allow_html=True)

    if more:
        with st.expander("Meer berichten", expanded=False):
            for it in more:
                st.markdown(f"- [{it['title']}]({article_url(it['link'])})")
                st.caption(f"{host(it.get('link',''))} • {pretty_dt(it.get('dt'))}")

    st.markdown("</div>", unsafe_allow_html=True)
