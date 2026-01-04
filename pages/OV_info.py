
import streamlit as st
from datetime import datetime
from streamlit_js_eval import streamlit_js_eval

from ov_api import search_stops_smart, nearby_stops, departures_by_stopcode

st.set_page_config(page_title="OV Info", page_icon="🚌", layout="wide")
st.markdown("# 🚌 OV Info")

st.caption("Zoek een halte op naam (zoals in OV Info), of gebruik live locatie om haltes in de buurt te tonen.")

tab1, tab2 = st.tabs(["🔎 Zoeken", "📍 Live locatie"])

def _fmt_dt(s: str) -> str:
    # API returns ISO 8601 strings
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        return dt.astimezone().strftime("%H:%M")
    except Exception:
        return s

def _departures_table(dep_json: dict):
    btmf = dep_json.get("BTMF") or []
    train = dep_json.get("TRAIN") or []
    rows = []
    # BTMF
    for block in btmf:
        for d in (block.get("Departures") or []):
            rows.append({
                "Tijd": _fmt_dt(d.get("ExpectedDeparture") or d.get("PlannedDeparture") or ""),
                "Lijn": d.get("LineNumber") or d.get("LineName") or "",
                "Richting": d.get("Destination") or "",
                "Type": d.get("TransportType") or "",
                "Status": d.get("VehicleStatus") or "",
                "Perron": d.get("Platform") or "",
            })
    # TRAIN (simpler view)
    for block in train:
        for d in (block.get("Departures") or []):
            rows.append({
                "Tijd": _fmt_dt(d.get("ExpectedDeparture") or d.get("PlannedDeparture") or ""),
                "Lijn": d.get("LineNumber") or d.get("LineName") or "",
                "Richting": d.get("Destination") or "",
                "Type": "TRAIN",
                "Status": d.get("VehicleStatus") or "",
                "Perron": d.get("Platform") or "",
            })
    if not rows:
        st.info("Geen vertrektijden gevonden (nu).")
        return
    st.dataframe(rows, use_container_width=True, hide_index=True)

def _stop_label(stop: dict) -> str:
    name = stop.get("ScheduleName") or stop.get("StopName") or "Onbekende halte"
    town = stop.get("Town") or ""
    code = stop.get("StopCode") or ""
    return f"{name} ({code})" if not town else f"{name} — {town} ({code})"

with tab1:
    q = st.text_input(
        "Zoek halte",
        placeholder="bijv. Huizen Zuiderzee, Amsterdam Centraal, Gouda Station…",
        key="ov_q",
    ).strip()

    colA, colB = st.columns([0.65, 0.35], gap="small")
    with colA:
        go = st.button("Zoek", type="primary", use_container_width=True)
    with colB:
        debug = st.toggle("Debug tonen", value=False)

    # --- Live zoeken terwijl je typt (vanaf 2 letters) ---
    # Streamlit rerunt bij elke toetsaanslag: we 'throttlen' met een simpele tijd-check.
    import time

    last_q = st.session_state.get("ov_last_q", "")
    last_t = st.session_state.get("ov_last_t", 0.0)

    should_search = False
    if q and len(q) >= 2 and q != last_q:
        # max ~2 searches per seconde
        if time.time() - float(last_t or 0.0) > 0.45:
            should_search = True

    if (go and q) or should_search:
        try:
            with st.spinner("Zoeken…"):
                raw = search_stops_smart(q)

            # Normaliseer: we willen altijd een lijst van dicts (of lege lijst)
            res = []
            if isinstance(raw, dict):
                # Sommige wrappers geven {"Stops":[...]} of {"results":[...]}
                raw = raw.get("Stops") or raw.get("results") or raw.get("stops") or []
            if isinstance(raw, list):
                for item in raw:
                    if isinstance(item, dict):
                        res.append(item)
                    elif isinstance(item, str) and item.strip():
                        res.append({"StopName": item.strip()})
            elif isinstance(raw, str) and raw.strip():
                res = [{"StopName": raw.strip()}]

            st.session_state.ov_last_results = res
            st.session_state.ov_last_q = q
            st.session_state.ov_last_t = time.time()
        except Exception as e:
            st.session_state.ov_last_results = []
            st.error(f"Zoeken faalde: {e}")

    res = st.session_state.get("ov_last_results", []) or []
    if res:
        st.caption(f"Aantal resultaten: {len(res)}")

        if debug:
            st.markdown("**Voorbeeld record:**")
            st.json(res[0])

        # labels -> item, maar voorkom dubbele keys
        options = {}
        counts = {}
        for s in res:
            label = _stop_label(s)
            counts[label] = counts.get(label, 0) + 1
            if counts[label] > 1:
                label = f"{label}  #{counts[label]}"
            options[label] = s

        choice = st.selectbox("Kies halte", list(options.keys()), key="ov_pick")

        if st.button("Toon vertrektijden", use_container_width=True, key="ov_show_depart"):
            st.session_state.ov_selected_stop = options.get(choice)

    sel = st.session_state.get("ov_selected_stop")
    if sel:

        st.markdown("## Vertrektijden")
        st.caption(_stop_label(sel))
        try:
            with st.spinner("Vertrektijden ophalen…"):
                stopcode = sel.get("StopCode") if isinstance(sel, dict) else None
                if not stopcode:
                    st.warning("Deze keuze heeft geen StopCode. Kies een andere halte uit de lijst.")
                    dep = None
                else:
                    dep = departures_by_stopcode(stopcode)

            if dep:
                _departures_table(dep)
        except Exception as e:
            st.error(f"Vertrektijd.info fout: {e}")

with tab2:
    st.caption("Tip: werkt alleen als je browser locatie-permissie aan staat. Bij Streamlit Cloud blijft dit soms streng; opnieuw toestaan helpt.")
    if st.button("📍 Pak live locatie", type="primary", use_container_width=True, key="ov_geo_btn"):
        # streamlit_js_eval returns dict like {"coords":{"latitude":..,"longitude":..},...} or None
        loc = streamlit_js_eval(js_expressions="navigator.geolocation.getCurrentPosition((p)=>p, (e)=>e)", want_output=True, key="ov_geo")
        st.session_state.ov_live_loc = loc

    loc = st.session_state.get("ov_live_loc")
    if not loc or (isinstance(loc, dict) and loc.get("code")):
        st.info("Geen locatie gekregen. Controleer browser-permissies.")
    else:
        try:
            coords = loc.get("coords", {}) if isinstance(loc, dict) else {}
            lat = coords.get("latitude")
            lon = coords.get("longitude")
            if lat is None or lon is None:
                st.info("Geen locatie gekregen. Controleer browser-permissies.")
            else:
                st.success(f"Locatie: {lat:.5f}, {lon:.5f}")
                dist = st.slider("Zoekradius (meter)", 200, 2000, 700, 50, key="ov_geo_dist")
                with st.spinner("Haltes in de buurt zoeken…"):
                    stops = nearby_stops(float(lat), float(lon), int(dist))
                if not stops:
                    st.warning("Geen haltes gevonden in deze radius.")
                else:
                    # Sort by a best-effort distance if provided
                    def _dist(s):
                        return float(s.get("Distance", 9e9)) if s.get("Distance") is not None else 9e9
                    stops_sorted = sorted(stops, key=_dist)
                    options = { _stop_label(s): s for s in stops_sorted[:25] }
                    choice = st.selectbox("Dichtbijzijnde haltes", list(options.keys()), key="ov_geo_pick")
                    if st.button("Toon vertrektijden (dichtbij)", use_container_width=True, key="ov_geo_show"):
                        st.session_state.ov_selected_stop = options[choice]
                        st.rerun()
        except Exception as e:
            st.error(f"Live locatie fout: {e}")
