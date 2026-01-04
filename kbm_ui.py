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
    st.session_state.setdefault("bookmarks", [])
    bid = item_id(it)
    ids = {item_id(x) for x in st.session_state.bookmarks if isinstance(x, dict)}
    if bid not in ids:
        st.session_state.bookmarks.insert(0, it)


def _safe_collect_items(feeds: list[str], query: str | None, max_items: int):
    out = collect_items(feeds, query=query, max_items=max_items)
    if isinstance(out, tuple):
        items = out[0]
    else:
        items = out
    if not isinstance(items, list):
        items = []
    items = [x for x in items if isinstance(x, dict)]
    return items


def _ensure_css_once():
    if st.session_state.get("_kbm_css_done"):
        return
    st.session_state["_kbm_css_done"] = True

    st.markdown(
        """
<style>
/* --- KBM Block layout (Hero + 4 rows) --- */
.kbm-block{
  margin: 0 0 26px 0;
  background: #0b0f14;
  border-radius: 18px;
  overflow: hidden;
  box-shadow: 0 10px 30px rgba(0,0,0,.22);
  border: 1px solid rgba(255,255,255,.06);
}

.kbm-block__title{
  font-size: 42px;
  font-weight: 900;
  letter-spacing: .5px;
  text-transform: uppercase;
  color: #ffffff;
  padding: 18px 18px 10px 18px;
}

.kbm-hero{
  position: relative;
  height: 270px;
  background: #111;
  background-size: cover;
  background-position: center;
}

.kbm-hero__shade{
  position:absolute; inset:0;
  background: linear-gradient(180deg, rgba(0,0,0,0) 42%, rgba(0,0,0,.85) 100%);
}

.kbm-hero__bar{
  position:absolute; left:0; right:0; bottom:0;
  padding: 14px 16px;
}

.kbm-hero__title a{
  color:#fff;
  text-decoration:none;
  font-size: 28px;
  font-weight: 900;
  line-height: 1.1;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.kbm-hero__meta{
  margin-top: 6px;
  color: rgba(255,255,255,.78);
  font-size: 14px;
}

.kbm-list{
  padding: 8px 0 10px 0;
}

.kbm-row{
  display:flex;
  gap: 14px;
  padding: 12px 18px;
  border-top: 1px solid rgba(255,255,255,.06);
  align-items: center;
}

.kbm-row:hover{
  background: rgba(255,255,255,.03);
}

.kbm-thumb{
  width: 92px;
  height: 92px;
  border-radius: 14px;
  background: rgba(255,255,255,.06);
  overflow: hidden;
  flex: 0 0 auto;
  border: 1px solid rgba(255,255,255,.08);
}

.kbm-thumb img{
  width:100%;
  height:100%;
  object-fit: cover;
  display:block;
}

.kbm-row__title a{
  color:#fff;
  text-decoration:none;
  font-size: 22px;
  font-weight: 900;
  line-height: 1.15;
  display: -webkit-box;
  -webkit-line-clamp: 2;  /* max 2 regels */
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.kbm-row__meta{
  margin-top: 6px;
  color: rgba(255,255,255,.70);
  font-size: 13px;
}

.kbm-actions{
  padding: 0 18px 16px 18px;
}

.kbm-actions .stButton button{
  width: 100%;
}

.kbm-expander-fix [data-testid="stExpander"]{
  border-color: rgba(255,255,255,.10) !important;
  background: rgba(255,255,255,.02) !important;
}
</style>
        """,
        unsafe_allow_html=True,
    )


def _card_link(title: str, link: str) -> str:
    safe_title = html.escape(title or "Zonder titel")
    safe_link = html.escape(link or "")
    return f'<a href="/Artikel?url={safe_link}">{safe_title}</a>'


def _render_preview(it: dict, section_key: str, idx: int):
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
        if st.button("⭐ Bewaar", key=f"bm_{section_key}_{idx}_{item_id(it)}", use_container_width=True):
            _bookmark(it)
            st.toast("Bewaard ⭐")


def render_section(
    title: str,
    hours_limit: int = 24,
    query: str | None = None,
    max_items: int = 60,
    thumbs_n: int = 4,
    feeds: list[str] | None = None,
) -> None:
    _ensure_css_once()

    if feeds is None:
        feeds = CATEGORY_FEEDS.get(title, [])

    section_key = title.lower().replace(" ", "_").replace("&", "and")
    items = _safe_collect_items(feeds, query=query, max_items=max_items)

    items = [x for x in items if within_hours(x.get("dt"), hours_limit)]
    items = [x for x in items if _matches_query(x, query)]
    items = items[: max(0, int(max_items))]

    if not items:
        st.info(f"{title}: geen berichten gevonden.")
        return

    # Hero = liefst eerste met image
    hero_idx = 0
    for i, it in enumerate(items[:12]):
        if _pick_image(it):
            hero_idx = i
            break
    hero = items.pop(hero_idx)

    hero_img = _pick_image(hero)
    hero_title = hero.get("title") or "Zonder titel"
    hero_link = hero.get("link") or ""
    hero_meta = f"{host(hero_link)} • {pretty_dt(hero.get('dt'))}"

    # Thumbs = volgende 4 (of minder)
    thumbs_n = max(0, int(thumbs_n))
    thumbs = items[:thumbs_n]
    rest = items[thumbs_n:]

    # ---------- BLOCK HTML ----------
    st.markdown('<div class="kbm-block">', unsafe_allow_html=True)
    st.markdown(f'<div class="kbm-block__title">{html.escape(title)}</div>', unsafe_allow_html=True)

    hero_bg = html.escape(hero_img) if hero_img else ""
    hero_style = f"background-image:url('{hero_bg}');" if hero_bg else "background:#111;"

    st.markdown(
        f"""
<div class="kbm-hero" style="{hero_style}">
  <div class="kbm-hero__shade"></div>
  <div class="kbm-hero__bar">
    <div class="kbm-hero__title">{_card_link(hero_title, hero_link)}</div>
    <div class="kbm-hero__meta">{html.escape(hero_meta)}</div>
  </div>
</div>
        """,
        unsafe_allow_html=True,
    )

    # Thumb rows
    st.markdown('<div class="kbm-list">', unsafe_allow_html=True)

    # Als thumbnail geen image heeft: gewoon leeg blok (zoals je wireframe)
    for idx, it in enumerate(thumbs):
        t = it.get("title") or "Zonder titel"
        link = it.get("link") or ""
        meta = f"{host(link)} • {pretty_dt(it.get('dt'))}"
        img = _pick_image(it)

        thumb_html = (
            f"<div class='kbm-thumb'><img src='{html.escape(img)}' loading='lazy' /></div>"
            if img
            else "<div class='kbm-thumb'></div>"
        )

        st.markdown(
            f"""
<div class="kbm-row">
  {thumb_html}
  <div class="kbm-row__body">
    <div class="kbm-row__title">{_card_link(t, link)}</div>
    <div class="kbm-row__meta">{html.escape(meta)}</div>
  </div>
</div>
            """,
            unsafe_allow_html=True,
        )

        # Preview onder elke row (expander)
        with st.container():
            st.markdown('<div class="kbm-expander-fix">', unsafe_allow_html=True)
            with st.expander("Lees preview", expanded=False):
                _render_preview(it, section_key, idx)
            st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)  # kbm-list

    # Meer berichten (optioneel)
    if rest:
        with st.expander("Meer berichten", expanded=False):
            for i, it in enumerate(rest):
                link = (it.get("link") or "").strip()
                t = it.get("title") or "Zonder titel"
                st.markdown(f"- [{t}](/Artikel?url={link})")
                st.caption(f"{host(link)} • {pretty_dt(it.get('dt'))}")

    st.markdown("</div>", unsafe_allow_html=True)  # kbm-block
