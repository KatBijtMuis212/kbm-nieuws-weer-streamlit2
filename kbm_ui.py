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


def _render_preview(it: dict, section_key: str, idx: int) -> None:
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
        # key moet uniek zijn over ALLE secties + dezelfde items
        if st.button("⭐ Bewaar", key=f"bm_{section_key}_{idx}_{item_id(it)}", use_container_width=True):
            _bookmark(it)
            st.toast("Bewaard ⭐")


def _safe_collect_items(feeds: list[str], query: str | None, max_items: int):
    out = collect_items(feeds, query=query, max_items=max_items)
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


def _card_link(title: str, link: str) -> str:
    # klikbaar binnen Streamlit multipage (jouw Artikel page)
    safe_title = html.escape(title or "Zonder titel")
    safe_link = html.escape(link or "")
    return f'<a href="/Artikel?url={safe_link}" style="text-decoration:none">{safe_title}</a>'


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

    section_key = title.lower().replace(" ", "_").replace("&", "and")

    items, _stats = _safe_collect_items(feeds, query=query, max_items=max_items)

    items = [x for x in items if within_hours(x.get("dt"), hours_limit)]
    items = [x for x in items if _matches_query(x, query)]
    items = items[: max(0, int(max_items))]

    st.markdown(f"## {title}")

    if not items:
        st.info("Geen berichten gevonden.")
        return

    # ------------------------------------------------------------
    # HERO: pak bij voorkeur eerste item mét afbeelding
    # ------------------------------------------------------------
    hero_idx = 0
    for i, it in enumerate(items[:10]):  # klein search window
        if _pick_image(it):
            hero_idx = i
            break

    hero = items.pop(hero_idx)
    hero_img = _pick_image(hero)
    hero_title = hero.get("title") or "Zonder titel"
    hero_link = hero.get("link") or ""

    # HERO layout (breed, altijd zichtbaar)
    hero_cols = st.columns([1.15, 1], gap="large")
    with hero_cols[0]:
        if hero_img:
            try:
                st.image(hero_img, use_container_width=True)
            except Exception:
                pass
        else:
            st.caption("Geen afbeelding beschikbaar voor dit bericht.")
    with hero_cols[1]:
        st.markdown(
            f"<div style='font-size:1.25rem; font-weight:800; line-height:1.2'>{_card_link(hero_title, hero_link)}</div>",
            unsafe_allow_html=True,
        )
        st.caption(f"{host(hero_link)} • {pretty_dt(hero.get('dt'))}")

        # korte hero preview (optioneel)
        hero_sum = _pick_summary(hero)
        if hero_sum:
            st.markdown(html.unescape(hero_sum), unsafe_allow_html=True)

        bcols = st.columns([1, 1, 1], gap="small")
        with bcols[0]:
            if hero_link:
                st.link_button("Open origineel", hero_link, use_container_width=True)
        with bcols[1]:
            if hero_link:
                st.link_button("Lees in app", f"/Artikel?url={hero_link}", use_container_width=True)
        with bcols[2]:
            if st.button("⭐ Bewaar", key=f"bm_{section_key}_hero_{item_id(hero)}", use_container_width=True):
                _bookmark(hero)
                st.toast("Bewaard ⭐")

    st.divider()

    # ------------------------------------------------------------
    # THUMB GRID: 4 stuks (of minder als niet genoeg)
    # ------------------------------------------------------------
    thumbs_n = max(0, int(thumbs_n))
    thumbs = items[:thumbs_n]
    rest = items[thumbs_n:]

    if thumbs:
        cols = st.columns(min(4, len(thumbs)), gap="large")
        for idx, it in enumerate(thumbs):
            img = _pick_image(it)
            link = it.get("link") or ""
            t = it.get("title") or "Zonder titel"

            with cols[idx % len(cols)]:
                if img:
                    try:
                        st.image(img, use_container_width=True)
                    except Exception:
                        pass
                st.markdown(
                    f"<div style='font-weight:700; line-height:1.25'>{_card_link(t, link)}</div>",
                    unsafe_allow_html=True,
                )
                st.caption(f"{host(link)} • {pretty_dt(it.get('dt'))}")

                with st.expander("Lees preview", expanded=False):
                    _render_preview(it, section_key, idx)

    # ------------------------------------------------------------
    # REST: simpel lijstje + preview in expander
    # ------------------------------------------------------------
    if rest:
        with st.expander("Meer berichten", expanded=False):
            for idx, it in enumerate(rest):
                link = (it.get("link") or "").strip()
                t = it.get("title") or "Zonder titel"
                st.markdown(f"- [{t}](/Artikel?url={link})")
                st.caption(f"{host(link)} • {pretty_dt(it.get('dt'))}")
