import html
import streamlit as st

from common import CATEGORY_FEEDS, collect_items, within_hours, host, item_id, pretty_dt


def _pick_image(it: dict) -> str:
    return (it.get("image") or it.get("img") or "").strip()


def _pick_summary(it: dict) -> str:
    return (it.get("summary") or it.get("rss_summary") or it.get("description") or "").strip()


def _matches_query(it: dict, query: str | None) -> bool:
    if not query:
        return True
    q = query.strip().lower()
    hay = " ".join(
        [
            str(it.get("title") or ""),
            str(_pick_summary(it) or ""),
            str(it.get("link") or ""),
        ]
    ).lower()
    return q in hay


def _bookmark(it: dict) -> None:
    if "bookmarks" not in st.session_state:
        st.session_state.bookmarks = []
    bid = item_id(it)
    ids = {item_id(x) for x in st.session_state.bookmarks if isinstance(x, dict)}
    if bid not in ids:
        st.session_state.bookmarks.insert(0, it)


def _render_preview(it: dict) -> None:
    title = it.get("title") or "Zonder titel"
    link = it.get("link") or ""
    src = host(link)
    dt = pretty_dt(it.get("dt"))
    img = _pick_image(it)

    st.markdown(f"**{title}**")
    st.caption(f"{src} • {dt}")

    if img:
        try:
            st.image(img, use_container_width=True)
        except Exception:
            pass

    summary = _pick_summary(it)
    if summary:
        st.markdown(html.unescape(summary), unsafe_allow_html=True)
    else:
        st.caption("Geen previewtekst gevonden in deze feed.")

    cols = st.columns([1, 1, 1], gap="small")
    with cols[0]:
        if link:
            st.link_button("Open origineel", link, use_container_width=True)
    with cols[1]:
        if link:
            st.link_button("Lees in app", f"/Artikel?url={link}", use_container_width=True)
    with cols[2]:
        if st.button("⭐ Bewaar", key=f"bm_{item_id(it)}", use_container_width=True):
            _bookmark(it)
            st.toast("Bewaard ⭐")


def _safe_collect_items(feeds: list[str], query: str | None, max_items: int):
    out = collect_items(feeds, query=query, max_per_feed=25, max_items=max_items)
    if isinstance(out, tuple):
        items = out[0]
        stats = out[1] if len(out) > 1 else {}
    else:
        items = out
        stats = {}
    if not isinstance(items, list):
        items = []
    items = [x for x in items if isinstance(x, dict)]
    return items, stats


def render_section(
    title: str,
    hours_limit: int = 24,
    query: str | None = None,
    max_items: int = 60,
    thumbs_n: int = 4,
    feeds: list[str] | None = None,
) -> None:
    if feeds is None:
        feeds = CATEGORY_FEEDS.get(title, [])

    items, _stats = _safe_collect_items(feeds, query=query, max_items=max_items)

    items = [x for x in items if within_hours(x.get("dt"), hours_limit)]
    items = [x for x in items if _matches_query(x, query)]
    items = items[: max(0, int(max_items))]

    st.markdown('<div class="kbm-card">', unsafe_allow_html=True)
    st.markdown(f"### {title}")

    if not items:
        st.info("Geen berichten gevonden.")
        st.markdown("</div>", unsafe_allow_html=True)
        return

    top = items[: min(int(thumbs_n), len(items))]
    rest = items[min(int(thumbs_n), len(items)) :]

    st.markdown('<div class="kbm-grid">', unsafe_allow_html=True)

    for it in top:
        link = (it.get("link") or "").strip()
        img = _pick_image(it)
        src = host(link)
        dt_txt = pretty_dt(it.get("dt"))
        headline = it.get("title") or "Zonder titel"

        thumb = ""
        if img:
            thumb = f"<div class='kbm-thumb' style=\"background-image:url('{html.escape(img)}')\"></div>"

        st.markdown(
            f"""
<div class="kbm-item kbm-item--card">
  {thumb}
  <div class="kbm-item-inner">
    <div class="kbm-item-title"><a href="/Artikel?url={html.escape(link)}">{html.escape(headline)}</a></div>
    <div class="kbm-item-meta">{html.escape(src)} • {html.escape(dt_txt)}</div>
  </div>
</div>
""",
            unsafe_allow_html=True,
        )

        with st.expander("Lees preview", expanded=False):
            _render_preview(it)

    st.markdown("</div>", unsafe_allow_html=True)

    if rest:
        with st.expander("Meer berichten", expanded=False):
            for it in rest:
                link = (it.get("link") or "").strip()
                st.markdown(f"- [{it.get('title','Zonder titel')}](/Artikel?url={link})")
                st.caption(f"{host(link)} • {pretty_dt(it.get('dt'))}")

    st.markdown("</div>", unsafe_allow_html=True)
