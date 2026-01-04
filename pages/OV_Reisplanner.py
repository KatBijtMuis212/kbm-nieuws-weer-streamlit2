from __future__ import annotations

import time
from datetime import datetime
from urllib.parse import urlencode, quote_plus

import streamlit as st

try:
    from zoneinfo import ZoneInfo
    NL_TZ = ZoneInfo("Europe/Amsterdam")
except Exception:
    NL_TZ = None

st.set_page_config(page_title="OV Reisplanner", page_icon="🧭", layout="wide")

st.markdown("## 🧭 OV Reisplanner")
st.caption("9292-style invulvelden. Resultaten openen in Google Maps / NS / 9292 (gratis). Voor echte ingebouwde reisadviezen is een betaalde Reisadvies API nodig.")


def _to_epoch_seconds(d: datetime) -> int:
    if d.tzinfo is None:
        if NL_TZ:
            d = d.replace(tzinfo=NL_TZ)
    # Google verwacht seconds since epoch UTC
    return int(d.timestamp())


col1, col2 = st.columns([1, 1], gap="large")
with col1:
    origin = st.text_input("Van", placeholder="bijv. Huizen, Utrecht Centraal, Golfstroom 22 Huizen…")
    dest = st.text_input("Naar", placeholder="bijv. Amsterdam Centraal…")

with col2:
    mode_when = st.radio("Wanneer", ["Vertrek", "Aankomst"], horizontal=True)
    d = st.date_input("Datum", value=datetime.now().date())
    t = st.time_input("Tijd", value=datetime.now().time().replace(second=0, microsecond=0))

st.markdown("### Opties")
c3, c4, c5 = st.columns([1, 1, 1], gap="large")
with c3:
    allow_bus = st.checkbox("Bus", value=True)
    allow_tram = st.checkbox("Tram", value=True)
with c4:
    allow_metro = st.checkbox("Metro", value=True)
    allow_train = st.checkbox("Trein", value=True)
with c5:
    less_walking = st.checkbox("Minder lopen (Google)", value=False)
    max_alts = st.selectbox("Aantal opties (Google)", [1, 2, 3], index=2)

# Let op: zonder betaalde route-API kunnen we modaliteiten niet 100% afdwingen.
# We gebruiken deze selectie als “hint” voor de gebruiker + Google preference.

go = st.button("Plan reis", type="primary", use_container_width=True)

if go:
    if not origin.strip() or not dest.strip():
        st.warning("Vul ‘Van’ en ‘Naar’ in.")
        st.stop()

    dt_local = datetime.combine(d, t)
    if NL_TZ:
        dt_local = dt_local.replace(tzinfo=NL_TZ)

    epoch = _to_epoch_seconds(dt_local)

    # Google Maps transit link
    # api=1 is for Maps URLs. travelmode=transit. departure_time/arrival_time (epoch seconds).
    g_params = {
        "api": "1",
        "origin": origin,
        "destination": dest,
        "travelmode": "transit",
    }
    if mode_when == "Vertrek":
        g_params["departure_time"] = str(epoch)
    else:
        g_params["arrival_time"] = str(epoch)

    # routing preference (not perfect, but helps)
    if less_walking:
        g_params["transit_routing_preference"] = "less_walking"

    g_url = "https://www.google.com/maps/dir/?" + urlencode(g_params, quote_via=quote_plus)

    # NS reisplanner (we geven een startlink; NS gebruikt veel JS)
    ns_url = "https://www.ns.nl/reisplanner/"

    # 9292 reisplanner (startlink)
    nine_url = "https://9292.nl/reisplanner"

    st.markdown("### Opties")
    st.link_button("🗺️ Open in Google Maps (OV)", g_url, use_container_width=True)
    st.link_button("🚆 Open NS Reisplanner", ns_url, use_container_width=True)
    st.link_button("🚌 Open 9292 Reisplanner", nine_url, use_container_width=True)

    st.markdown("### Jouw gekozen vervoersmiddelen (hint)")
    chosen = []
    if allow_bus: chosen.append("Bus")
    if allow_tram: chosen.append("Tram")
    if allow_metro: chosen.append("Metro")
    if allow_train: chosen.append("Trein")
    st.info(" • ".join(chosen) if chosen else "Geen selectie (alles uit).")

    st.caption("Google Maps route-data komt uit GTFS en partners; deep link toont meestal meerdere alternatieven. Voor echte route-opties *in jouw app* is een route-API nodig.")
