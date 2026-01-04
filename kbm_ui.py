# kbm_ui.py — UI helpers voor KbM Nieuws (hero + thumbnails) + stabiele keys
from __future__ import annotations

import base64
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

import streamlit as st
import requests
from bs4 import BeautifulSoup

# Alles wat we nodig hebben komt uit common.py. Als iets ontbreekt, vangen we het af.
try:
    from common import (
        CATEGORY_FEEDS,
        collect_items,
        within_hours,
        host,
        item_id,
        pretty_dt,
        pre,
    )
except Exception as e:  # pragma: no cover
    raise ImportError(f"Kon common.py niet importeren: {e}")


# ---------- Keys / utils ----------

def _uniq_key(prefix: str) -> str:
    """Return a unique key for this session (prevents StreamlitDuplicateElementKey)."""
    st.session_state.setdefault("_kbm_keyseq", 0)
    st.session_state["_kbm_keyseq"] += 1
    return f"{prefix}_{st.session_state['_kbm_keyseq']}"


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


def _safe_str(x: Any) -> str:
    return "" if x is None else str(x)


def _norm_title(t: str) -> str:
    return re.sub(r"\s+", " ", (t or "").strip())


def _get_title(it: Dict[str, Any]) -> str:
    # Verschillende bronnen noemen dit anders
    for k in ("title", "titel", "headline", "name"):
        v = it.get(k)
        if isinstance(v, str) and v.strip():
            return _norm_title(v)
    # fallback op summary
    v = it.get("summary") or it.get("description") or it.get("content")
    if isinstance(v, str) and v.strip():
        return _norm_title(v)[:140]
    return "(zonder titel)"


def _get_link(it: Dict[str, Any]) -> str:
    for k in ("link", "url", "href"):
        v = it.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return ""


def _get_dt(it: Dict[str, Any]) -> Any:
    # common gebruikt meestal "dt", maar sommige feeds kunnen "published"/"date" hebben
    for k in ("dt", "published", "date", "updated"):
        v = it.get(k)
        if v is not None and v != "":
            return v
    return None


def _dt_sort_key(v: Any) -> float:
    """Robuuste sorteersleutel: accepteert datetime / int/float / ISO string."""
    if v is None:
        return 0.0
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, datetime):
        try:
            return v.timestamp()
        except Exception:
            return 0.0
    if isinstance(v, str):
        s = v.strip()
        if not s:
            return 0.0
        # ISO-ish
        try:
            # handle Z
            s2 = s.replace("Z", "+00:00")
            return datetime.fromisoformat(s2).timestamp()
        except Exception:
            return 0.0
    return 0.0


# ---------- Placeholder thumbnail (altijd een plaatje) ----------

_PLACEHOLDER_SVG = """
<svg xmlns="http://www.w3.org/2000/svg" width="220" height="220" viewBox="0 0 220 220">
  <defs>
    <linearGradient id="g" x1="0" x2="1" y1="0" y2="1">
      <stop offset="0" stop-color="#e9edf2"/>
      <stop offset="1" stop-color="#dfe6ee"/>
    </linearGradient>
  </defs>
  <rect width="220" height="220" rx="28" fill="url(#g)"/>
  <rect x="34" y="46" width="152" height="108" rx="18" fill="#cfd8e3"/>
  <circle cx="82" cy="88" r="14" fill="#b8c5d6"/>
  <path d="M54 142l38-34 24 20 34-30 44 44H54z" fill="#b8c5d6"/>
  <rect x="34" y="168" width="120" height="14" rx="7" fill="#c7d2df"/>
  <rect x="34" y="190" width="86" height="12" rx="6" fill="#cfd8e3"/>
</svg>
""".strip()


def _svg_data_uri(svg: str) -> str:
    b = base64.b64encode(svg.encode("utf-8")).decode("ascii")
    return f"data:image/svg+xml;base64,{b}"


_PLACEHOLDER_URI = _svg_data_uri(_PLACEHOLDER_SVG)


def _pick_img(it: Dict[str, Any]) -> str:
    for k in ("img", "image", "thumbnail", "thumb", "og_image", "media", "media_url"):
        v = it.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return ""


def _img_or_placeholder(it: Dict[str, Any]) -> str:
    return _pick_img(it) or _PLACEHOLDER_URI


# ---------- Data fetching ----------

def _get_items_for_section(
    title: str,
    hours_limit: Optional[int] = None,
    query: str = "",
    max_items: int = 80,
) -> List[Dict[str, Any]]:
    feeds = CATEGORY_FEEDS.get(title, [])

    # collect_items kan bij jou (items, stats) teruggeven.
    res = collect_items(feeds, query=query, max_items=max_items)
    if isinstance(res, tuple) and len(res) >= 1:
        items = res[0]
    else:
        items = res

    items = _flatten(items)

    # Uren-filter: alleen logisch voor "Net binnen"
    if hours_limit and hours_limit > 0 and title.strip().lower() == "net binnen":
        items = [it for it in items if within_hours(_get_dt(it), hours_limit)]

    # Sorteer robuust op datum (nieuwste eerst)
    items.sort(key=lambda it: _dt_sort_key(_get_dt(it)), reverse=True)
    return items


def _page_path_for_section(title: str) -> str:
    """Zoek automatisch de juiste Streamlit page voor een section/categorie."""
    import glob

    title_norm = _safe_str(title)
    for p in glob.glob("pages/*.py"):
        try:
            txt = open(p, "r", encoding="utf-8", errors="ignore").read()
        except Exception:
            continue
        if f'render_section("{title_norm}"' in txt or f"render_section('{title_norm}'" in txt:
            return p.replace("\\", "/")
    return ""


# ---------- UI blocks ----------

def _hero_card(it: Dict[str, Any], section_key: str):
    img = _img_or_placeholder(it)
    title = _get_title(it)
    link = _get_link(it)
    meta = f"{host(link)} • {pretty_dt(_get_dt(it))}".strip(" •")
    oid = item_id(it)

    # HERO moet altijd titel/meta overlay hebben, zoals jij wil
    href = f"?section={section_key}&open={oid}"

    st.markdown(
        f"""
        <a href="{href}" style="text-decoration:none;color:inherit;">
          <div style="
            position:relative;
            border-radius:18px;
            overflow:hidden;
            height:220px;
            background:#e9edf2;
          ">
            <img src="{img}" style="width:100%;height:100%;object-fit:cover;display:block;">
            <div style="
              position:absolute;inset:0;
              background:linear-gradient(180deg, rgba(0,0,0,0) 0%, rgba(0,0,0,.55) 55%, rgba(0,0,0,.70) 100%);
            "></div>

            <div style="
              position:absolute;left:16px;right:16px;bottom:14px;
              color:#fff;
            ">
              <div style="
                font-size:1.15rem;
                font-weight:850;
                line-height:1.15;
                text-shadow:0 2px 10px rgba(0,0,0,.45);
                overflow:hidden;
                display:-webkit-box;
                -webkit-line-clamp:3;
                -webkit-box-orient:vertical;
              ">{title}</div>
              <div style="margin-top:6px;opacity:.9;font-size:.9rem;">{meta}</div>
            </div>
          </div>
        </a>
        """,
        unsafe_allow_html=True,
    )


def _thumb_row(it: Dict[str, Any], section_key: str):
    img = _img_or_placeholder(it)
    title = _get_title(it)
    link = _get_link(it)
    meta = f"{host(link)} • {pretty_dt(_get_dt(it))}".strip(" •")
    oid = item_id(it)
    href = f"?section={section_key}&open={oid}"

    img_html = (
        f'<img src="{img}" '
        'style="width:82px;height:82px;object-fit:cover;border-radius:12px;'
        'flex:0 0 82px;display:block;">'
    )

    st.markdown(
        f"""
        <a href="{href}" style="text-decoration:none;color:inherit;">
          <div style="display:flex;gap:12px;align-items:center;margin:10px 0;">
            {img_html}
            <div style="min-width:0;line-height:1.25;">
              <div style="
                font-weight:750;
                overflow:hidden;
                text-overflow:ellipsis;
                display:-webkit-box;
                -webkit-line-clamp:3;
                -webkit-box-orient:vertical;
              ">{title}</div>
              <div class="kbm-meta" style="opacity:.72;margin-top:3px;font-size:0.85rem;">{meta}</div>
            </div>
          </div>
        </a>
        """,
        unsafe_allow_html=True,
    )


def _list_row(it: Dict[str, Any], section_key: str):
    img = _img_or_placeholder(it)
    title = _get_title(it)
    link = _get_link(it)
    meta = f"{host(link)} • {pretty_dt(_get_dt(it))}".strip(" •")
    oid = item_id(it)
    href = f"?section={section_key}&open={oid}"

    img_html = (
        f'<img src="{img}" '
        'style="width:72px;height:72px;object-fit:cover;border-radius:12px;'
        'flex:0 0 72px;display:block;">'
    )

    st.markdown(
        f"""
        <a href="{href}" style="text-decoration:none;color:inherit;">
          <div style="display:flex;gap:12px;align-items:center;margin:10px 0;">
            {img_html}
            <div style="min-width:0;line-height:1.25;">
              <div style="
                font-weight:750;
                overflow:hidden;
                text-overflow:ellipsis;
                display:-webkit-box;
                -webkit-line-clamp:3;
                -webkit-box-orient:vertical;
              ">{title}</div>
              <div class="kbm-meta" style="opacity:.72;margin-top:3px;font-size:0.85rem;">{meta}</div>
            </div>
          </div>
        </a>
        """,
        unsafe_allow_html=True,
    )


@st.cache_data(show_spinner=False, ttl=60 * 30)
def _fetch_article_text(url: str) -> str:
    """Probeer de volledige artikeltekst op te halen via de originele URL.

    Werkt heuristisch (geen perfecte scraper), maar is veel beter dan alleen een RSS summary.
    """
    if not url:
        return ""
    try:
        r = requests.get(
            url,
            timeout=12,
            headers={
                "User-Agent": "KbMNieuws/1.0 (Streamlit)",
                "Accept": "text/html,application/xhtml+xml",
            },
        )
        r.raise_for_status()
    except Exception:
        return ""

    html = r.text or ""
    if not html.strip():
        return ""

    soup = BeautifulSoup(html, "html.parser")

    # weg met rommel
    for tag in soup(["script", "style", "noscript", "svg", "iframe"]):
        tag.decompose()

    # prefer <article>
    node = soup.find("article")
    if node is None:
        # fallback: kies het grootste 'main' of een div met meeste tekst
        node = soup.find("main")
    if node is None:
        # grootste div/section
        best = None
        best_len = 0
        for cand in soup.find_all(["div", "section"], limit=80):
            txt = cand.get_text(" ", strip=True)
            if len(txt) > best_len:
                best = cand
                best_len = len(txt)
        node = best or soup.body or soup

    # verwijder typische navigatieblokken binnen node
    for sel in ["header", "footer", "nav", "aside", "form"]:
        for t in node.find_all(sel):
            t.decompose()

    # pak paragrafen
    paras = []
    for p in node.find_all(["p", "h2", "h3"], limit=120):
        txt = p.get_text(" ", strip=True)
        txt = re.sub(r"\s+", " ", txt).strip()
        if not txt:
            continue
        # filter hele korte rommel
        if len(txt) < 30 and txt.endswith(":"):
            continue
        paras.append(txt)

    # fallback op totale tekst
    if not paras:
        txt = node.get_text("\n", strip=True)
        txt = re.sub(r"\n{3,}", "\n\n", txt)
        return txt.strip()

    # de-dup
    out = []
    seen = set()
    for t in paras:
        key = t[:120]
        if key in seen:
            continue
        seen.add(key)
        out.append(t)

    return "\n\n".join(out).strip()


def _render_article(it: Dict[str, Any], section_key: str):
    title = _get_title(it)
    link = _get_link(it)
    img = _pick_img(it)

    st.markdown(f"### {title}")
    meta = f"{host(link)} • {pretty_dt(_get_dt(it))}".strip(" •")
    if meta:
        st.caption(meta)

    if img:
        try:
            st.image(img, width="stretch")
        except TypeError:
            st.image(img, use_container_width=True)

    body = it.get("content") or it.get("summary") or it.get("description") or ""
    # Als RSS geen volledige tekst geeft: probeer live te scrapen.
    if (not body) or (isinstance(body, str) and len(body.strip()) < 200):
        scraped = _fetch_article_text(link)
        if scraped and len(scraped) > 200:
            body = scraped
    if body:
        st.markdown(body, unsafe_allow_html=True)
    else:
        st.info("Geen volledige tekst beschikbaar voor dit bericht.")

    if link:
        try:
            st.link_button("Bekijk origineel", link, width="stretch")
        except TypeError:
            st.link_button("Bekijk origineel", link)


def render_section(
    title: str,
    hours_limit: Optional[int] = None,
    query: str = "",
    max_items: int = 80,
    thumbs_n: int = 4,
    view: str = "full",
):
    section_key = re.sub(r"[^a-z0-9]+", "_", title.lower()).strip("_") or "section"

    # Query params: open item in-app
    try:
        qp = st.query_params
    except Exception:
        qp = {}

    if isinstance(qp, dict):
        qp_section = _safe_str(qp.get("section", ""))
        qp_open = _safe_str(qp.get("open", ""))
    else:
        qp_section = _safe_str(qp.get("section"))
        qp_open = _safe_str(qp.get("open"))

    items = _get_items_for_section(title, hours_limit=hours_limit, query=query, max_items=max_items)

    # Als er open=<id> is voor deze sectie: toon artikel view
    if qp_open and (qp_section == section_key or qp_section == title):
        hit = None
        for it in items:
            if str(item_id(it)) == qp_open:
                hit = it
                break
        if hit:
            if st.button("← Terug", key=_uniq_key(f"back_{section_key}")):
                try:
                    st.query_params.clear()
                except Exception:
                    pass
                st.experimental_rerun()
            _render_article(hit, section_key)
            return

    # Header (home wil dit expliciet)
    st.markdown(f"## {title}")

    if not items:
        st.info("Geen berichten gevonden.")
        return

    hero = items[0]
    rest = items[1:]

    _hero_card(hero, section_key)

    n = max(0, int(thumbs_n or 0))
    for it in rest[:n]:
        _thumb_row(it, section_key)

    # Home/compact: knop "Meer <categorie>" en klaar
    if view in ("home", "compact"):
        label = f"Meer {title}"
        page_path = _page_path_for_section(title)
        if page_path:
            try:
                if st.button(label, key=_uniq_key(f"more_{section_key}"), width="stretch"):
                    st.switch_page(page_path)
            except TypeError:
                if st.button(label, key=_uniq_key(f"more_{section_key}")):
                    st.switch_page(page_path)
        else:
            st.caption(label)
        return

    # Full view: lijst + laad meer
    st.markdown("### Meer berichten")

    shown = int(st.session_state.get(f"kbm_shown_{section_key}", max(12, n)))
    start = 1 + n
    more_items = items[start : start + shown]
    for it in more_items:
        _list_row(it, section_key)

    remaining = max(0, len(items) - (start + shown))
    if remaining > 0:
        label = f"Laad meer ({min(20, remaining)})"
        try:
            if st.button(label, key=_uniq_key(f"load_{section_key}"), width="stretch"):
                st.session_state[f"kbm_shown_{section_key}"] = shown + 20
                st.experimental_rerun()
        except TypeError:
            if st.button(label, key=_uniq_key(f"load_{section_key}")):
                st.session_state[f"kbm_shown_{section_key}"] = shown + 20
                st.experimental_rerun()
