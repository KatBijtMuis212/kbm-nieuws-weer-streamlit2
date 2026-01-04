# kbm_ui.py — UI helpers voor KbM Nieuws (hero + thumbnails) + stabiele keys
from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple, Optional

import streamlit as st

# Alles wat we nodig hebben komt uit common.py. Als iets ontbreekt, vangen we het af.
try:
    from common import CATEGORY_FEEDS, collect_items, within_hours, host, item_id, pretty_dt, pre
except Exception as e:  # pragma: no cover
    raise ImportError(f"Kon common.py niet importeren: {e}")

# ---------- Kleine utils ----------

def _as_list(x: Any) -> List[Any]:
    if x is None:
        return []
    if isinstance(x, list):
        return x
    return [x]

def _flatten(items: Any) -> List[Dict[str, Any]]:
    # collect_items hoort List[dict] te geven, maar we maken het extra robuust.
    out: List[Dict[str, Any]] = []
    for it in _as_list(items):
        if isinstance(it, list):
            out.extend(_flatten(it))
        elif isinstance(it, dict):
            out.append(it)
    return out

def _norm_title(t: str) -> str:
    return re.sub(r"\s+", " ", (t or "").strip())

def _safe_str(x: Any) -> str:
    return "" if x is None else str(x)

def _pick_img(it: Dict[str, Any]) -> str:
    # voorkeur: feed image -> og:image -> fallback
    for k in ("image", "thumbnail", "thumb", "og_image", "media", "media_url"):
        v = it.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return ""

def _dedupe(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen = set()
    out = []
    for it in items:
        uid = _safe_str(item_id(it)) or (_safe_str(it.get("link")) + "|" + _safe_str(it.get("title")))
        if uid in seen:
            continue
        seen.add(uid)
        out.append(it)
    return out

def _inject_fonts():
    st.markdown(
        '''
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@400;600&display=swap');
        html, body, [class*="css"] { font-family: "Montserrat", sans-serif; }
        .kbm-title { font-weight: 600; }
        .kbm-meta { opacity:.75; font-size: .9rem; }
        </style>
        ''',
        unsafe_allow_html=True
    )

def _hero_card(it: Dict[str, Any], section_key: str):
    img = _pick_img(it)
    title = _norm_title(it.get("title",""))
    meta = f"{host(it.get('link',''))} • {pretty_dt(it.get('dt'))}".strip(" •")
    # Hero met tekst-overlay + schaduw
    if img:
        st.markdown(
            f'''
            <div style="position:relative;border-radius:18px;overflow:hidden;margin:12px 0;">
              <img src="{img}" style="width:100%;height:230px;object-fit:cover;display:block;">
              <div style="position:absolute;left:0;right:0;bottom:0;padding:16px 16px 14px 16px;
                          background:linear-gradient(180deg, rgba(0,0,0,0) 0%, rgba(0,0,0,.55) 55%, rgba(0,0,0,.70) 100%);">
                <div class="kbm-title" style="color:#fff;font-size:1.35rem;line-height:1.2;text-shadow:0 2px 14px rgba(0,0,0,.55);">{title}</div>
                <div class="kbm-meta" style="color:#fff;text-shadow:0 2px 12px rgba(0,0,0,.55);">{meta}</div>
              </div>
            </div>
            ''',
            unsafe_allow_html=True
        )
    else:
        st.markdown(f"### {title}")
        st.caption(meta)

    cols = st.columns([1,1,1])
    with cols[0]:
        st.link_button("Open origineel", it.get("link","") or "#", use_container_width=True)
    with cols[1]:
        if st.button("Lees in app", key=f"open_{section_key}_{item_id(it)}_hero", use_container_width=True):
            st.session_state["kbm_open_item"] = it
            st.session_state["kbm_open_section"] = section_key
            st.experimental_rerun()
    with cols[2]:
        if st.button("⭐ Bewaar", key=f"bm_{section_key}_{item_id(it)}_hero", use_container_width=True):
            st.session_state.setdefault("bookmarks", [])
            st.session_state["bookmarks"].insert(0, it)

def _thumb_row(it: Dict[str, Any], section_key: str, idx: int):
    img = _pick_img(it)
    title = _norm_title(it.get("title",""))
    meta = f"{host(it.get('link',''))} • {pretty_dt(it.get('dt'))}".strip(" •")

    left, right = st.columns([1, 4], vertical_alignment="center")
    with left:
        if img:
            st.image(img, width=86)
        else:
            st.markdown('<div style="width:86px;height:64px;border-radius:12px;background:#e9edf2;"></div>', unsafe_allow_html=True)
    with right:
        st.markdown(f'<div class="kbm-title" style="font-size:1.05rem;line-height:1.25;">{title}</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="kbm-meta">{meta}</div>', unsafe_allow_html=True)

    btns = st.columns([1,1,1])
    with btns[0]:
        st.link_button("Open origineel", it.get("link","") or "#", use_container_width=True)
    with btns[1]:
        if st.button("Lees in app", key=f"open_{section_key}_{item_id(it)}_{idx}", use_container_width=True):
            st.session_state["kbm_open_item"] = it
            st.session_state["kbm_open_section"] = section_key
            st.experimental_rerun()
    with btns[2]:
        if st.button("⭐ Bewaar", key=f"bm_{section_key}_{item_id(it)}_{idx}", use_container_width=True):
            st.session_state.setdefault("bookmarks", [])
            st.session_state["bookmarks"].insert(0, it)

    st.divider()

def _render_article(it: Dict[str, Any]):
    st.markdown(f"## {_norm_title(it.get('title',''))}")
    st.caption(f"{host(it.get('link',''))} • {pretty_dt(it.get('dt'))}".strip(" •"))
    img = _pick_img(it)
    if img:
        st.image(img, use_container_width=True)

    # Video detectie (NU.nl /video/)
    link = _safe_str(it.get("link"))
    if "/video/" in link:
        st.info("🎬 Dit lijkt een NU.nl-video. Ik probeer ’m hieronder te tonen (als embed).")
        # simpele embed poging; als dit niet werkt blijft de knop 'Open origineel' over.
        st.components.v1.iframe(link, height=420, scrolling=True)

    # Content
    body = it.get("content") or it.get("summary") or ""
    if isinstance(body, str) and body.strip():
        st.markdown(body)
    else:
        st.warning("Dit artikel kon niet volledig uitgelezen worden (mogelijk JS/consent).")
    st.link_button("Open origineel", link or "#", use_container_width=True)

# ---------- Main ----------

def render_section(title: str, hours_limit: int = 24, query: str | None = None, max_items: int = 80, thumbs_n: int = 4):
    _inject_fonts()
    section_key = re.sub(r"[^a-z0-9]+", "_", (title or "section").lower()).strip("_") or "section"

    # open article view (in-app)
    if st.session_state.get("kbm_open_item") and st.session_state.get("kbm_open_section") == section_key:
        it = st.session_state.get("kbm_open_item")
        if st.button("← Terug", key=f"back_{section_key}"):
            st.session_state["kbm_open_item"] = None
            st.session_state["kbm_open_section"] = None
            st.experimental_rerun()
        _render_article(it)
        return

    feed_labels = CATEGORY_FEEDS.get(title, [])
    res = collect_items(feed_labels, query=query, max_per_feed=25)
    items = res[0] if isinstance(res, tuple) else res
    items = _flatten(items)

    # tijdfilter (defensief: dt ontbreekt soms)
    filtered = []
    for it in items:
        dt = it.get("dt")
        try:
            ok = within_hours(dt, hours_limit) if hours_limit else True
        except Exception:
            ok = True
        if ok:
            filtered.append(it)

    items = _dedupe(filtered)[:max_items]

    # Niets? Toon hulp
    if not items:
        st.info("Geen resultaten. Probeer een andere zoekterm of verhoog 'Max uren oud'.")
        return

    # Hero = eerste item, thumbs = volgende n
    hero = items[0]
    thumbs = items[1:1+max(0, thumbs_n)]

    _hero_card(hero, section_key)

    # Thumbnail lijst (exact 4/6/8 etc)
    for idx, it in enumerate(thumbs, start=1):
        _thumb_row(it, section_key, idx)

    # Meer berichten (rest)
    with st.expander("Meer berichten", expanded=False):
        for idx, it in enumerate(items[1+len(thumbs):], start=100):
            st.markdown(f"- [{_norm_title(it.get('title',''))}]({_safe_str(it.get('link'))})  \n<span class='kbm-meta'>{host(it.get('link',''))} • {pretty_dt(it.get('dt'))}</span>", unsafe_allow_html=True) 
