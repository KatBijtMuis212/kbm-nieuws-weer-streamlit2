# kbm_ui.py — UI helpers voor KbM Nieuws (hero + thumbnails) + stabiele keys
from __future__ import annotations

import re
import base64
from typing import Any, Dict, List, Optional

import streamlit as st

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


# ---------- Kleine utils ----------

def _uniq_key(prefix: str) -> str:
    """Return a unique key for this session.

    Streamlit vereist unieke keys per element. Voor navigatieknoppen
    (zoals 'Meer <categorie>') is een oplopende teller per sessie prima.
    """
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


def _norm_title(t: str) -> str:
    return re.sub(r"\s+", " ", (t or "").strip())


def _safe_str(x: Any) -> str:
    return "" if x is None else str(x)


# Een nette, lichte placeholder thumbnail (data-uri SVG), zodat elk item altijd een thumb heeft.
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
    # common.py gebruikt meestal "img". We ondersteunen meerdere keys.
    for k in ("img", "image", "thumbnail", "thumb", "og_image", "media", "media_url"):
        v = it.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return ""


def _img_or_placeholder(it: Dict[str, Any]) -> str:
    return _pick_img(it) or _PLACEHOLDER_URI


def _get_items_for_section(
    title: str, hours_limit: Optional[int] = None, query: str = "", max_items: int = 80
) -> List[Dict[str, Any]]:
    """Haal items op voor een categorie (title)."""
    feeds = CATEGORY_FEEDS.get(title, [])
    items = collect_items(feeds, query=query, max_items=max_items)  # verwacht list[dict]
    items = _flatten(items)

    # Optionele uren-filter (bijv. Net binnen)
    if hours_limit and hours_limit > 0:
        items = [it for it in items if within_hours(it.get("dt"), hours_limit)]

    # Sorteer op datum (nieuwste eerst) als dt aanwezig is
    def _sort_key(it: Dict[str, Any]):
        return it.get("dt") or 0

    items.sort(key=_sort_key, reverse=True)
    return items


def _page_path_for_section(title: str) -> str:
    """Zoek automatisch de juiste Streamlit page voor een section/categorie.

    We scannen /pages/*.py en zoeken naar render_section("<title>", ...).
    Retourneert pad zoals "pages/22_Regionaal.py".
    """
    import glob

    title_norm = _safe_str(title)
    candidates = glob.glob("pages/*.py")
    for p in candidates:
        try:
            txt = open(p, "r", encoding="utf-8", errors="ignore").read()
        except Exception:
            continue
        if f'render_section("{title_norm}"' in txt or f"render_section('{title_norm}'" in txt:
            return p.replace("\\", "/")
    return ""


def _hero_card(it: Dict[str, Any], section_key: str):
    """Hero: grote kaart met beeld + titel overlay. Klikbaar -> in-app artikel."""
    img = _img_or_placeholder(it)
    title = _norm_title(it.get("title", ""))
    meta = f"{host(it.get('link',''))} • {pretty_dt(it.get('dt'))}".strip(" •")
    oid = item_id(it)
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


def _thumb_row(it: Dict[str, Any], section_key: str, idx: int):
    """Thumbnail row: beeld links, titel + meta rechts. Hele rij is klikbaar (in-app)."""
    img = _img_or_placeholder(it)
    title = _norm_title(it.get("title", ""))
    meta = f"{host(it.get('link',''))} • {pretty_dt(it.get('dt'))}".strip(" •")
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


def _list_row(it: Dict[str, Any], section_key: str, idx: int):
    """Row in 'Meer berichten' / load-more lijst: altijd thumbnail + titel + meta rechts."""
    img = _img_or_placeholder(it)
    title = _norm_title(it.get("title", ""))
    meta = f"{host(it.get('link',''))} • {pretty_dt(it.get('dt'))}".strip(" •")
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


def _render_article(it: Dict[str, Any], section_key: str):
    """In-app artikelweergave."""
    title = _norm_title(it.get("title", ""))
    link = _safe_str(it.get("link", ""))
    img = _pick_img(it)

    st.markdown(f"### {title}")

    meta = f"{host(link)} • {pretty_dt(it.get('dt'))}".strip(" •")
    if meta:
        st.caption(meta)

    if img:
        # streamlit 1.52: image width param gebruikt 'width'
        st.image(img, width="stretch")

    body = it.get("summary") or it.get("content") or ""
    if body:
        st.markdown(body, unsafe_allow_html=True)
    else:
        st.info("Geen volledige tekst beschikbaar voor dit bericht.")

    if link:
        try:
            st.link_button("Bekijk origineel", link, width="stretch")
        except TypeError:
            # oudere streamlit
            st.link_button("Bekijk origineel", link)


def render_section(
    title: str,
    hours_limit: Optional[int] = None,
    query: str = "",
    max_items: int = 80,
    thumbs_n: int = 4,
    view: str = "full",
):
    """Render een categorieblok.

    view="home"/"compact" -> Header + 1 hero + N thumbs + knop "Meer <categorie>"
    view="full"           -> Volledige categoriepagina met 'load more' lijst (ook thumbs!)
    """
    section_key = re.sub(r"[^a-z0-9]+", "_", title.lower()).strip("_") or "section"

    # --- Query params: open item in-app ---
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

    # Als er een open=<id> is voor deze sectie: toon artikel view
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

    # Header voor ieder blok
    st.markdown(f"## {title}")

    if not items:
        st.info("Geen berichten gevonden.")
        return

    hero = items[0]
    rest = items[1:]

    _hero_card(hero, section_key)

    n = max(0, int(thumbs_n or 0))
    for i, it in enumerate(rest[:n]):
        _thumb_row(it, section_key, i)

    # Home/compact view: eindigt hier + knop naar categoriepagina
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

    # Volledige view: lijst met meer berichten + "Laad meer" (alles met thumbnails)
    st.markdown("### Meer berichten")

    shown = int(st.session_state.get(f"kbm_shown_{section_key}", max(12, n)))

    start = 1 + n
    more_items = items[start : start + shown]
    for i, it in enumerate(more_items):
        _list_row(it, section_key, i)

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
