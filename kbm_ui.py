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
    # voorkeur: RSS/entry image -> og:image -> fallback
    # NB: common.collect_items zet de hoofdafbeelding meestal in key 'img'
    for k in ("img", "image", "thumbnail", "thumb", "og_image", "media", "media_url"):
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
    oid = item_id(it)

    # Klik op hero (titel/beeld) opent in-app via query params
    href = f"?section={section_key}&open={oid}"

    if img:
        st.markdown(
            f'''
            <div style="position:relative;border-radius:18px;overflow:hidden;margin:12px 0;">
              <a href="{href}" style="text-decoration:none;display:block;">
                <img src="{img}" style="width:100%;height:230px;object-fit:cover;display:block;">
                <div style="position:absolute;left:0;right:0;bottom:0;padding:16px 16px 14px 16px;
                            background:linear-gradient(180deg, rgba(0,0,0,0) 0%, rgba(0,0,0,.55) 55%, rgba(0,0,0,.70) 100%);">
                  <div class="kbm-title" style="color:#fff;font-size:22px;font-weight:800;line-height:1.2;text-shadow:0 2px 14px rgba(0,0,0,.55);">{title}</div>
                  <div class="kbm-meta" style="color:#fff;text-shadow:0 2px 12px rgba(0,0,0,.55);">{meta}</div>
                </div>
              </a>
            </div>
            ''',
            unsafe_allow_html=True,
        )
    else:
        # fallback zonder image (nog steeds klikbaar)
        st.markdown(f"### [{title}]({href})")
        st.caption(meta)


def _thumb_row(it: Dict[str, Any], section_key: str, idx: int):
    img = _pick_img(it)
    title = _norm_title(it.get("title",""))
    meta = f"{host(it.get('link',''))} • {pretty_dt(it.get('dt'))}".strip(" •")
    oid = item_id(it)
    href = f"?section={section_key}&open={oid}"

    col_img, col_txt = st.columns([1, 3.2], gap="small", vertical_alignment="center")

    with col_img:
        if img:
            st.markdown(
                f'''
                <a href="{href}" style="display:block;">
                  <img src="{img}" style="width:82px;height:82px;object-fit:cover;border-radius:12px;display:block;">
                </a>
                ''',
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                f'''
                <a href="{href}" style="display:block;">
                  <div style="width:82px;height:82px;border-radius:12px;background:#222;"></div>
                </a>
                ''',
                unsafe_allow_html=True,
            )

    with col_txt:
        # Titel als "link" (geen zichtbare knoppen)
        st.markdown(
            f'''
            <div style="line-height:1.25;">
              <a href="{href}" style="text-decoration:none;color:inherit;font-weight:750;">{title}</a>
              <div class="kbm-meta" style="opacity:.72;margin-top:3px;">{meta}</div>
            </div>
            ''',
            unsafe_allow_html=True,
        )


def _thumb_only(it: Dict[str, Any], section_key: str, idx: int):
    """Compact thumbnail: beeld links (vierkant), titel eronder. Past bij jouw mockup."""
    img = _pick_img(it)
    title = _norm_title(it.get("title", ""))

    if img:
        st.image(img, width=120)
    else:
        st.markdown('<div style="width:120px;height:120px;border-radius:18px;background:#e9edf2;"></div>', unsafe_allow_html=True)

    if st.button("Open", key=f"open_{section_key}_{item_id(it)}_thumb_{idx}", width="stretch"):
        st.session_state["kbm_open_item"] = it
        st.session_state["kbm_open_section"] = section_key
        st.experimental_rerun()

    st.caption(title)


def _render_article(it: Dict[str, Any]):
    st.markdown(f"## {_norm_title(it.get('title',''))}")
    st.caption(f"{host(it.get('link',''))} • {pretty_dt(it.get('dt'))}".strip(" •"))
    img = _pick_img(it)
    if img:
        st.image(img, width="stretch")

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
    st.link_button("Open origineel", link or "#", width="stretch")

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

    # Layout zoals je mockup: links thumbnails, rechts lijst
    left_col, right_col = st.columns([1.05, 2.25], gap="large")

    with left_col:
        for idx, it in enumerate(thumbs, start=1):
            _thumb_row(it, section_key, idx)

    with right_col:
        st.markdown("### Meer berichten")
        for idx, it in enumerate(items[1+len(thumbs):], start=100):
            title2 = _norm_title(it.get("title", ""))
            meta2 = f"{host(it.get('link',''))} • {pretty_dt(it.get('dt'))}".strip(" •")

            row = st.columns([3, 1], vertical_alignment="center")
            with row[0]:
                if st.button(title2, key=f"open_{section_key}_{item_id(it)}_list_{idx}"):
                    st.session_state["kbm_open_item"] = it
                    st.session_state["kbm_open_section"] = section_key
                    st.experimental_rerun()
                st.caption(meta2)
            with row[1]:
                st.link_button("Open", it.get("link", "") or "#", width="stretch")

            if idx >= 112:  # max ~12 regels in deze kolom (lekker overzicht)
                break
