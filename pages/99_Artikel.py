import streamlit as st
from common import fetch_readable_text, collect_items, CATEGORY_FEEDS, find_related_items, openai_summarize, host

st.set_page_config(page_title="Artikel", page_icon="📰", layout="wide")

url = st.query_params.get("url", "")
st.markdown("# Artikel")
if not url:
    st.info("Geen artikel geselecteerd.")
    st.stop()

st.caption(f"Bron: {host(url)}")
st.write(url)

title, text = fetch_readable_text(url)

if title:
    st.markdown(f"## {title}")

if text:
    st.markdown("### Volledige tekst (best-effort)")
    st.write(text)
else:
    st.warning("Dit artikel kon niet volledig uitgelezen worden (mogelijk JS/consent).")

# Multi-source backgrounder (extra, alleen als tekst ontbreekt of als je wilt)
with st.expander("🧠 AI-achtergrondstuk (meerdere bronnen)", expanded=True):
    # collect a bigger pool from several categories to find related coverage
    pool = []
    for k in ["Binnenland","Buitenland","Economie","Sport","Show","Net binnen"]:
        feeds = CATEGORY_FEEDS.get(k, [])
        items, _ = collect_items(feeds, query=None, max_per_feed=20)
        pool.extend(items)

    related = find_related_items(pool, title or "", max_n=4)
    st.markdown("**Bronnen die ook hierover schrijven:**")
    for it in related:
        st.markdown(f"- {host(it['link'])}: {it['title']}")

    api_key = st.secrets.get("OPENAI_API_KEY", "")
    model = st.secrets.get("OPENAI_MODEL", "gpt-4o-mini")

    if st.button("✨ Maak achtergrondstuk", use_container_width=True):
        if not api_key:
            st.error("AI-samenvatting lukte niet (check OPENAI_API_KEY/OPENAI_MODEL).")
        else:
            sources_text = ""
            # include the extracted text if we have it
            if text:
                sources_text += f"BRON 0 ({host(url)}):\n{(text[:8000])}\n\n"
            for i, it in enumerate(related, start=1):
                t2, txt2 = fetch_readable_text(it["link"])
                if txt2:
                    sources_text += f"BRON {i} ({host(it['link'])}):\n{txt2[:6000]}\n\n"
                else:
                    sources_text += f"BRON {i} ({host(it['link'])}):\n{it.get('rss_summary','')[:1500]}\n\n"

            prompt = f"""Je bent een Nederlandse nieuwsredacteur.
Schrijf een diepgaand, feitelijk achtergrondstuk (geen bulletpoints) op basis van de bronnen hieronder.
Structuur:
- 1 zin lead (nieuwswaardig)
- 2-4 alinea's context/duiding (wie/wat/waarom)
- 1 alinea: wat nu / mogelijke gevolgen
Vermijd letterlijk kopiëren; parafraseer.
Als bronnen elkaar tegenspreken: benoem dat.
\n\nBRONNEN:\n{sources_text}
"""
            out = openai_summarize(model=model, api_key=api_key, prompt=prompt)
            if not out:
                st.error("AI-samenvatting lukte niet (check OPENAI_API_KEY/OPENAI_MODEL).")
            else:
                st.success("Klaar ✅")
                st.write(out)
