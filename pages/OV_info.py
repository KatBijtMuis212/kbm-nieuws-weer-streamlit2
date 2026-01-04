import time
from datetime import datetime

import streamlit as st
from streamlit_js_eval import streamlit_js_eval

from ov_api import search_stops_smart, nearby_stops, departures_by_stopcode, departures_by_nametown

st.set_page_config(page_title="OV Info", page_icon="🚌", layout="wide")

# ----------------------------
# Styling: busbord vibe
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
.kbm-row{display:grid; grid-template-columns:110px 90px 1fr 110px 110px; gap:10px; padding:10px 10px;
        border-radius:12px; align-items:center;}
.kbm-row + .kbm-row{margin-top:8px;}
.kbm-row.h{background:rgba(255,255,255,.06); color:rgba(255,255,255,.85); font-weight:800; text-transform:uppercase; font-size:12px;}
.kbm-row.r{background:rgba(255,255,255,.03); color:#fff;}
.kbm-time{font-size:22px; font-weight:900;}
.kbm-line{font-size:20px; font-weight:900;}
.kbm-dest{font-size:18px; font-weight:800;}
.kbm-min{font-size:16px; font-weight:900;}
.kbm-plat{font-size:14px; opacity:.9}
.kbm-badge{display:inline-block; padding:4px 8px; border-radius:999px; font-size:12px; font-weight:900; border:1px solid rgba(255,255,255,.14);}
.ok{background:rgba(46,204,113,.18);}
.warn{background:rgba(241,196,15,.18);}
.bad{background:rgba(231,76,60,.18);}
.smallcap{opacity:.75; font-size:12px;}
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
      <div class="kbm-ov-sub">Zoek een halte op naam (live tijdens typen) of gebruik live locatie voor haltes in de buurt.</div>
    </div>
    <div class="kbm-pill">🔑 Vertrektijd.info API</div>
  </div>
</div>
""",
    unsafe_allow_html=True,
)

tab1, tab2 = st.tabs(["🔎 Zoeken", "📍 Live locatie"])


# ----------------------------
# Helpers
# ----------------------------
def _fmt_dt(s: str) -> str:
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        return dt.astimezone().strftime("%H:%M")
    except Exception:
        return s or "—"


def _mins_until(iso: str) -> int | None:
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone()
        mins = int(round((dt - datetime.now().astimezone()).total_seconds() / 60))
        return mins
    except Exception:
        return None


def _stop_obj(stop):
    if isinstance(stop, dict) and "Stop" in stop and isinstance(stop.get("Stop"), dict):
        return stop["Stop"]
    return stop


def _get_stopcode(stop) -> str | None:
    stop = _stop_obj(stop)
    if not isinstance(stop, dict):
        return None
    for k in ("StopCode", "Code", "Id", "StopId", "stopCode", "stop_id"):
        v = stop.get(k)
        if v:
            return str(v).strip()
    return None


def _get_town_and_name(stop) -> tuple[str | None, str | None]:
    stop = _stop_obj(stop)
    if not isinstance(stop, dict):
        return (None, None)
    town = (stop.get("Town") or stop.get("City") or stop.get("Locality") or "").strip() or None
    name = (stop.get("ScheduleName") or stop.get("StopName") or stop.get("Name") or "").strip() or None
    return (town, name)


def _stop_label(stop) -> str:
    if not stop:
        return "Onbekende halte"
    if isinstance(stop, str):
        return stop.strip() or "Onbekende halte"
    stop = _stop_obj(stop)
    if isinstance(stop, dict):
        name = (stop.get("ScheduleName") or stop.get("StopName") or stop.get("Name") or "").strip()
        town = (stop.get("Town") or stop.get("City") or stop.get("Locality") or "").strip()
        code = _get_stopcode(stop) or ""
        if name and town and code:
            return f"{name} — {town} ({code})"
        if name and town:
            return f"{name} — {town}"
        if name and code:
            return f"{name} ({code})"
        if name:
            return name
        if town and code:
            return f"{town} ({code})"
        if town:
            return town
        if code:
            return code
    return str(stop)


def _departures_to_rows(dep_json: dict) -> list[dict]:
    btmf = dep_json.get("BTMF") or []
    train = dep_json.get("TRAIN") or []
    rows = []

    def push(d: dict, typ: str):
        exp = d.get("ExpectedDeparture") or d.get("PlannedDeparture") or ""
        mins = _mins_until(exp) if exp else None
        rows.append(
            {
                "time": _fmt_dt(exp),
                "line": d.get("LineNumber") or d.get("LineName") or "—",
                "dest": d.get("Destination") or "—",
                "mins": mins,
                "plat": d.get("Platform") or "",
                "typ": d.get("TransportType") or typ,
                "status": d.get("VehicleStatus") or "",
                "raw": d,
            }
        )

    for block in btmf:
        for d in (block.get("Departures") or []):
            push(d, "BTMF")
    for block in train:
        for d in (block.get("Departures") or []):
            push(d, "TRAIN")

    # sort
    rows.sort(key=lambda r: (9999 if r["mins"] is None else r["mins"]))
    return rows


def _render_board(rows: list[dict], max_rows: int = 16):
    st.markdown('<div class="kbm-board">', unsafe_allow_html=True)
    st.markdown(
        """
<div class="kbm-row h">
  <div>tijd</div><div>lijn</div><div>richting</div><div>vertrekt</div><div>perron</div>
</div>
""",
        unsafe_allow_html=True,
    )

    if not rows:
        st.info("Geen vertrektijden gevonden (nu).")
        st.markdown("</div>", unsafe_allow_html=True)
        return

    for r in rows[:max_rows]:
        mins = r["mins"]
        if mins is None:
            badge = '<span class="kbm-badge warn">?</span>'
            mins_txt = "—"
        elif mins <= 0:
            badge = '<span class="kbm-badge bad">NU</span>'
            mins_txt = "nu"
        elif mins <= 3:
            badge = '<span class="kbm-badge warn">BINNENKORT</span>'
            mins_txt = f"{mins} min"
        else:
            badge = '<span class="kbm-badge ok">OK</span>'
            mins_txt = f"{mins} min"

        st.markdown(
            f"""
<div class="kbm-row r">
  <div class="kbm-time">{r['time']}</div>
  <div class="kbm-line">{r['line']}</div>
  <div class="kbm-dest">{r['dest']} <span class="smallcap">({r['typ']})</span></div>
  <div class="kbm-min">{badge} {mins_txt}</div>
  <div class="kbm-plat">{r['plat']}</div>
</div>
""",
            unsafe_allow_html=True,
        )

    st.markdown("</div>", unsafe_allow_html=True)


def _search_live(q: str) -> list[dict]:
    """Search with type-o tolerance: if no results, try trimmed variants."""
    q = (q or "").strip()
    if not q:
        return []

    raw = search_stops_smart(q)

    # typefout? probeer korter
    if not raw and len(q) >= 3:
        for qq in (q[:-1], q[:-2], q.split(" ")[0]):
            qq = (qq or "").strip()
            if len(qq) < 2:
                continue
            raw = search_stops_smart(qq)
            if raw:
                st.caption(f"Ik vond niets op **{q}** — wel resultaten op **{qq}**.")
                break

    # normaliseer naar list[dict]
    res = []
    if isinstance(raw, dict):
        raw = raw.get("Stops") or raw.get("results") or raw.get("stops") or []
    if isinstance(raw, list):
        for item in raw:
            if isinstance(item, dict):
                res.append(item)
            elif isinstance(item, str) and item.strip():
                res.append({"StopName": item.strip()})
    elif isinstance(raw, str) and raw.strip():
        res = [{"StopName": raw.strip()}]
    return res


# ----------------------------
# TAB 1 — Zoeken (live typing)
# ----------------------------
with tab1:
    # Live typing via st_keyup
    q_raw = ""
    try:
        from streamlit_keyup import st_keyup  # type: ignore

        q_raw = st_keyup(
            "Zoek halte",
            placeholder="bijv. Utrecht Centraal, Huizen Zuiderzee, Gouda Station…",
            key="ov_q_keyup",
        ) or ""
    except Exception:
        q_raw = st.text_input(
            "Zoek halte",
            placeholder="Installeer streamlit-keyup voor live typen…",
            key="ov_q",
        ) or ""

    q = q_raw.strip()

    colA, colB, colC = st.columns([0.55, 0.25, 0.20], gap="small")
    with colA:
        auto = st.toggle("Live zoeken", value=True)
    with colB:
        auto_refresh = st.toggle("Auto-refresh vertrektijden", value=False)
    with colC:
        debug = st.toggle("Debug", value=False)

    # throttle live searches
    last_q = st.session_state.get("ov_last_q", "")
    last_t = float(st.session_state.get("ov_last_t", 0.0))

    if auto and q and q != last_q and (time.time() - last_t) > 0.25:
        with st.spinner("Zoeken…"):
            res = _search_live(q)
        st.session_state["ov_last_results"] = res
        st.session_state["ov_last_q"] = q
        st.session_state["ov_last_t"] = time.time()

    res = st.session_state.get("ov_last_results", []) or []
    if res:
        st.caption(f"Aantal resultaten: {len(res)}")

        if debug:
            st.json(res[0])

        # labels -> item (uniques)
        options = {}
        counts = {}
        for s in res:
            label = _stop_label(s)
            counts[label] = counts.get(label, 0) + 1
            if counts[label] > 1:
                label = f"{label}  #{counts[label]}"
            options[label] = s

        choice = st.selectbox("Kies halte", list(options.keys()), key="ov_pick")
        st.session_state["ov_selected_stop"] = options.get(choice)

    sel = st.session_state.get("ov_selected_stop")
    if sel:
        st.markdown("## Vertrektijden")
        st.caption(_stop_label(sel))

        # optioneel auto-refresh
        if auto_refresh:
            st.caption("⏱️ Auto-refresh staat aan (elke 20 sec).")
            time.sleep(0.1)
            st.rerun()

        try:
            with st.spinner("Vertrektijden ophalen…"):
                stopcode = _get_stopcode(sel)

                dep_rows = []
                if stopcode:
                    dep = departures_by_stopcode(stopcode)
                    dep_rows = _departures_to_rows(dep) if isinstance(dep, dict) else []
                else:
                    # Fallback: probeer departures op town+stopnaam
                    town, name = _get_town_and_name(sel)
                    if town and name:
                        raw_list = departures_by_nametown(town, name)
                        # best-effort parse: maak simpele rows
                        if isinstance(raw_list, list):
                            for d in raw_list:
                                if not isinstance(d, dict):
                                    continue
                                exp = d.get("ExpectedDeparture") or d.get("PlannedDeparture") or d.get("departure") or ""
                                mins = _mins_until(exp) if exp else None
                                dep_rows.append(
                                    {
                                        "time": _fmt_dt(exp),
                                        "line": d.get("LineNumber") or d.get("line") or d.get("LineName") or "—",
                                        "dest": d.get("Destination") or d.get("destination") or "—",
                                        "mins": mins,
                                        "plat": d.get("Platform") or d.get("platform") or "",
                                        "typ": d.get("TransportType") or d.get("type") or "—",
                                        "status": d.get("VehicleStatus") or "",
                                        "raw": d,
                                    }
                                )
                            dep_rows.sort(key=lambda r: (9999 if r["mins"] is None else r["mins"]))
                    else:
                        st.warning("Deze halte mist StopCode én (plaats/naam). Kies een andere optie uit de lijst.")

            _render_board(dep_rows)

        except Exception as e:
            st.error(f"Vertrektijd.info fout: {e}")


# ----------------------------
# TAB 2 — Live locatie (Promise JS)
# ----------------------------
with tab2:
    st.caption("Zorg dat je browser locatie-permissie aan staat. In Streamlit Cloud moet je soms 1x opnieuw toestaan.")

    js_geo = """
new Promise((resolve) => {
  navigator.geolocation.getCurrentPosition(
    (p) => resolve({coords:{latitude:p.coords.latitude, longitude:p.coords.longitude, accuracy:p.coords.accuracy}}),
    (e) => resolve({error:true, code:e.code, message:e.message}),
    {enableHighAccuracy:true, timeout:12000, maximumAge:0}
  );
})
"""

    if st.button("📍 Pak live locatie", type="primary", use_container_width=True, key="ov_geo_btn"):
        loc = streamlit_js_eval(js_expressions=js_geo, want_output=True, key="ov_geo")
        st.session_state["ov_live_loc"] = loc

    loc = st.session_state.get("ov_live_loc")
    if not loc or (isinstance(loc, dict) and loc.get("error")):
        st.info("Geen locatie gekregen. Check permissies in je browser (slotje links van de URL).")
        if isinstance(loc, dict) and loc.get("error"):
            st.caption(f"Browser error: {loc.get('message')} (code {loc.get('code')})")
        st.stop()

    coords = loc.get("coords", {}) if isinstance(loc, dict) else {}
    lat = coords.get("latitude")
    lon = coords.get("longitude")
    if lat is None or lon is None:
        st.info("Geen locatie gekregen. Check permissies in je browser.")
        st.stop()

    st.success(f"Locatie: {float(lat):.5f}, {float(lon):.5f}  • acc ±{coords.get('accuracy','?')} m")

    dist = st.slider("Zoekradius (meter)", 200, 2000, 700, 50, key="ov_geo_dist")

    with st.spinner("Haltes in de buurt zoeken…"):
        stops = nearby_stops(float(lat), float(lon), int(dist))

    if not stops:
        st.warning("Geen haltes gevonden in deze radius.")
        st.stop()

    # sort best-effort on Distance
    def _dist(s):
        try:
            return float(_stop_obj(s).get("Distance", 9e9))
        except Exception:
            return 9e9

    stops_sorted = sorted(stops, key=_dist)

    options = {}
    counts = {}
    for s in stops_sorted[:40]:
        label = _stop_label(s)
        counts[label] = counts.get(label, 0) + 1
        if counts[label] > 1:
            label = f"{label}  #{counts[label]}"
        options[label] = s

    choice = st.selectbox("Dichtbijzijnde haltes", list(options.keys()), key="ov_geo_pick")
    sel = options.get(choice)
    st.session_state["ov_selected_stop"] = sel

    if st.button("Toon vertrektijden", use_container_width=True, key="ov_geo_show"):
        st.rerun()
