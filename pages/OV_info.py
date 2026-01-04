# pages/OV_info.py — OV Info + live locatie + type-ahead zoeken
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

import streamlit as st
from streamlit_autorefresh import st_autorefresh

# type-ahead (key-up). Als het pakket ontbreekt, vallen we terug op text_input.
try:
    from streamlit_keyup import st_keyup
except Exception:
    st_keyup = None  # type: ignore

try:
    from streamlit_js_eval import streamlit_js_eval
except Exception:
    streamlit_js_eval = None  # type: ignore

# OV helpers uit common.py
from common import (
    vt_get,
)

VT_STOP_SEARCH = "/stop/_nametown/{town}/{name}"
VT_STOP_SEARCH_Q = "/stop/_name/{name}"
VT_DEPARTURES = "/departures/{stopcode}"

def _stop_label(stop: Any) -> str:
    if not isinstance(stop, dict):
        return "Onbekende halte"
    name = stop.get("ScheduleName") or stop.get("StopName") or stop.get("Name") or "Onbekende halte"
    town = stop.get("Town") or stop.get("City") or stop.get("Place") or ""
    code = stop.get("StopCode") or stop.get("Code") or ""
    bits = [str(name).strip()]
    if town:
        bits.append(str(town).strip())
    if code:
        bits.append(str(code).strip())
    return " • ".join([b for b in bits if b])

def _safe_list(x: Any) -> List[dict]:
    if x is None:
        return []
    if isinstance(x, list):
        return [y for y in x if isinstance(y, dict)]
    if isinstance(x, dict):
        return [x]
    return []

@st.cache_data(ttl=45, show_spinner=False)
def search_stops(q: str) -> List[dict]:
    q = (q or "").strip()
    if not q:
        return []
    # Vertrektijd.info heeft verschillende endpoints; we proberen eerst _name, dan town+name parse.
    try:
        data = vt_get(VT_STOP_SEARCH_Q.format(name=q))
        res = data.get("Stops") or data.get("stops") or data.get("Result") or data
        stops = _safe_list(res)
        if stops:
            return stops[:25]
    except Exception:
        pass
    # fallback: als gebruiker "Huizen, Busstation" etc typt, splitten we grof
    try:
        parts = [p.strip() for p in q.split(",") if p.strip()]
        if len(parts) >= 2:
            town, name = parts[0], ",".join(parts[1:])
            data = vt_get(VT_STOP_SEARCH.format(town=town, name=name))
            res = data.get("Stops") or data.get("stops") or data.get("Result") or data
            return _safe_list(res)[:25]
    except Exception:
        pass
    return []

@st.cache_data(ttl=30, show_spinner=False)
def departures_by_stopcode(stopcode: str) -> List[dict]:
    data = vt_get(VT_DEPARTURES.format(stopcode=stopcode))
    res = data.get("Departures") or data.get("departures") or data.get("Result") or data
    return _safe_list(res)

def _km(a: float, b: float, c: float, d: float) -> float:
    # haversine
    R = 6371.0
    phi1 = math.radians(a)
    phi2 = math.radians(c)
    dphi = math.radians(c - a)
    dl = math.radians(d - b)
    h = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dl/2)**2
    return 2*R*math.asin(math.sqrt(h))

def _try_get_geoloc() -> Optional[Tuple[float,float]]:
    if streamlit_js_eval is None:
        return None
    try:
        # streamlit-js-eval geeft dict terug met lat/lon
        loc = streamlit_js_eval(js_expressions="navigator.geolocation.getCurrentPosition((pos)=>pos.coords)", key="geo", want_output=True)
        if isinstance(loc, dict):
            lat = loc.get("latitude") or loc.get("lat")
            lon = loc.get("longitude") or loc.get("lon") or loc.get("lng")
            if lat and lon:
                return float(lat), float(lon)
    except Exception:
        return None
    return None

def _departures_table(dep: List[dict]):
    rows = []
    for d in dep[:10]:
        line = d.get("LinePublicNumber") or d.get("Line") or ""
        dest = d.get("DestinationName") or d.get("Destination") or ""
        time_s = d.get("ExpectedDepartureTime") or d.get("TargetDepartureTime") or d.get("DepartureTime") or ""
        delay = d.get("Delay") or d.get("DelayMinutes") or 0
        platform = d.get("Platform") or d.get("StopPoint") or ""
        mode = d.get("TransportType") or d.get("Transport") or ""
        rows.append({
            "Lijn": line,
            "Richting": dest,
            "Vertrek": str(time_s)[11:16] if isinstance(time_s, str) and len(time_s) >= 16 else str(time_s),
            "Perron": platform,
            "Modaliteit": mode,
            "Δ min": delay,
        })
    st.dataframe(rows, use_container_width=True, hide_index=True)

st.set_page_config(page_title="OV Info", page_icon="🚌", layout="wide")
st.title("🚌 OV Info")
st.caption("Zoek een halte op naam, of gebruik live locatie om haltes in de buurt te tonen. (Auto-refresh 30s)")

st_autorefresh(interval=30_000, key="ov_refresh")

tab1, tab2 = st.tabs(["🔎 Zoeken", "📍 Live locatie"])

with tab1:
    if st_keyup:
        q = st_keyup("Zoek halte", key="ov_q", debounce=250, placeholder="bijv. Huizen Busstation, Utrecht CS, Gouda…")
    else:
        q = st.text_input("Zoek halte", key="ov_q_fallback", placeholder="bijv. Huizen Busstation, Utrecht CS, Gouda…")

    stops = search_stops(q) if q and len(q) >= 2 else []
    if q and len(q) >= 2:
        if stops:
            options = { _stop_label(s): s for s in stops }
            sel_label = st.selectbox("Kies halte", list(options.keys()), key="ov_sel_label")
            st.session_state["ov_selected_stop"] = options.get(sel_label)
        else:
            st.info("Geen haltes gevonden. Tip: probeer alleen plaatsnaam of alleen halte-naam.")

    sel = st.session_state.get("ov_selected_stop")
    if sel:
        st.subheader("Volgende 10 ritten")
        st.caption(_stop_label(sel))
        stopcode = sel.get("StopCode") if isinstance(sel, dict) else None
        if not stopcode:
            st.warning("Deze keuze heeft geen StopCode. Kies een andere halte uit de lijst.")
        else:
            try:
                dep = departures_by_stopcode(stopcode)
                if dep:
                    _departures_table(dep)
                else:
                    st.warning("Geen ritten gevonden (mogelijk tijdelijk geen realtime data).")
            except Exception as e:
                st.error(f"Vertrektijd.info fout: {e}")

with tab2:
    st.write("Klik op **Sta locatie toe** in je browser. Als permissies uit staan: site-instellingen → locatie → toestaan.")
    loc = _try_get_geoloc()
    if not loc:
        st.warning("Geen locatie gekregen. Controleer browser-permissies.")
    else:
        lat, lon = loc
        st.success(f"Locatie: {lat:.5f}, {lon:.5f}")
        # Met alleen Vertrektijd.info hebben we geen 'nearby stops' endpoint in jouw set.
        # Daarom: we vragen de gebruiker om een plaatsnaam en gebruiken dat als nearby-basis.
        town = st.text_input("Plaats (voor haltes in de buurt)", value="Huizen", key="ov_near_town")
        name = st.text_input("Filter (optioneel)", value="", key="ov_near_name")
        q2 = f"{town}, {name}".strip().strip(",")
        stops2 = search_stops(q2) if town else []
        if stops2:
            # als stops coords hebben, sorteer op afstand
            scored = []
            for s in stops2:
                slat = s.get("Latitude") or s.get("lat")
                slon = s.get("Longitude") or s.get("lon") or s.get("lng")
                if slat and slon:
                    try:
                        dist = _km(lat, lon, float(slat), float(slon))
                    except Exception:
                        dist = 9999.0
                else:
                    dist = 9999.0
                scored.append((dist, s))
            scored.sort(key=lambda x: x[0])
            options = { f"{_stop_label(s)}" + (f" • {d:.1f} km" if d < 9999 else ""): s for d,s in scored[:25] }
            sel_label = st.selectbox("Dichtbij (gesorteerd)", list(options.keys()), key="ov_near_sel_label")
            sel = options.get(sel_label)
            if sel:
                st.session_state["ov_selected_stop"] = sel
                stopcode = sel.get("StopCode") if isinstance(sel, dict) else None
                if stopcode:
                    dep = departures_by_stopcode(stopcode)
                    if dep:
                        _departures_table(dep)
                    else:
                        st.warning("Geen ritten gevonden (mogelijk tijdelijk geen realtime data).")
        else:
            st.info("Geen haltes gevonden voor deze plaatsnaam.")
