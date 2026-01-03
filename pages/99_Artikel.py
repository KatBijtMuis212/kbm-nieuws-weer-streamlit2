import streamlit as st
from common import load_article, host, ai_backgrounder, build_related_snippets

st.set_page_config(page_title="Artikel", page_icon="📰", layout="wide")
st.markdown("# Artikel")

try:
    qp = st.query_params
    url = qp.get("url")
except Exception:
    url = None

if isinstance(url, list):
    url = url[0] if url else None

if not url:
    st.info("Geen URL meegegeven. Ga terug en open een bericht via 🔎 Open.")
    st.stop()

with st.spinner("Artikel ophalen…"):
    art = load_article(url)

title = art.get("title") or "Bericht"
src = host(url)
st.markdown(f"## {title}")
st.caption(src)

if art.get("ok") and art.get("text"):
    st.success("Tekst is uitgelezen (statisch).")
    with st.expander("Volledige tekst (geëxtraheerd)", expanded=False):
        st.write(art["text"])
else:
    # Nicer message
    st.warning("Deze bron levert de volledige tekst vaak pas na cookies/consent en JavaScript.")
    st.info("Geen stress: we maken hieronder een uitgebreid achtergrondstuk op basis van meerdere bronnen (als beschikbaar).")

    # Only do multi-source if we have an OpenAI key and we can find related snippets
    with st.spinner("Gerelateerde berichten verzamelen…"):
        snippets = build_related_snippets(url, title, window_hours=24, k=6)

    if snippets:
        with st.expander("Bronnen gebruikt (klik open)", expanded=False):
            for s in snippets:
                st.markdown(f"- **{s['source']}** • {s['title']} ({s['dt']})")
                if s.get("rss_summary"):
                    st.caption(s["rss_summary"][:300] + ("…" if len(s["rss_summary"]) > 300 else ""))

        with st.spinner("Achtergrondstuk schrijven…"):
            bg = ai_backgrounder(main_title=title, main_source=src, snippets=snippets)

        if bg:
            st.markdown(bg)
        else:
            st.error("AI-achtergrondstuk kon niet worden gemaakt. Controleer OPENAI_API_KEY/OPENAI_MODEL in Secrets.")
    else:
        st.error("Geen gerelateerde bronnen gevonden om een achtergrondstuk te maken (probeer later opnieuw).")

st.divider()
st.markdown(f"[Open origineel artikel]({url})")
