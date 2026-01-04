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
    st.markdown(s, unsafe_allow_html=True)


def _bookmark(it: dict) -> None:
    """Add item to session bookmark list (id-based)."""
    if "bookmarks" not in st.session_state:
        st.session_state.bookmarks = []
    bid = item_id(it)
    ids = {item_id(x) for x in st.session_state.bookmarks}
    if bid in ids:
        return
    st.session_state.bookmarks.insert(0, it)


def render_item_preview(it: dict) -> None:
    """Compact preview inside expander."""
    title = it.get("title") or "Zonder titel"
    link = it.get("link") or ""
    src = host(link)
    dt = pretty_dt(it.get("dt"))
    img = it.get("image") or ""

    st.markdown(f"**{title}**")
    st.caption(f"{src} • {dt}")

    if img:
        try:
            st.image(img, use_container_width=True)
        except Exception:
            pass

    summary = it.get("summary") or it.get("description") or ""
    if summary:
        _render_rss_html(summary)

    cols = st.columns([1, 1, 1], gap="small")
    with cols[0]:
        if link:
            st.link_button("Open origineel", link, use_container_width=True)
    with cols[1]:
        if link:
            st.link_button("Lees in app", article_url(link), use_container_width=True)
    with cols[2]:
        if st.button("⭐ Bewaar", key=f"bm_{item_id(it)}", use_container_width=True):
            _bookmark(it)
            st.toast("Bewaard ⭐")


def render_section(
    title: str,
    feeds: list[str] | None = None,
    hours: int = 48,
    limit: int = 25,
    compact: bool = False,
    show_images: bool = True,
) -> None:
    """Render one news section from a set of feeds."""
    if feeds is None:
        feeds = CATEGORY_FEEDS.get(title, [])

    st.markdown('<div class="kbm-card">', unsafe_allow_html=True)
    st.markdown(f"### {title}")

    items = collect_items(feeds)
    items = [x for x in items if within_hours(x.get("dt"), hours)]
    items = items[: max(0, int(limit))]

    if not items:
        st.info("Geen berichten gevonden (of te oud).")
        st.markdown("</div>", unsafe_allow_html=True)
        return

    top = items[: min(6, len(items))]
    more = items[6:] if len(items) > 6 else []

    st.markdown('<div class="kbm-grid">', unsafe_allow_html=True)

    for it in top:
        link = it.get("link") or ""
        img = it.get("image") or ""
        src = host(link)
        dt = pretty_dt(it.get("dt"))
        headline = it.get("title") or "Zonder titel"

        if compact:
            st.markdown(
                f"""
<div class="kbm-item">
  <div class="kbm-item-inner">
    <div class="kbm-item-title"><a href="{article_url(link)}">{html.escape(headline)}</a></div>
    <div class="kbm-item-meta">{html.escape(src)} • {html.escape(dt)}</div>
  </div>
</div>
""",
                unsafe_allow_html=True,
            )
        else:
            thumb = ""
            if show_images and img:
                thumb = f"""
<div class="kbm-thumb" style="background-image:url('{html.escape(img)}')"></div>
"""
            st.markdown(
                f"""
<div class="kbm-item kbm-item--card">
  {thumb}
  <div class="kbm-item-inner">
    <div class="kbm-item-title"><a href="{article_url(link)}">{html.escape(headline)}</a></div>
    <div class="kbm-item-meta">{html.escape(src)} • {html.escape(dt)}</div>
  </div>
</div>
""",
                unsafe_allow_html=True,
            )
            with st.expander("Lees preview", expanded=False):
                render_item_preview(it)

    st.markdown("</div>", unsafe_allow_html=True)

    if more:
        with st.expander("Meer berichten", expanded=False):
            for it in more:
                st.markdown(f"- [{it.get('title','Zonder titel')}]({article_url(it.get('link',''))})")
                st.caption(f"{host(it.get('link',''))} • {pretty_dt(it.get('dt'))}")

    st.markdown("</div>", unsafe_allow_html=True)
