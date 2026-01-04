from __future__ import annotations

import time
from datetime import datetime
from typing import Any

import streamlit as st
from streamlit_keyup import st_keyup
from streamlit_js_eval import streamlit_js_eval
from streamlit_autorefresh import st_autorefresh

from ov_all import (
    search_stops_smart,
    nearby_stops,
    departures_by_stopcode,
    departures_by_nametown,
    normalize_departures,
    group_by_mode,
)

st.set_page_config(page_title="OV Info", page_icon="🚌", layout="wide")


# ----------------------------
# Styling: “busbord” vibe
# ----------------------------
st.markdown(
    """
<style>
.kbm-ov-wrap{background:linear-gradient(180deg,#0b1520,#0d1b2a); border:1px solid rgba(255,255,255,.08);
            border-radius:18px; padding:18px; box-shadow:0 16px 40px rgba(0,0,0,.35);}
.kbm-ov-head{display:flex; align-items:center; justify-content:space-between; gap:14px; flex-wrap:wrap;}
.kbm-ov-title{font-size:36px; font-weight:900; color:#fff; letter-spacing:.3px;}
.kbm-ov-sub{color:rgba(255,255,255,.78); margin-top:4px;}
.kbm-pill{display:inline-flex; align-items:center; gap:8px; padding:8px 12px; border-radius:999px;
         background:rgba(255,255,255,.08); color:#fff; border:1px solid rgba(255,255,255,.10);}
.kbm-board{margin-top:14px; background:#0a0f14; border-radius:16px; padding:12px; border:1px solid rgba(255,255,255,.08);}
.kbm-row{display:grid; grid-template-columns:110px 90px 1fr 120px 90px; gap:10px; padding:10px 10px;
        border-radius:12px; align-items:center;}
.kbm-row + .kbm-row{margin-top:8px;}
.kbm-row.h{background:rgba(255,255,255,.06); color:rgba(255,255,255,.85); font-weight:800; text-transform:uppercase; font-size:12px;}
.kbm-row.r{background:rgba(255,255,255,.03); color:#fff;}
.kbm-time{font-size:22px; font-weight:900;}
.kbm-line{font-size:20px; font-weight:900;}
.kbm-dest{font-size:18px; font-weight:800;}
.kbm-min{font-size:14px; font-weight:900;}
.kbm-plat{font-size:14px; opacity:.9}
.kbm-badge{display:inline-block; padding:4px 8px; border-radius:999px; font-size:12px; font-weight:900; border:1px solid rgba(255,255,255,.14);}
.ok{background:rgba(46,204,113,.18);}
.warn{background:rgba(241,196,15,.18);}
.bad{background:rgba(231,76,60,.18);}
.gray{background:rgba(255,255,255,.08);}
.smallcap{opacity:.75; font-size:12px;}
.kbm-mode{margin-top:16px; font-size:18px; font-weight:900; color:#fff;}
</style>
""",
    unsafe_allow_html=True,
)

st.markdown(
    """
<div class="kbm-ov-wrap">
  <div class="kbm-ov-head">
    <div>
      <div class="kbm-ov-title">🚌 OV Info</div>
      <div class="kbm-ov-sub">Live zoeken tijdens typen + live locatie. Vertrektijden per BUS / TRAM / METRO / TREIN.</div>
    </div>
    <div class="kbm-pill">🔁 Realtime vertrektijden (best effort)</div>
  </div>
</div>
""",
    unsafe_allow_html=True,
)

tab1, tab2 = st.tabs(["🔎 Zoeken", "📍 Live locatie"])


def _stop_label(stop: Any) -> str:
    if not stop:
        return "Onbekende halte"
    if isinstance(stop, str):
        return stop.strip() or "Onbekende halte"
    if isinstance(stop, dict):
        name = (stop.get("ScheduleName") or stop.get("StopName") or stop.get("Name") or "").strip()
        town = (stop.get("Town") or stop.get("City") or stop.get("Locality") or "").strip()
        code = (stop.get("StopCode") or stop.get("Code") or stop.get("Id") or stop.get("StopId") or "").strip()
        if name and town and code:
            return f"{name} — {town} ({code})"
        if name and town:
            return f"{name} — {town}"
        if name and code:
            return f"{name} ({code})"
        if name:
            return name
        if town:
            return town
        if code:
            return code
    return str(stop)


def _pick_stopcode(stop: dict) -> str | None:
    for k in ("StopCode", "Code", "Id", "StopId", "stopCode", "stop_id"):
        v = stop.get(k)
        if v:
            return str(v).strip()
    return None


def _badge_for(dep) -> str:
    # delay/status badge
    if dep.delay_min >= 5:
        return '<span class="kbm-badge bad">+%d</span>' % dep.delay_min
    if dep.delay_min >= 2:
        return '<span class="kbm-badge warn">+%d</span>' % dep.delay_min
    if dep.status and "cancel" in dep.status.lower():
        return '<span class="kbm-badge bad">CANCEL</span>'
    if dep.status and "storing" in dep.status.lower():
        return '<span class="kbm-badge warn">STORING</span>'
    return '<span class="kbm-badge ok">OK</span>'


def _mins_until(dt_utc):
    try:
        now = datetime.utcnow().timestamp()
        return int(round((dt_utc.timestamp() - now) / 60))
    except Exception:
        return None


def _render_mode_block(mode: str, deps, max_rows: int = 10):
    st.markdown(f'<div class="kbm-mode">{mode}</div>', unsafe_allow_html=True)
    st.markdown('<div class="kbm-board">', unsafe_allow_html=True)
    st.markdown(
        """
<div class="kbm-row h">
  <div>tijd</div><div>lijn</div><div>richting</div><div>status</div><div>perron</div>
</div>
""",
        unsafe_allow_html=True,
    )

    if not deps:
        st.markdown("</div>", unsafe_allow_html=True)
        st.info(f"Geen {mode}-vertrekken gevonden.")
        return

    for dep in deps[:max_rows]:
        t_local = dep.departure_time.astimezone().strftime("%H:%M")
        badge = _badge_for(dep)
        mins = _mins_until(dep.departure_time)
        mins_txt = "—" if mins is None else ("NU" if mins <= 0 else f"{mins} min")
        plat = dep.platform or ""

        st.markdown(
            f"""
<div class="kbm-row r">
  <div class="kbm-time">{t_local}</div>
  <div class="kbm-line">{dep.line}</div>
  <div class="kbm-dest">{dep.destination}</div>
  <div class="kbm-min">{badge} {mins_txt}</div>
  <div class="kbm-plat">{plat}</div>
</div>
""",
            unsafe_allow_html=True,
        )

    st.markdown("</div>", unsafe_allow_html=True)


def _fetch_departures_for_stop(stop: dict):
    stopcode = _pick_stopcode(stop)
    if stopcode:
        raw = departures_by_stopcode(stopcode)
        deps = normalize_departures(raw)
        return deps

    # fallback: town + name
    town = (stop.get("Town") or stop.get("City") or stop.get("Locality") or "").strip()
    name = (stop.get("ScheduleName") or stop.get("StopName") or stop.get("Name") or "").strip()
    if town and name:
        raw = departures_by_nametown(town, name)
        deps = normalize_departures(raw)
        return deps

    return []


# ----------------------------
# TAB 1 — Zoeken (live)
# ----------------------------
with tab1:
from streamlit_keyup import st_keyup

q_raw = st_keyup(
    "Zoek halte",
    placeholder="bijv. Utrecht Centraal, Huizen Zuiderzee…",
    key="ov_q"
) or ""

st.caption("Live typing: ✅ (keyup actief)")

    q = q_raw.strip()

    c1, c2, c3, c4 = st.columns([0.35, 0.20, 0.25, 0.20], gap="small")
    with c1:
        live = st.toggle("Live zoeken", value=True)
    with c2:
        max_rows = st.selectbox("Toon", [10, 15, 20], index=0)
    with c3:
        auto_refresh = st.toggle("Auto-refresh (30s)", value=True)
    with c4:
        debug = st.toggle("Debug", value=False)

    if auto_refresh:
        st_autorefresh(interval=30_000, key="ov_autorefresh")

    # Live query throttle
    if live and q:
        last_q = st.session_state.get("ov_last_q", "")
        last_t = float(st.session_state.get("ov_last_t", 0.0))
        if q != last_q and (time.time() - last_t) > 0.20:
            res = search_stops_smart(q)
            # typefout fallback: probeer kortere variant
            if not res and len(q) >= 3:
                for qq in (q[:-1], q[:-2], q.split(" ")[0]):
                    qq = qq.strip()
                    if len(qq) < 2:
                        continue
                    res = search_stops_smart(qq)
                    if res:
                        st.caption(f"Ik vond niets op **{q}**, wel op **{qq}**.")
                        break

            st.session_state["ov_results"] = res
            st.session_state["ov_last_q"] = q
            st.session_state["ov_last_t"] = time.time()

    res = st.session_state.get("ov_results", []) or []
    if res:
        if debug:
            st.json(res[:2])

        # unique labels
        options = {}
        seen = {}
        for s in res[:60]:
            lab = _stop_label(s)
            seen[lab] = seen.get(lab, 0) + 1
            if seen[lab] > 1:
                lab = f"{lab}  #{seen[lab]}"
            options[lab] = s

        choice = st.selectbox("Kies halte", list(options.keys()), key="ov_pick")
        st.session_state["ov_selected"] = options.get(choice)

    stop = st.session_state.get("ov_selected")
    if stop:
        st.markdown("## Vertrektijden")
        st.caption(_stop_label(stop))

        deps = _fetch_departures_for_stop(stop)
        groups = group_by_mode(deps)

        # altijd per modaliteit blokken (voegt overzicht toe)
        # volgorde
        for mode in ["BUS", "TRAM", "METRO", "TREIN"]:
            if mode in groups:
                _render_mode_block(mode, groups[mode], max_rows=max_rows)

        # overige modes
        for mode, lst in groups.items():
            if mode not in {"BUS", "TRAM", "METRO", "TREIN"}:
                _render_mode_block(mode, lst, max_rows=max_rows)


# ----------------------------
# TAB 2 — Live locatie (werkt)
# ----------------------------
with tab2:
    st.caption("Tip: sta locatie toe in je browser (slotje links van de URL).")

    js_geo = """
new Promise((resolve) => {
  navigator.geolocation.getCurrentPosition(
    (p) => resolve({coords:{latitude:p.coords.latitude, longitude:p.coords.longitude, accuracy:p.coords.accuracy}}),
    (e) => resolve({error:true, code:e.code, message:e.message}),
    {enableHighAccuracy:true, timeout:12000, maximumAge:0}
  );
})
"""

    if st.button("📍 Pak live locatie", type="primary", use_container_width=True):
        loc = streamlit_js_eval(js_expressions=js_geo, want_output=True, key="ov_geo")
        st.session_state["ov_loc"] = loc

    loc = st.session_state.get("ov_loc")
    if not loc or (isinstance(loc, dict) and loc.get("error")):
        st.info("Nog geen locatie. Klik op ‘Pak live locatie’ en sta locatie toe.")
        if isinstance(loc, dict) and loc.get("error"):
            st.caption(f"Browser: {loc.get('message')} (code {loc.get('code')})")
        st.stop()

    coords = loc.get("coords", {})
    lat = coords.get("latitude")
    lon = coords.get("longitude")
    if lat is None or lon is None:
        st.warning("Locatie ontvangen maar zonder coords. Probeer opnieuw.")
        st.stop()

    st.success(f"Locatie: {float(lat):.5f}, {float(lon):.5f} • acc ±{coords.get('accuracy','?')} m")
    dist = st.slider("Zoekradius (meter)", 200, 2000, 700, 50)

    stops = nearby_stops(float(lat), float(lon), int(dist))
    if not stops:
        st.warning("Geen haltes gevonden in deze radius.")
        st.stop()

    options = {}
    seen = {}
    for s in stops[:50]:
        lab = _stop_label(s)
        seen[lab] = seen.get(lab, 0) + 1
        if seen[lab] > 1:
            lab = f"{lab}  #{seen[lab]}"
        options[lab] = s

    choice = st.selectbox("Dichtbijzijnde haltes", list(options.keys()))
    st.session_state["ov_selected"] = options.get(choice)

    if st.button("Toon vertrektijden", use_container_width=True):
        st.switch_page("pages/OV_info.py")
