
import streamlit as st
from datetime import datetime
from streamlit_js_eval import streamlit_js_eval

import time
import collections
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

def _stop_label(stop) -> str:
    """Maak een leesbare label-string voor een halte.

    API-responses kunnen dicts zijn, maar soms ook strings (of None). We vangen dat netjes af.
    """
    if isinstance(stop, str):
        s = stop.strip()
        return s if s else "Onbekende halte"
    if not isinstance(stop, dict):
        return "Onbekende halte"

    name = stop.get("ScheduleName") or stop.get("StopName") or stop.get("Name") or "Onbekende halte"
    town = stop.get("Town") or stop.get("Place") or ""
    code = stop.get("StopCode") or stop.get("Code") or ""

    name = str(name).strip() if name is not None else "Onbekende halte"
    town = str(town).strip() if town is not None else ""
    code = str(code).strip() if code is not None else ""

    if town and code:
        return f"{name} — {town} ({code})"
    if town:
        return f"{name} — {town}"
    if code:
        return f"{name} ({code})"
    return name


def _normalize_stop_results(res):
    """Maak van wat de API ook teruggeeft altijd een lijst met dicts/strings."""
    if res is None:
        return []
    # Soms: {"Stops": [...]} of {"results": [...]}
    if isinstance(res, dict):
        for k in ("Stops", "stops", "Results", "results", "data"):
            if k in res and isinstance(res.get(k), list):
                return res.get(k) or []
        # fallback: één record
        return [res]
    if isinstance(res, list):
        return res
    # fallback: één string/waarde
    return [res]


def _build_options(res_list):
    """Bouw een stabiele, unieke mapping label -> record."""
    options = {}
    counts = collections.defaultdict(int)

    for item in res_list:
        if item is None:
            continue
        label = _stop_label(item)
        counts[label] += 1
        key = label if counts[label] == 1 else f"{label} · #{counts[label]}"
        options[key] = item
    return options

with tab1:
    q = st.text_input(
        "Zoek halte",
        placeholder="bijv. Huiz...derzee, Amsterdam Centraal, Gouda Station…",
        key="ov_q",
    ).strip()

    colA, colB, colC = st.columns([0.45, 0.30, 0.25], gap="small")
    with colA:
        go = st.button("Zoek", type="primary", use_container_width=True)
    with colB:
        auto = st.toggle("Zoek tijdens typen", value=True)
    with colC:
        debug = st.toggle("Debug tonen", value=False)

    # Auto-zoeken: laat de API niet op élke letter volledig losgaan.
    # We zoeken als de query verandert én minstens 2 tekens heeft, met een kleine throttle.
    minlen = 2
    now = time.time()
    last_q = st.session_state.get("ov_last_q", "")
    last_t = float(st.session_state.get("ov_last_t", 0.0))

    should_search = False
    if go and q:
        should_search = True
    elif auto and q and len(q) >= minlen and q != last_q and (now - last_t) >= 0.8:
        should_search = True

    if should_search:
        try:
            with st.spinner("Zoeken… even geduld (max ~12 sec)."):
                res = search_stops_smart(q)
            st.session_state.ov_last_results = res
            st.session_state.ov_last_q = q
            st.session_state.ov_last_t = now
        except Exception as e:
            st.session_state.ov_last_results = []
            st.error(f"Zoeken faalde: {e}")

    res_raw = st.session_state.get("ov_last_results", [])
    res = _normalize_stop_results(res_raw)

    if res:
        st.caption(f"Aantal resultaten: {len(res)}")
        if debug:
            st.markdown("**Voorbeeld record:**")
            st.json(res[0])

        options = _build_options(res)
        if options:
            choice = st.selectbox("Kies halte", list(options.keys()), key="ov_pick")
            if st.button("Toon vertrektijden", use_container_width=True, key="ov_show_depart"):
                st.session_state.ov_selected_stop = options[choice]
        else:
            st.warning("Geen bruikbare halte-items gevonden in de API-respons.")

    sel = st.session_state.get("ov_selected_stop")
    if sel:
        st.markdown("## Vertrektijden")
        st.caption(_stop_label(sel))
        try:
            stopcode = sel.get("StopCode") if isinstance(sel, dict) else None
            if not stopcode:
                st.error("Ik kan geen haltecode vinden bij deze keuze. Probeer een andere halte (of typ iets specifieker).")
            else:
                with st.spinner("Vertrektijden ophalen…"):
                    dep = departures_by_stopcode(stopcode)
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
                    options = _build_options(stops_sorted[:25])
                    choice = st.selectbox("Dichtbijzijnde haltes", list(options.keys()), key="ov_geo_pick")
                    if st.button("Toon vertrektijden (dichtbij)", use_container_width=True, key="ov_geo_show"):
                        st.session_state.ov_selected_stop = options[choice]
                        st.rerun()
        except Exception as e:
            st.error(f"Live locatie fout: {e}")
