# -*- coding: utf-8 -*-
import streamlit as st
import datetime as dt

from ov_data import (
    fetch_ovapi_departures,
    fetch_vertrektijd_departures,
    human_minutes,
)

st.set_page_config(page_title="OV", page_icon="🚌", layout="wide")
st.markdown("# 🚌 Realtime OV")

st.caption("Je kunt nu zoeken op **plaats + halte** (zoals OV Info). "
           "Als je een Vertrektijd.info API-key hebt, werkt dit super soepel. "
           "Zonder key kun je nog steeds OVAPI codes gebruiken (TPC/StopAreaCode).")

tab_search, tab_codes = st.tabs(["🔎 Zoeken op halte", "🧩 Codes (fallback)"])

def render_table(deps):
    now = dt.datetime.now(dt.timezone.utc)
    rows = []
    for d in deps:
        hhmm, mins = human_minutes(d, now=now)
        rows.append({
            "Tijd": hhmm,
            "In": mins,
            "Lijn": d.line,
            "Richting": d.destination,
            "Perron": d.platform or "—",
            "Realtime": "✅" if d.realtime else "—",
            "Vertraging": (f"+{int(d.delay_sec/60)} min" if d.delay_sec and d.delay_sec > 0 else ("op tijd" if d.delay_sec == 0 else "—")),
        })
    st.dataframe(rows, use_container_width=True, hide_index=True)

with tab_search:
    c1, c2, c3 = st.columns([0.36, 0.36, 0.28], gap="small")
    with c1:
        town = st.text_input("Plaats", placeholder="bijv. Huizen, Hilversum, Den Haag…")
    with c2:
        stop = st.text_input("Halte", placeholder="bijv. Busstation, Station, Gooiland, Erasmusplein…")
    with c3:
        limit = st.slider("Max", 10, 80, 30, 5)

    api_key = st.secrets.get("VERTREKTIJD_API_KEY", "").strip()

    if st.button("🚏 Toon vertrektijden", use_container_width=True):
        if not (town.strip() and stop.strip()):
            st.warning("Vul zowel **Plaats** als **Halte** in.")
        elif api_key:
            try:
                with st.spinner("Ophalen…"):
                    deps = fetch_vertrektijd_departures(town, stop, api_key=api_key)
                if not deps:
                    st.info("Geen vertrektijden gevonden. Probeer een iets andere halte-naam (bijv. 'Station' of 'Busstation').")
                else:
                    render_table(deps[:limit])
            except Exception as e:
                st.error(f"Vertrektijd.info fout: {e}")
        else:
            st.info("Geen VERTREKTIJD_API_KEY gevonden. Zet die in Streamlit Secrets om zoeken op naam te activeren.")
            st.markdown("**Alternatief:** gebruik hieronder OVAPI codes (TPC/StopAreaCode).")

    st.markdown("### 📍 Live locatie (optioneel)")
    st.markdown(
        "Streamlit kan je live locatie alleen krijgen als je browser toestemming geeft. "
        "Als je dit wilt, kan ik een kleine extra dependency toevoegen (streamlit-js-eval) zodat we "
        "automatisch de dichtstbijzijnde halte kunnen tonen."
    )

with tab_codes:
    st.markdown("### 🧩 OVAPI codes (werkt zonder API-key)")
    st.caption("TPC is het handigst. Die kun je vinden via ovzoeker.nl (haltenummer).")
    cc1, cc2, cc3 = st.columns([0.34, 0.33, 0.33], gap="small")
    with cc1:
        kind = st.selectbox("Type code", ["tpc", "stopareacode"], index=0)
    with cc2:
        code = st.text_input("Code", value="", placeholder="bijv. 50006541 (tpc) of GvEras (stopareacode)")
    with cc3:
        limit2 = st.slider("Max resultaten", 5, 60, 20, 5, key="lim2")

    if st.button("Ophalen via OVAPI", use_container_width=True):
        if not code.strip():
            st.warning("Vul een code in.")
        else:
            try:
                with st.spinner("Ophalen…"):
                    deps = fetch_ovapi_departures(code.strip(), kind=kind)
                if not deps:
                    st.warning("Geen vertrektijden gevonden voor deze code.")
                else:
                    render_table(deps[:limit2])
            except Exception as e:
                st.error(f"OVAPI fout: {e}")
