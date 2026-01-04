# -*- coding: utf-8 -*-
import streamlit as st
import datetime as dt
from ov_data import fetch_ovapi_departures, human_departure, build_9292_link

st.set_page_config(page_title="OV", page_icon="🚌", layout="wide")
st.markdown("# 🚌 Realtime OV")

st.caption("Realtime vertrektijden (bus/tram/metro/veer) via OVAPI (KV78Turbo). "
           "Voor reisadvies kun je (optioneel) doorlinken naar 9292.")

tab1, tab2 = st.tabs(["🚏 Vertrektijden", "🧭 Reisplanner (link)"])

with tab1:
    c1, c2, c3 = st.columns([0.34, 0.33, 0.33], gap="small")
    with c1:
        kind = st.selectbox("Type code", ["stopareacode", "tpc"], index=0, help="stopareacode = haltegebied/station, tpc = per perron/haltepaal.")
    with c2:
        code = st.text_input("Code", value="", placeholder="bijv. GvEras of 50006541")
    with c3:
        limit = st.slider("Max resultaten", 5, 60, 20, 5)

    st.info("Tip: je kunt codes vinden via ovzoeker.nl (haltenummer = tpc). "
            "Met tpc kun je vaak meteen werken. stopareacode geeft (als beschikbaar) alle perrons in 1x.")

    if code.strip():
        try:
            with st.spinner("Ophalen…"):
                deps, raw = fetch_ovapi_departures(code.strip(), kind=kind)
            if not deps:
                st.warning("Geen vertrektijden gevonden voor deze code (kan ook betekenen: geen realtime data nu).")
            else:
                now = dt.datetime.now(dt.timezone.utc)
                rows = []
                for d in deps[:limit]:
                    rows.append({
                        "Tijd": d.departure_time.astimezone().strftime("%H:%M"),
                        "In": max(0, int(round((d.departure_time - now).total_seconds()/60))),
                        "Lijn": d.line,
                        "Richting": d.destination,
                        "Perron": d.platform or "—",
                        "Realtime": "✅" if d.realtime else "—",
                        "Vertraging": (f"+{int(d.delay_sec/60)} min" if d.delay_sec and d.delay_sec > 0 else ("op tijd" if d.delay_sec == 0 else "—")),
                    })
                st.dataframe(rows, use_container_width=True, hide_index=True)
        except Exception as e:
            st.error(f"Kon OV-data niet ophalen: {e}")

with tab2:
    from_q = st.text_input("Van", placeholder="bijv. Huizen, Busstation / Amsterdam Centraal")
    to_q = st.text_input("Naar", placeholder="bijv. Hilversum / Den Haag Centraal")
    if st.button("Open reisadvies", use_container_width=True):
        if from_q.strip() and to_q.strip():
            st.link_button("🚀 Reisadvies openen (9292)", build_9292_link(from_q.strip(), to_q.strip()), use_container_width=True)
        else:
            st.warning("Vul zowel 'Van' als 'Naar' in.")
