
# kbm_ui.py — KbM Nieuws UI (hero + thumbnails, light theme)
from __future__ import annotations

import html
from typing import Any, Dict, List, Optional, Tuple

import streamlit as st

from common import CATEGORY_FEEDS, collect_items, within_hours, host, item_id, pretty_dt


# ----------------------------
# Styling (light, Montserrat)
# ----------------------------
_UI_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@400;600&display=swap');

html, body, [class*="css"]  {
  font-family: 'Montserrat', sans-serif !important;
}

.kbm-section { margin: 10px 0 24px 0; }
.kbm-h2 { font-size: 34px; font-weight: 600; margin: 10px 0 14px 0; color: #0b1220; }

.kbm-hero {
  position: relative;
  width: 100%;
  border-radius: 18px;
  overflow: hidden;
  border: 1px solid rgba(0,0,0,.06);
  box-shadow: 0 10px 26px rgba(0,0,0,.08);
  background: #f3f4f6;
}
.kbm-hero img { width: 100%; height: 240px; object-fit: cover; display:block; }
.kbm-hero .kbm-hero-fallback { height: 240px; background: linear-gradient(135deg,#e7e7e7,#f7f7f7); }

.kbm-hero .kbm-hero-overlay {
  position:absolute; left:0; right:0; bottom:0;
  padding: 14px 16px;
  background: linear-gradient(180deg, rgba(0,0,0,0) 0%, rgba(0,0,0,.55) 55%, rgba(0,0,0,.70) 100%);
}
.kbm-hero .kbm-hero-title {
  font-weight: 600;
  font-size: 22px;
  color: #fff;
  line-height: 1.18;
  text-shadow: 0 2px 8px rgba(0,0,0,.55);
}
.kbm-hero .kbm-hero-meta {
  margin-top: 6px;
  font-size: 12px;
  color: rgba(255,255,255,.9);
}

.kbm-list { margin-top: 14px; }
.kbm-row {
  display:flex; gap: 14px; align-items: center;
  padding: 12px 12px;
  border-radius: 14px;
  border: 1px solid rgba(0,0,0,.06);
  background: #ffffff;
  box-shadow: 0 6px 14px rgba(0,0,0,.06);
  margin-bottom: 12px;
}
.kbm-thumb {
  width: 68px; height: 68px; border-radius: 14px; overflow:hidden;
  flex: 0 0 68px; background:#eef0f3;
  border: 1px solid rgba(0,0,0,.06);
}
.kbm-thumb img { width: 100%; height:100%; object-fit: cover; display:block; }
.kbm-thumb .kbm-thumb-fallback { width:100%; height:100%; background: linear-gradient(135deg,#e7e7e7,#f7f7f7); }

.kbm-row-title { font-weight: 600; font-size: 16px; color:#0b1220; line-height:1.25; }
.kbm-row-meta { margin-top: 4px; font-size: 12px; color: #5b667a; }

.kbm-btnrow { margin-top: 10px; display:flex; gap: 10px; flex-wrap: wrap; }
.kbm-note { font-size: 12px; color: #5b667a; margin-top: 8px; }

@media (max-width: 520px) {
  .kbm-hero img, .kbm-hero .kbm-hero-fallback { height: 200px; }
  .kbm-h2 { font-size: 28px; }
}
</style>
"""

def _ensure_css() -> None:
    if not st.session_state.get("_kbm_css_done"):
        st.markdown(_UI_CSS, unsafe_allow_html=True)
        st.session_state["_kbm_css_done"] = True


def _pick_image(it: Dict[str, Any]) -> str:
    return (it.get("image") or it.get("img") or it.get("thumb") or "").strip()


def _pick_summary(it: Dict[str, Any]) -> str:
    return (it.get("summary") or it.get("rss_summary") or it.get("description") or "").strip()


def _matches_query(it: Dict[str, Any], query: str) -> bool:
    if not query:
        return True
    q = query.lower().strip()
    if not q:
        return True
    blob = (it.get("title","") + " " + _pick_summary(it)).lower()
    return q in blob


def _safe_markdown(text: str) -> str:
    # keep simple markup, strip overly long html
    t = html.unescape(text or "").strip()
    return t


def _render_article(it: Dict[str, Any], section_key: str) -> None:
    # inline "artikel" view (no expander)
    title = (it.get("title") or "Onbekende titel").strip()
    link = (it.get("link") or "").strip()
    src = host(link)
    dt = pretty_dt(it.get("dt"))
    img = _pick_image(it)

    st.markdown(f"### {title}")
    st.caption(f"{src} • {dt}")

    if img:
        try:
            st.image(img, use_container_width=True)
        except Exception:
            pass

    summary = _pick_summary(it)
    if summary:
        st.markdown(_safe_markdown(summary), unsafe_allow_html=True)
    else:
        st.caption("Geen previewtekst gevonden in deze feed.")

    c1, c2 = st.columns([1,1], gap="small")
    with c1:
        if link:
            st.link_button("Open origineel", link, use_container_width=True)
    with c2:
        st.button("Sluit", key=f"close_{section_key}_{item_id(it)}", use_container_width=True, on_click=lambda: st.session_state.__setitem__(f"open_{section_key}", ""))


def render_section(
    category: str,
    *,
    hours_limit: Optional[int] = None,
    query: str = "",
    max_items: int = 80,
    thumbs_n: int = 4,
    feed_labels: Optional[List[str]] = None,
) -> None:
    """
    Renders one block in the desired style:
    - 1 hero item with image + title overlay
    - N list rows with thumbnail + title
    Clicking an item opens an inline article view (no per-item expander).
    """
    _ensure_css()

    labels = feed_labels or CATEGORY_FEEDS.get(category, [])
    if not labels:
        st.info(f"Geen feeds ingesteld voor {category}.")
        return

    items, _meta = collect_items(labels, query=None, max_items=max_items)
    if hours_limit:
        items = [x for x in items if within_hours(x.get("dt"), hours_limit)]

    # optional query filter (after collect)
    if query:
        items = [x for x in items if _matches_query(x, query)]

    if not items:
        st.caption("Geen berichten gevonden.")
        return

    section_key = category.lower().replace(" ", "_")
    st.markdown(f'<div class="kbm-section"><div class="kbm-h2">{category}</div></div>', unsafe_allow_html=True)

    # hero
    hero = items[0]
    hero_title = html.escape((hero.get("title") or "").strip() or "Onbekend")
    hero_link = (hero.get("link") or "").strip()
    hero_src = html.escape(host(hero_link))
    hero_dt = html.escape(pretty_dt(hero.get("dt")))
    hero_img = _pick_image(hero)

    if hero_img:
        hero_html = f"""
        <div class="kbm-hero">
          <img src="{html.escape(hero_img)}" />
          <div class="kbm-hero-overlay">
            <div class="kbm-hero-title">{hero_title}</div>
            <div class="kbm-hero-meta">{hero_src} • {hero_dt}</div>
          </div>
        </div>
        """
    else:
        hero_html = f"""
        <div class="kbm-hero">
          <div class="kbm-hero-fallback"></div>
          <div class="kbm-hero-overlay">
            <div class="kbm-hero-title">{hero_title}</div>
            <div class="kbm-hero-meta">{hero_src} • {hero_dt}</div>
          </div>
        </div>
        """
    st.markdown(hero_html, unsafe_allow_html=True)

    # hero click -> open inline
    if st.button("Lees in app", key=f"openhero_{section_key}_{item_id(hero)}", use_container_width=True):
        st.session_state[f"open_{section_key}"] = item_id(hero)

    # list
    st.markdown('<div class="kbm-list">', unsafe_allow_html=True)
    for it in items[1:1+thumbs_n]:
        it_title = html.escape((it.get("title") or "").strip() or "Onbekend")
        it_link = (it.get("link") or "").strip()
        it_src = html.escape(host(it_link))
        it_dt = html.escape(pretty_dt(it.get("dt")))
        it_img = _pick_image(it)
        if it_img:
            thumb = f'<div class="kbm-thumb"><img src="{html.escape(it_img)}" /></div>'
        else:
            thumb = '<div class="kbm-thumb"><div class="kbm-thumb-fallback"></div></div>'

        row_html = f"""
        <div class="kbm-row">
          {thumb}
          <div style="flex: 1 1 auto;">
            <div class="kbm-row-title">{it_title}</div>
            <div class="kbm-row-meta">{it_src} • {it_dt}</div>
          </div>
        </div>
        """
        st.markdown(row_html, unsafe_allow_html=True)

        if st.button("Lees in app", key=f"open_{section_key}_{item_id(it)}"):
            st.session_state[f"open_{section_key}"] = item_id(it)

    st.markdown("</div>", unsafe_allow_html=True)

    # inline open item
    open_id = st.session_state.get(f"open_{section_key}", "")
    if open_id:
        chosen = next((x for x in items if item_id(x) == open_id), None)
        if chosen:
            st.divider()
            _render_article(chosen, section_key)
