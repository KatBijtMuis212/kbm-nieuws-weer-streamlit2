import streamlit as st
from streamlit_javascript import st_javascript
from common import (
    vt_find_stops_by_name,
    vt_find_stops_by_name_town,
    vt_find_stops_by_geo,
    vt_departures_by_town_stop,
)

st.set_page_config(page_title="OV info", page_icon="🚌", layout="wide")
st.markdown("# 🚌 OV info (live)")

tab1, tab2 = st.tabs(["🔎 Zoeken", "📍 Live locatie"])

def render_departures(town: str, stop: str):
    st.caption(f"Halte: **{stop}** — Plaats: **{town}**")
    try:
        data = vt_departures_by_town_stop(town, stop)
    except Exception as e:
        st.error(f"Vertrektijd.info fout: {e}")
        return

    # data structuur verschilt soms; probeer slim te lezen
    obj = data.get("obj") if isinstance(data, dict) else None
    if not obj:
        st.info("Geen vertrektijden gevonden.")
        return

    # meestal: obj is lijst met vervoer-types (BTMF/NS/etc)
    rows = []
    for group in obj if isinstance(obj, list) else [obj]:
        deps = group.get("Departures") or []
        for d in deps:
            rows.append({
                "Vertrek": d.get("ExpectedDeparture") or d.get("PlannedDeparture") or "",
                "Type": d.get("TransportType") or "",
                "Lijn": d.get("LineNumber") or "",
                "Richting": d.get("Destination") or "",
                "Vervoerder": d.get("Agency") or "",
                "Status": d.get("DepartureStatus") or "",
            })

    if not rows:
        st.info("Geen vertrektijden gevonden.")
        return

    st.dataframe(rows, use_container_width=True, hide_index=True)

with tab1:
    colA, colB = st.columns([0.6, 0.4], gap="large")
    with colA:
        q = st.text_input("Halte (naam)", placeholder="bijv. Busstation, Station, Centrum…")
    with colB:
        town = st.text_input("Plaats (optioneel, helpt enorm)", placeholder="bijv. Huizen")

    debug = st.toggle("Debug tonen", value=True)

    if st.button("Zoek haltes", use_container_width=True):
        if not q.strip():
            st.warning("Vul eerst een halte-naam in.")
            st.stop()

        st.info("Zoeken… even geduld (max ~12 sec).")

        try:
            if town.strip():
                stops = vt_find_stops_by_name_town(q, town)
            else:
                stops = vt_find_stops_by_name(q)

            if debug:
                st.write("Aantal resultaten:", len(stops))
                if len(stops) > 0:
                    st.write("Voorbeeld record:", stops[0])

        except Exception as e:
            st.error(f"Zoeken faalde: {type(e).__name__}: {e}")
            st.stop()

        if not stops:
            st.warning("Geen haltes gevonden. Probeer andere spelling of vul plaats in.")
        else:
            opts = []
            for s in stops[:25]:
                stopname = s.get("StopName") or s.get("ScheduleName") or "Onbekend"
                stown = s.get("Town") or town or "?"
                opts.append((stown, stopname))

            choice = st.selectbox("Kies halte", opts, format_func=lambda x: f"{x[1]} — {x[0]}")
            if st.button("Toon vertrektijden", use_container_width=True):
                render_departures(choice[0], choice[1])

with tab2:
    st.info("Klik op **Vraag locatie** en geef toestemming in je browser.")
    if st.button("📍 Vraag locatie", use_container_width=True):
        coords = st_javascript("""
            await new Promise((resolve) => {
              if (!navigator.geolocation) { resolve(null); return; }
              navigator.geolocation.getCurrentPosition(
                (pos) => resolve({lat: pos.coords.latitude, lon: pos.coords.longitude}),
                (err) => resolve(null),
                {enableHighAccuracy:true, timeout:10000, maximumAge:0}
              );
            });
        """)

        if not coords or "lat" not in coords:
            st.error("Geen locatie gekregen. Controleer browser-permissies.")
        else:
            lat, lon = float(coords["lat"]), float(coords["lon"])
            st.success(f"Locatie: {lat:.5f}, {lon:.5f}")

            dist = st.slider("Zoekafstand (km)", 0.2, 5.0, 1.0, 0.1)
            try:
                near = vt_find_stops_by_geo(lat, lon, distance_km=dist)
            except Exception as e:
                st.error(f"Vertrektijd.info fout: {e}")
                near = []

            if not near:
                st.warning("Geen haltes in de buurt gevonden.")
            else:
                opts = []
                for s in near[:25]:
                    stopname = s.get("StopName") or s.get("ScheduleName") or "Onbekend"
                    stown = s.get("Town") or "?"
                    opts.append((stown, stopname))
                choice = st.selectbox("Dichtbijzijnde haltes", opts, format_func=lambda x: f"{x[1]} — {x[0]}")
                if st.button("Toon vertrektijden (live)", use_container_width=True):
                    render_departures(choice[0], choice[1])
