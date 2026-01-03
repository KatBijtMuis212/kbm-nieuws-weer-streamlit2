import streamlit as st
from common import load_article, host, ai_summarize

st.set_page_config(page_title="Artikel", page_icon="🔎", layout="wide")
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
    it = load_article(url)

st.markdown(f"## {it.get('title') or 'Bericht'}")
st.caption(host(url))

if it.get("ok") and it.get("text"):
    if it.get("summary"):
        st.markdown(it["summary"])
    else:
        st.info("Geen AI-samenvatting (nog).")
        if st.button("🧠 Maak AI-samenvatting", use_container_width=True):
            with st.spinner("Samenvatting maken…"):
                s = ai_summarize(it["text"], title=it.get("title", ""), source=host(url))
            if s:
                st.markdown(s)
            else:
                st.warning("AI-samenvatting lukte niet (check OPENAI_API_KEY/OPENAI_MODEL).")

    with st.expander("Volledige tekst (geëxtraheerd)", expanded=False):
        st.write(it["text"])
else:
    st.warning("Kon geen tekst uitlezen (site blokkeert of alleen via consent/JS).")
    st.info("AMP/print varianten worden automatisch geprobeerd. Als dat faalt, blijft alleen RSS-preview over.")

st.divider()
st.markdown(f"[Open origineel artikel]({url})")
