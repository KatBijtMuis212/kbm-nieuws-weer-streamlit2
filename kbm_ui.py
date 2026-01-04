# kbm_ui.py — KbM Nieuws UI (hero + thumbs, light theme, safe keys)
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
import re
import streamlit as st

from common import (
    CATEGORY_FEEDS,
    collect_items,
    within_hours,
    host,
    item_id,
    fetch_art,
    pre,
)

# -----------------------------
# Helpers
# -----------------------------

def _slug(s: str) -> str:
    s = (s or "").strip().lower()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    return s.strip("_") or "sec"

def _pick_image(it: Dict[str, Any]) -> str:
    return (it.get("image") or it.get("img") or it.get("thumb") or it.get("enclosure") or "").strip()

def _pick_title(it: Dict[str, Any]) -> str:
    return (it.get("title") or "").strip()

def _pick_link(it: Dict[str, Any]) -> str:
    return (it.get("link") or "").strip()

def _pick_dt_label(it: Dict[str, Any]) -> str:
    # keep it simple: show already formatted dt_label if available
    return (it.get("dt_label") or it.get("pub") or it.get("date") or "").strip()

def _safe_text(s: str) -> str:
    return (s or "").replace("\x00", "").strip()

def _matches_query(it: Dict[str, Any], query: str) -> bool:
    q = (query or "").strip().lower()
    if not q:
        return True
    hay = " ".join([
        _pick_title(it),
        _pick_link(it),
        str(it.get("source") or ""),
        str(it.get("host") or ""),
    ]).lower()
    return q in hay

def _dedup(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen: set[str] = set()
    out: List[Dict[str, Any]] = []
    for it in items:
        iid = _safe_text(item_id(it)) or _safe_text(_pick_link(it)) or _safe_text(_pick_title(it))
        if not iid:
            # last resort: hash title+link
            iid = str(hash((_pick_title(it), _pick_link(it))))
        if iid in seen:
            continue
        seen.add(iid)
        out.append(it)
    return out

# Binnenland / Buitenland heuristics (light touch, avoids obvious misplacements)
_FOREIGN_MARKERS = [
    "/buitenland", "/international", "/world", "/wereld", "/foreign",
    "brussel", "brussels", "eu-", "europa", "griekenland", "greece",
    "curaçao", "curacao", "verenigde staten", "vs", "ukraine", "rusland", "china",
]
_DOMESTIC_MARKERS = [
    "/binnenland", "/net-binnen", "/politiek", "/economie", "/sport", "/tech",
    "den haag", "amsterdam", "rotterdam", "utrecht", "groningen", "friesland",
    "noord-holland", "zuid-holland", "gelderland", "brabant", "limburg", "zeeland",
]

def _filter_binnen_buiten(category: str, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    cat = (category or "").strip().lower()
    if cat not in ("binnenland", "buitenland"):
        return items

    def score(it: Dict[str, Any]) -> Tuple[int, int]:
        # returns (domestic_score, foreign_score)
        t = (_pick_title(it) + " " + _pick_link(it)).lower()
        d = sum(1 for m in _DOMESTIC_MARKERS if m in t)
        f = sum(1 for m in _FOREIGN_MARKERS if m in t)
        return d, f

    filtered: List[Dict[str, Any]] = []
    for it in items:
        d, f = score(it)
        if cat == "binnenland":
            # drop obvious foreign
            if f >= 1 and d == 0:
                continue
            filtered.append(it)
        else:
            # buitenland: prefer foreign, but allow if feed clearly is foreign category
            if d >= 1 and f == 0:
                continue
            filtered.append(it)

    return filtered

# -----------------------------
# CSS
# -----------------------------

def _ensure_css() -> None:
    if st.session_state.get("_kbm_ui_css_done"):
        return
    st.markdown(
        """
<style>
/* Light baseline */
.kbm-block { margin: 8px 0 18px 0; }
.kbm-hero { position: relative; border-radius: 16px; overflow: hidden; border: 1px solid rgba(0,0,0,.08); }
.kbm-hero img { width: 100%; height: 220px; object-fit: cover; display:block; }
.kbm-hero .kbm-hero-overlay {
  position:absolute; left:0; right:0; bottom:0;
  padding: 14px 14px 12px 14px;
  background: linear-gradient(180deg, rgba(0,0,0,0) 0%, rgba(0,0,0,.70) 55%, rgba(0,0,0,.80) 100%);
}
.kbm-hero .kbm-hero-title { color: #fff; font-weight: 700; font-size: 22px; line-height: 1.2; margin: 0; }
.kbm-hero .kbm-hero-meta { color: rgba(255,255,255,.92); font-size: 13px; margin-top: 4px; }

.kbm-row { display:flex; gap: 12px; align-items: center; padding: 10px 10px; border-radius: 14px; border: 1px solid rgba(0,0,0,.08); background: #fff; margin-top: 10px; }
.kbm-thumb { width: 68px; height: 68px; border-radius: 12px; background: #e9edf2; overflow:hidden; flex: 0 0 auto; border: 1px solid rgba(0,0,0,.06); }
.kbm-thumb img { width: 100%; height: 100%; object-fit: cover; display:block; }
.kbm-row .kbm-txt { flex: 1 1 auto; min-width: 0; }
.kbm-row .kbm-title { font-weight: 700; font-size: 16px; line-height: 1.25; color: #0b1220; margin: 0; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
.kbm-row .kbm-meta { margin-top: 4px; font-size: 12px; color: rgba(11,18,32,.62); }

.kbm-article { margin-top: 12px; padding: 12px 12px; border-radius: 14px; border: 1px solid rgba(0,0,0,.08); background:#fff; }
.kbm-article h3 { margin: 0 0 6px 0; }
</style>
        """,
        unsafe_allow_html=True,
    )
    st.session_state["_kbm_ui_css_done"] = True

# -----------------------------
# Article view
# -----------------------------

def _render_article(section_key: str, it: Dict[str, Any]) -> None:
    title = _pick_title(it)
    link = _pick_link(it)
    src = host(link) if link else (it.get("host") or it.get("source") or "")
    dt = _pick_dt_label(it)

    st.markdown('<div class="kbm-article">', unsafe_allow_html=True)
    st.markdown(f"### {title}")
    if src or dt:
        st.caption(" • ".join([x for x in [str(src).strip(), str(dt).strip()] if x]))
    c1, c2 = st.columns([1, 1], gap="small")
    with c1:
        if link:
            st.link_button("Open origineel", link, use_container_width=True)
    with c2:
        st.button(
            "Sluit",
            key=f"close_{section_key}",
            use_container_width=True,
            on_click=lambda: st.session_state.__setitem__(f"open_{section_key}", ""),
        )

    # Try to fetch full article (best-effort)
    if link:
        try:
            art = fetch_art(link)
        except Exception as e:
            art = {"ok": False, "text": "", "html": "", "error": str(e)}
        if art and art.get("ok"):
            txt = (art.get("text") or "").strip()
            if txt:
                st.write(txt)
            else:
                html = (art.get("html") or "").strip()
                if html:
                    st.markdown(html, unsafe_allow_html=True)
                else:
                    st.caption("Geen artikeltekst gevonden.")
        else:
            st.caption("Dit artikel kon niet volledig uitgelezen worden (mogelijk JS/consent).")
    st.markdown("</div>", unsafe_allow_html=True)

# -----------------------------
# Main render
# -----------------------------

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
    Render one category block:
    - 1 hero (image + title overlay)
    - thumbs_n list items with thumbnail + title
    Clicking opens an inline article view (no per-item expander).
    """
    _ensure_css()

    labels = feed_labels or CATEGORY_FEEDS.get(category, [])
    if not labels:
        st.info(f"Geen feeds ingesteld voor {category}.")
        return

    items, _meta = collect_items(labels, query=None, max_items=max_items)
    items = _dedup(items)
    items = _filter_binnen_buiten(category, items)

    if hours_limit:
        items = [x for x in items if within_hours(x.get("dt"), hours_limit)]
    if query:
        items = [x for x in items if _matches_query(x, query)]

    if not items:
        st.caption("Geen resultaten.")
        return

    section_key = _slug(category)

    # Keep an "open item" per section
    open_key = f"open_{section_key}"
    if open_key not in st.session_state:
        st.session_state[open_key] = ""

    hero = items[0]
    hero_img = _pick_image(hero)
    hero_title = _pick_title(hero)
    hero_link = _pick_link(hero)

    # HERO
    if hero_img:
        st.markdown('<div class="kbm-hero">', unsafe_allow_html=True)
        st.markdown(f'<img src="{hero_img}">', unsafe_allow_html=True)
        meta = " • ".join([x for x in [host(hero_link), _pick_dt_label(hero)] if x])
        st.markdown(
            f'<div class="kbm-hero-overlay"><div class="kbm-hero-title">{hero_title}</div>'
            f'<div class="kbm-hero-meta">{meta}</div></div>',
            unsafe_allow_html=True,
        )
        st.markdown("</div>", unsafe_allow_html=True)
    else:
        # no image: just title
        st.subheader(hero_title)

    # Hero buttons
    b1, b2 = st.columns([1, 1], gap="small")
    with b1:
        if hero_link:
            st.link_button("Open origineel", hero_link, use_container_width=True)
    with b2:
        st.button(
            "Lees in app",
            key=f"open_{section_key}_hero_{item_id(hero)}_0",
            use_container_width=True,
            on_click=lambda iid=item_id(hero): st.session_state.__setitem__(open_key, iid),
        )

    # THUMBS LIST (next N items)
    for i, it in enumerate(items[1:1 + max(0, thumbs_n)], start=1):
        img = _pick_image(it)
        title = _pick_title(it)
        link = _pick_link(it)
        meta = " • ".join([x for x in [host(link), _pick_dt_label(it)] if x])

        st.markdown('<div class="kbm-row">', unsafe_allow_html=True)
        if img:
            st.markdown(f'<div class="kbm-thumb"><img src="{img}"></div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="kbm-thumb"></div>', unsafe_allow_html=True)
        st.markdown(
            f'<div class="kbm-txt"><div class="kbm-title">{title}</div><div class="kbm-meta">{meta}</div></div>',
            unsafe_allow_html=True,
        )
        st.markdown("</div>", unsafe_allow_html=True)

        c1, c2 = st.columns([1, 1], gap="small")
        with c1:
            if link:
                st.link_button("Open origineel", link, use_container_width=True, key=f"orig_{section_key}_{item_id(it)}_{i}")
        with c2:
            st.button(
                "Lees in app",
                key=f"open_{section_key}_{item_id(it)}_{i}",
                use_container_width=True,
                on_click=lambda iid=item_id(it): st.session_state.__setitem__(open_key, iid),
            )

    # Article view (if selected)
    opened = st.session_state.get(open_key) or ""
    if opened:
        # find matching item in current slice or in full list
        it = next((x for x in items if item_id(x) == opened), None)
        if it:
            _render_article(section_key, it)
        else:
            st.session_state[open_key] = ""
