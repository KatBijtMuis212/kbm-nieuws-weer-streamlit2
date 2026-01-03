import streamlit as st
from urllib.parse import urlencode

from common import (
    fetch_readable_text,
    collect_items,
    CATEGORY_FEEDS,
    find_related_items,
    openai_summarize,
    host,
)

st.set_page_config(page_title="Artikel", page_icon="📰", layout="wide")

st.markdown("# Artikel")

url = st.query_params.get("url") if hasattr(st, "query_params") else st.experimental_get_query_params().get("url", [""])[0]
if isinstance(url, list):
    url = url[0]
url = (url or "").strip()

if not url:
    st.error("Geen artikel-URL meegegeven.")
    st.stop()

st.caption(f"Bron: {host(url)}")
st.markdown(url)

title, text = fetch_readable_text(url)

if title:
    st.markdown(f"## {title}")

if text:
    st.success("Artikeltekst uitgelezen ✅")
    st.write(text)
else:
    st.warning("Dit artikel kon niet volledig uitgelezen worden (mogelijk JS/consent).")

# Multi-source backgrounder (optional)
with st.expander("🧠 AI-achtergrondstuk (meerdere bronnen)", expanded=False):
    # gather items from all categories as a pool
    pool_labels = []
    for labels in CATEGORY_FEEDS.values():
        pool_labels.extend(labels)
    pool_labels = sorted(set(pool_labels))

    items, _ = collect_items(pool_labels, query=None, max_per_feed=10)
    related = find_related_items(items, title or "", max_n=5)

    st.markdown("**Bronnen die ook hierover schrijven:**")
    for it in related:
        st.write(f"- {host(it.get('link',''))}: {it.get('title','')}")

    api_key = st.secrets.get("OPENAI_API_KEY", "")
    model = st.secrets.get("OPENAI_MODEL", "gpt-4o-mini")

    if st.button("✨ Maak achtergrondstuk", use_container_width=True):
        if not api_key:
            st.error("OPENAI_API_KEY ontbreekt in Streamlit Secrets.")
        else:
            # prompt: strong backgrounder, long allowed
            src_block = "\n".join([f"- {it.get('title','')} ({it.get('link','')})" for it in related[:5]])
            base_text = (text[:12000] if text else "")
            prompt = f"""Je bent een Nederlandse nieuwsredacteur.
Schrijf een uitgebreid, helder achtergrondstuk (mag lang zijn) voor een slimme lezer.
- Begin met 2-3 zinnen lead (wat is er gebeurd / waarom relevant).
- Daarna context, feiten, betrokken partijen, mogelijke gevolgen.
- Gebruik kopjes.
- Geen bullet-spam: vooral lopende tekst.
- Als de originele artikeltekst ontbreekt, baseer je op de bronlijst hieronder en algemene kennis, maar verzin geen feiten: wees duidelijk als iets onzeker is.

ORIGINELE TEKST (indien beschikbaar):
{base_text}

BRONLIJST:
{src_block}
"""
            with st.spinner("AI schrijft…"):
                out = openai_summarize(model=model, api_key=api_key, prompt=prompt)
            if out:
                st.markdown(out)
            else:
                st.error("AI-samenvatting lukte niet (check OPENAI_API_KEY/OPENAI_MODEL).")
