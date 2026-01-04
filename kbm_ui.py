# kbm_ui.py — UI renderer for KbM Nieuws (stable keys, hero+thumb layout, light theme)
from __future__ import annotations

import html
import re
from typing import Any, Dict, List, Optional

import streamlit as st

# Import common as a module to avoid ImportError when one symbol is missing
import common as cm


# ---------- small helpers ----------
def _get(name: str, default: Any = None) -> Any:
    return getattr(cm, name, default)


def _host(url: str) -> str:
    fn = _get("host")
    try:
        return fn(url) if callable(fn) else ""
    except Exception:
        return ""


def _item_id(it: dict, fallback: str) -> str:
    fn = _get("item_id")
    try:
        v = fn(it) if callable(fn) else None
    except Exception:
        v = None
    v = (v or "").strip()
    return v or fallback


def _pretty_dt(dt: Any) -> str:
    fn = _get("pretty_dt")
    try:
        return fn(dt) if callable(fn) else ""
    except Exception:
        return ""


def _within_hours(dt: Any, hours: int) -> bool:
    fn = _get("within_hours")
    try:
        return fn(dt, hours) if callable(fn) else True
    except Exception:
        return True


def _pick_image(it: dict) -> str:
    return (it.get("image") or it.get("img") or it.get("thumb") or it.get("thumbnail") or "").strip()


def _pick_summary(it: dict) -> str:
    return (it.get("summary") or it.get("rss_summary") or it.get("description") or "").strip()


def _section_key(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", (name or "").strip().lower()).strip("_") or "sec"


# ---------- filtering Binnenland/Buitenland sanity ----------
_FOREIGN_HINTS = [
    "grieken", "turk", "curacao", "curaçao", "brussel", "brussels",
    "duits", "frankrijk", "spanje", "ital", "verenigde staten", "washington",
    "iran", "israel", "israël", "gaza", "ukraine", "oekra", "rusland",
    "china", "japan", "india", "syrie", "syrië", "afghan", "mexic",
    "venez", "argentin", "brazil", "nigeria", "kenia", "australi"
]
def _looks_foreign(it: dict) -> bool:
    url = (it.get("link") or it.get("url") or "").lower()
    title = (it.get("title") or "").lower()
    txt = f"{title} {url}"
    if "/buitenland" in url or "/world" in url or "/international" in url:
        return True
    return any(h in txt for h in _FOREIGN_HINTS)

def _section_filter(section_name: str, items: List[dict]) -> List[dict]:
    s = (section_name or "").lower()
    if "binnenland" in s:
        # remove obvious buitenland
        return [it for it in items if not _looks_foreign(it)]
    if "buitenland" in s:
        # keep only likely foreign when mixed feeds leak
        return [it for it in items if _looks_foreign(it) or "/buitenland" in (it.get("link") or "").lower()]
    return items


# ---------- article thumbnail/og:image best-effort ----------
@st.cache_data(show_spinner=False, ttl=6 * 60 * 60)
def _og_image(url: str) -> str:
    """Fetch og:image from article page (best-effort). Requires requests+bs4 in common."""
    fn = _get("fetch_article_media")
    try:
        if callable(fn):
            media = fn(url)  # expected dict with 'image' maybe
            if isinstance(media, dict):
                img = (media.get("image") or media.get("og_image") or "").strip()
                if img:
                    return img
    except Exception:
        pass
    return ""


def _ensure_images(items: List[dict]) -> List[dict]:
    out = []
    for it in items:
        if not _pick_image(it):
            url = it.get("link") or it.get("url") or ""
            if url:
                img = _og_image(url)
                if img:
                    it = dict(it)
                    it["image"] = img
        out.append(it)
    return out


# ---------- rendering ----------
def _inject_montserrat():
    st.markdown(
        """
<style>
@import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@400;600;700&display=swap');
html, body, [class*="css"]  { font-family: 'Montserrat', sans-serif !important; }
.kbm-hero { position: relative; border-radius: 18px; overflow: hidden; margin: 10px 0 14px 0; }
.kbm-hero img { width: 100%; height: 240px; object-fit: cover; display:block; }
.kbm-hero .overlay {
  position:absolute; left:0; right:0; bottom:0;
  padding: 14px 16px;
  background: linear-gradient(180deg, rgba(0,0,0,0.0), rgba(0,0,0,0.65));
  color: #fff;
}
.kbm-hero .overlay .t { font-weight: 700; font-size: 28px; line-height: 1.1; margin: 0; }
.kbm-hero .overlay .m { opacity: .92; font-size: 14px; margin-top: 6px; }

.kbm-row { display:flex; gap:14px; align-items:center; padding: 10px 0; border-bottom: 1px solid rgba(0,0,0,.08);}
.kbm-thumb { width: 72px; height: 72px; border-radius: 14px; object-fit: cover; background: #eee; flex: 0 0 72px;}
.kbm-title { font-weight: 600; font-size: 18px; line-height: 1.2; margin: 0; color: #111; }
.kbm-meta { font-size: 13px; opacity: .70; margin-top: 2px; color: #111; }
.kbm-actions { display:flex; gap:8px; margin-top: 8px;}
.kbm-actions button { width: 100%; }
</style>
        """,
        unsafe_allow_html=True,
    )


def render_section(section_name: str, hours_limit: int = 6, query: Optional[str] = None,
                   max_items: int = 60, thumbs_n: int = 4):
    """
    Render one news section:
    - HERO (1 item) + THUMB LIST (thumbs_n items)
    - Remaining items shown as compact list with "Lees preview" toggle
    """
    _inject_montserrat()

    section_key = _section_key(section_name)

    # Collect items
    collect = _get("collect_items")
    catfeeds = _get("CATEGORY_FEEDS", {})
    feeds = catfeeds.get(section_name, []) if isinstance(catfeeds, dict) else []
    if not callable(collect):
        st.error("collect_items ontbreekt in common.py")
        return

    items = collect(feeds, query=query, max_items=max_items)

    # Time filter
    if hours_limit:
        items = [x for x in items if _within_hours(x.get("dt"), hours_limit)]

    # Binnenland/Buitenland sanity
    items = _section_filter(section_name, items)

    # Dedup by item_id
    seen = set()
    deduped = []
    for i, it in enumerate(items):
        iid = _item_id(it, f"{section_key}_{i}")
        if iid in seen:
            continue
        seen.add(iid)
        deduped.append(it)
    items = deduped

    # Fill images for hero/thumbs (best-effort)
    items = _ensure_images(items)

    st.markdown(f"## {html.escape(section_name)}")

    if not items:
        st.caption("Geen berichten gevonden.")
        return

    hero = items[0]
    rest = items[1:]

    # HERO
    hero_img = _pick_image(hero)
    hero_title = (hero.get("title") or "Onbekende titel").strip()
    hero_url = hero.get("link") or hero.get("url") or ""
    hero_meta = f"{_host(hero_url)} • {_pretty_dt(hero.get('dt'))}".strip(" •")

    if hero_img:
        st.markdown(
            f"""
<div class="kbm-hero">
  <img src="{html.escape(hero_img)}" alt="hero">
  <div class="overlay">
    <div class="t">{html.escape(hero_title)}</div>
    <div class="m">{html.escape(hero_meta)}</div>
  </div>
</div>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.subheader(hero_title)
        st.caption(hero_meta)

    # Hero actions
    c1, c2 = st.columns([1, 1])
    with c1:
        if hero_url:
            st.link_button("Open origineel", hero_url, use_container_width=True)
    with c2:
        # route to article page (if you have one), else open original
        st.link_button("Lees in app", hero_url, use_container_width=True)

    # THUMB TOP LIST
    top = rest[:thumbs_n]
    for idx, it in enumerate(top):
        url = it.get("link") or it.get("url") or ""
        img = _pick_image(it)
        title = (it.get("title") or "Onbekende titel").strip()
        meta = f"{_host(url)} • {_pretty_dt(it.get('dt'))}".strip(" •")
        st.markdown(
            f"""
<div class="kbm-row">
  <img class="kbm-thumb" src="{html.escape(img) if img else ''}" alt="">
  <div style="flex:1;">
    <div class="kbm-title">{html.escape(title)}</div>
    <div class="kbm-meta">{html.escape(meta)}</div>
  </div>
</div>
            """,
            unsafe_allow_html=True,
        )
        bcols = st.columns([1, 1, 1])
        # Unique keys: include section_key + idx + item_id fallback
        iid = _item_id(it, f"{section_key}_top_{idx}")
        with bcols[0]:
            if url:
                st.link_button("Open origineel", url, use_container_width=True, key=f"orig_{section_key}_{idx}_{iid}")
        with bcols[1]:
            if url:
                st.link_button("Lees in app", url, use_container_width=True, key=f"open_{section_key}_{idx}_{iid}")
        with bcols[2]:
            st.button("⭐ Bewaar", key=f"save_{section_key}_{idx}_{iid}", use_container_width=True)

    # Remaining list (compact)
    if len(rest) > thumbs_n:
        st.markdown("### Meer berichten")
        for j, it in enumerate(rest[thumbs_n:]):
            url = it.get("link") or it.get("url") or ""
            title = (it.get("title") or "Onbekende titel").strip()
            meta = f"{_host(url)} • {_pretty_dt(it.get('dt'))}".strip(" •")
            iid = _item_id(it, f"{section_key}_more_{j}")
            st.markdown(f"**{html.escape(title)}**  \n{html.escape(meta)}")
            show = st.toggle("Lees preview", key=f"pv_{section_key}_{j}_{iid}")
            if show:
                summary = _pick_summary(it)
                if not summary and url:
                    # fallback: try fetch readable
                    fr = _get("fetch_readable_text")
                    try:
                        if callable(fr):
                            summary = (fr(url) or "").strip()
                    except Exception:
                        summary = ""
                if summary:
                    st.write(summary[:1200] + ("…" if len(summary) > 1200 else ""))
                else:
                    st.caption("Geen preview beschikbaar.")
            st.divider()
