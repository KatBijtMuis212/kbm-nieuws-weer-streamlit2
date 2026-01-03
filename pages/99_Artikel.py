import streamlit as st
from common import load_article, host

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
    st.info("Geen URL meegegeven. Ga terug en open een bericht via ‘Open’ of ‘Lees meer’.")
    st.stop()

with st.spinner("Artikel ophalen & samenvatten…"):
    it = load_article(url, force_fetch=True)

st.markdown(f"### {it.get('title') or 'Bericht'}")
st.caption(host(url) + (f" • samenvatting: {it.get('summary_mode','')}" if it.get("summary_mode") else ""))

if it.get("img"):
    st.image(it["img"], use_container_width=True)

if it.get("summary"):
    st.markdown(it["summary"])
else:
    st.warning("Kon geen samenvatting maken (site blokkeert of layout onbekend).")

if it.get("excerpt"):
    with st.expander("Korte preview", expanded=False):
        st.write(it["excerpt"])

st.markdown(f"[Open origineel artikel]({url})")
