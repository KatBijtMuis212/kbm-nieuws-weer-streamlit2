# kbm_ui.py — UI helpers voor KbM Nieuws (hero + thumbnails) + stabiele keys
from __future__ import annotations

import re
import base64
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


def _placeholder_thumb() -> str:
    """Altijd een thumbnail: data-URI SVG placeholder (werkt online/offline)."""
    svg = (
        "<svg xmlns='http://www.w3.org/2000/svg' width='82' height='82' viewBox='0 0 82 82'>"
        "<defs><linearGradient id='g' x1='0' y1='0' x2='1' y2='1'>"
        "<stop offset='0' stop-color='#2b2f36'/><stop offset='1' stop-color='#1f232a'/>"
        "</linearGradient></defs>"
        "<rect rx='12' ry='12' width='82' height='82' fill='url(#g)'/>"
        "<path d='M20 54l12-14 10 12 7-8 13 17H20z' fill='#5b6472'/>"
        "<circle cx='30' cy='30' r='6' fill='#5b6472'/>"
        "</svg>"
    )
    b64 = base64.b64encode(svg.encode("utf-8")).decode("ascii")
    return f"data:image/svg+xml;base64,{b64}"

def _img_or_placeholder(it: Dict[str, Any]) -> str:
    return _pick_img(it) or _placeholder_thumb()


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
    img = _img_or_placeholder(it)
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
    """Thumbnail row: beeld links, titel + meta rechts (ook op mobiel naast elkaar)."""
    img = _img_or_placeholder(it)
    title = _norm_title(it.get("title",""))
    meta = f"{host(it.get('link',''))} • {pretty_dt(it.get('dt'))}".strip(" •")
    oid = item_id(it)
    href = f"?section={section_key}&open={oid}"

    # Gebruik één HTML flex-row i.p.v. st.columns, zodat het op smalle schermen
    # niet onder elkaar gaat stapelen.
    img_html = f'<img src="{img}" style="width:82px;height:82px;object-fit:cover;border-radius:12px;flex:0 0 82px;display:block;">'

    st.markdown(
        f"""
        <a href="{href}" style="text-decoration:none;color:inherit;">
          <div style="display:flex;gap:12px;align-items:center;margin:10px 0;">
            {img_html}
            <div style="min-width:0;line-height:1.25;">
              <div style="font-weight:750;overflow:hidden;text-overflow:ellipsis;display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;">
                {title}
              </div>
              <div class="kbm-meta" style="opacity:.72;margin-top:3px;font-size:0.85rem;">
                {meta}
              </div>
            </div>
          </div>
        </a>
        """,
        unsafe_allow_html=True,
    )


def _thumb_only(it: Dict[str, Any], section_key: str, idx: int):
    """Compact thumbnail: beeld links (vierkant), titel eronder. Past bij jouw mockup."""
    img = _img_or_placeholder(it)
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



def _list_row(it: Dict[str, Any], section_key: str, idx: int):
    """Row in 'Meer berichten' / load-more lijst: altijd thumbnail + titel + meta rechts."""
    img = _img_or_placeholder(it)
    title = _norm_title(it.get("title", ""))
    meta = f"{host(it.get('link',''))} • {pretty_dt(it.get('dt'))}".strip(" •")
    oid = item_id(it)

    # Query params zorgen dat je op DEZE sectie blijft
    href = f"?section={section_key}&open={oid}"

    st.markdown(
        f"""
        <a href="{href}" style="text-decoration:none;color:inherit;">
          <div style="display:flex;gap:12px;align-items:center;margin:10px 0;">
            <img src="{img}" style="width:72px;height:72px;object-fit:cover;border-radius:12px;flex:0 0 72px;display:block;">
            <div style="min-width:0;line-height:1.25;">
              <div style="font-weight:750;overflow:hidden;text-overflow:ellipsis;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;">
                {title}
              </div>
              <div class="kbm-meta" style="opacity:.72;margin-top:3px;font-size:0.85rem;">
                {meta}
              </div>
            </div>
          </div>
        </a>
        """,
        unsafe_allow_html=True,
    )


def _render_article(it: Dict[str, Any]):
    st.markdown(f"## {_norm_title(it.get('title',''))}")
    st.caption(f"{host(it.get('link',''))} • {pretty_dt(it.get('dt'))}".strip(" •"))
    img = _img_or_placeholder(it)
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

def _page_path_for_section(title: str) -> str | None:
    """Find the Streamlit pages/<file>.py that renders this section title.

    We scan the /pages directory for a call like render_section("Title", ...).
    Returns the relative path (e.g. 'pages/22_Regionaal.py') suitable for st.switch_page.
    """
    try:
        from pathlib import Path
        import re as _re
        pages_dir = Path(__file__).resolve().parent / "pages"
        if not pages_dir.exists():
            return None
        needle = _re.compile(r'render_section\(\s*["\']' + _re.escape(title) + r'["\']', flags=_re.IGNORECASE)
        for fp in sorted(pages_dir.glob("*.py")):
            try:
                src = fp.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            if needle.search(src):
                return f"pages/{fp.name}"
    except Exception:
        return None
    return None

def render_section(title: str, hours_limit: int = 24, query: str | None = None, max_items: int = 80, thumbs_n: int = 4, view: str = "full"):
    _inject_fonts()
    section_key = re.sub(r"[^a-z0-9]+", "_", (title or "section").lower()).strip("_") or "section"

    # open article view gebeurt via query params (?section=...&open=...)

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

    # --- In-app artikel open via query params ---
    try:
        qp = st.query_params
        qp_section = (qp.get("section") or "").strip().lower()
        qp_open = (qp.get("open") or "").strip()
    except Exception:
        qp_section = ""
        qp_open = ""

    if qp_open and qp_section == section_key:
        hit = None
        for it in items:
            if str(item_id(it)) == qp_open:
                hit = it
                break
        if hit:
            if st.button("← Terug", key=f"back_{section_key}"):
                try:
                    st.query_params.clear()
                except Exception:
                    pass
                st.experimental_rerun()
            _render_article(hit)
            return

    # Niets? Toon hulp
    if not items:
        st.info("Geen resultaten. Probeer een andere zoekterm of verhoog 'Max uren oud'.")
        return

    # Hero = eerste item, thumbs = volgende n
    hero = items[0]
    thumbs = items[1:1+max(0, thumbs_n)]

    # Header op home/compact zodat je weet welke sectie je ziet
    if (view or "full").lower() in ("home", "compact"):
        st.markdown(f"## {title}")
    _hero_card(hero, section_key)

    # Home/compact view: alleen hero + 4 thumbs + 'Meer <categorie>' knop
    if (view or "full").lower() in ("home", "compact"):
        for idx, it in enumerate(thumbs, start=1):
            _thumb_row(it, section_key, idx)

        page_path = _page_path_for_section(title)
        label = f"Meer {title}"
        if page_path:
            try:
                if st.button(label, key=f"more_{section_key}", width="stretch"):
                    st.switch_page(page_path)
            except TypeError:
                # oudere Streamlit: geen width-arg
                if st.button(label, key=f"more_{section_key}"):
                    st.switch_page(page_path)
        else:
            st.caption(label)
        return

    # Volledige view: links thumbnails, rechts 'Meer berichten' lijst
    left_col, right_col = st.columns([1.05, 2.25], gap="large")

    with left_col:
        for idx, it in enumerate(thumbs, start=1):
            _thumb_row(it, section_key, idx)

    with right_col:
        st.markdown("### Meer berichten")

        for idx, it in enumerate(items[1+len(thumbs):], start=100):
            _list_row(it, section_key, idx)
            if idx >= 112:
                break
