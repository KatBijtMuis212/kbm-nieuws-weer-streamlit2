import streamlit as st
from common import fetch_article_text, ai_long_summary, build_related_snippets, ai_multi_source_background, host, pretty_dt

st.set_page_config(page_title="Artikel", page_icon="📰", layout="wide")
st.markdown("# Artikel")

url = st.query_params.get("url", "")
if not url:
    st.error("Geen artikel-URL meegegeven.")
    st.stop()

st.caption(f"Bron: {host(url)}")
st.markdown(f"**URL:** {url}")

art = fetch_article_text(url)

if art.get("ok"):
    if art.get("img"):
        st.image(art["img"], use_container_width=True)
    if art.get("title"):
        st.markdown(f"## {art['title']}")

    with st.expander("Volledige tekst (uitgelezen)", expanded=False):
        st.write(art.get("text",""))

    st.divider()
    st.subheader("AI-achtergrond (heel uitgebreid)")

    if st.button("🧠 Maak/refresh AI-stuk", use_container_width=True):
        st.session_state["kbm_ai"] = None

    if "kbm_ai" not in st.session_state or st.session_state["kbm_ai"] is None:
        with st.spinner("AI schrijft…"):
            st.session_state["kbm_ai"] = ai_long_summary(art.get("title",""), art.get("text",""), source=host(url))

    if st.session_state.get("kbm_ai"):
        st.write(st.session_state["kbm_ai"])
    else:
        st.warning("AI-samenvatting lukte niet (check OPENAI_API_KEY/OPENAI_MODEL).")

else:
    st.warning("Dit artikel kon niet volledig uitgelezen worden (mogelijk JS/consent).")
    st.info("Dan maken we een achtergrondstuk op basis van meerdere bronnen die hierover schrijven.")

    related = build_related_snippets(url, main_title=host(url)+" • "+(art.get("title") or "artikel"), window_hours=48, k=7)
    if not related:
        st.error("Geen gerelateerde bronnen gevonden in de feeds.")
        st.stop()

    with st.expander("Bronnen die we combineren", expanded=False):
        for r in related:
            st.markdown(f"- **{r.get('source','')}** — {r.get('title','')} ({r.get('dt','')})")
            if r.get("rss_summary"):
                st.caption(r["rss_summary"][:240] + ("…" if len(r["rss_summary"])>240 else ""))

    st.divider()
    st.subheader("AI-achtergrond op basis van meerdere bronnen")

    if st.button("🧠 Maak/refresh achtergrondstuk", use_container_width=True):
        st.session_state["kbm_ai_multi"] = None

    if "kbm_ai_multi" not in st.session_state or st.session_state["kbm_ai_multi"] is None:
        with st.spinner("AI schrijft (multi-bron)…"):
            st.session_state["kbm_ai_multi"] = ai_multi_source_background(main_title=host(url), snippets=related)

    if st.session_state.get("kbm_ai_multi"):
        st.write(st.session_state["kbm_ai_multi"])
    else:
        st.warning("AI-samenvatting lukte niet (check OPENAI_API_KEY/OPENAI_MODEL).")
