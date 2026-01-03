import math
import re
from datetime import datetime, timezone

import requests
import streamlit as st
from bs4 import BeautifulSoup

UA = "Mozilla/5.0 (KbMNieuwsStreamlit/2.0; +https://katbijtmuis.nl)"


# ---------------------------
# Helpers
# ---------------------------
def wx_emoji(code: int) -> str:
    # Open-Meteo weather codes (rough mapping)
    if code == 0:
        return "☀️"
    if code in (1, 2):
        return "🌤️"
    if code == 3:
        return "☁️"
    if code in (45, 48):
        return "🌫️"
    if code in (51, 53, 55, 56, 57):
        return "🌦️"
    if code in (61, 63, 65, 66, 67):
        return "🌧️"
    if code in (71, 73, 75, 77, 85, 86):
        return "🌨️"
    if code in (80, 81, 82):
        return "🌦️"
    if code in (95, 96, 99):
        return "⛈️"
    return "🌡️"


def wx_label(code: int) -> str:
    mapping = {
        0: "Helder",
        1: "Overwegend helder",
        2: "Half bewolkt",
        3: "Bewolkt",
        45: "Mist",
        48: "Rijpvormende mist",
        51: "Lichte motregen",
        53: "Motregen",
        55: "Zware motregen",
        56: "Lichte ijzige motregen",
        57: "IJzige motregen",
        61: "Lichte regen",
        63: "Regen",
        65: "Zware regen",
        66: "Lichte ijzige regen",
        67: "IJzige regen",
        71: "Lichte sneeuw",
        73: "Sneeuw",
        75: "Zware sneeuw",
        77: "Sneeuwkorrels",
        80: "Lichte buien",
        81: "Buien",
        82: "Zware buien",
        85: "Lichte sneeuwbuien",
        86: "Sneeuwbuien",
        95: "Onweer",
        96: "Onweer met hagel",
        99: "Zwaar onweer met hagel",
    }
    return mapping.get(code, "Weer")


def fx_css(code: int) -> str:
    # Lightweight “particles” depending on weather
    # (Pure CSS; Streamlit-safe)
    if code == 0:
        # sun shimmer
        return """
.kbm-sky{position:relative;overflow:hidden;border-radius:18px}
.kbm-sunbeam{position:absolute;inset:-30%;background:radial-gradient(circle,rgba(255,255,255,.35),transparent 55%);animation:spin 18s linear infinite}
@keyframes spin{from{transform:rotate(0deg)}to{transform:rotate(360deg)}}
"""

    if code in (1, 2, 3):
        # slow clouds
        return """
.kbm-sky{position:relative;overflow:hidden;border-radius:18px}
.kbm-cloud{position:absolute;top:12%;left:-30%;width:60%;height:40%;background:rgba(255,255,255,.22);filter:blur(2px);border-radius:999px;animation:drift 22s linear infinite}
.kbm-cloud.b{top:42%;width:50%;opacity:.75;animation-duration:28s}
@keyframes drift{to{left:110%}}
"""

    if code in (61, 63, 65, 80, 81, 82, 51, 53, 55):
        # rain
        return """
.kbm-sky{position:relative;overflow:hidden;border-radius:18px}
.kbm-rain{position:absolute;inset:0;background-image:linear-gradient(transparent 0%,rgba(255,255,255,.18) 50%,transparent 100%);
background-size:10px 40px;animation:rain 0.55s linear infinite;opacity:.65;mix-blend-mode:screen}
@keyframes rain{from{background-position:0 0}to{background-position:0 40px}}
"""

    if code in (71, 73, 75, 85, 86, 77):
        # snow
        return """
.kbm-sky{position:relative;overflow:hidden;border-radius:18px}
.kbm-snow{position:absolute;inset:0;background-image:radial-gradient(rgba(255,255,255,.7) 1px,transparent 1.5px);
background-size:18px 18px;animation:snow 6s linear infinite;opacity:.55}
@keyframes snow{from{background-position:0 0}to{background-position:0 120px}}
"""

    if code in (95, 96, 99):
        # lightning pulse
        return """
.kbm-sky{position:relative;overflow:hidden;border-radius:18px}
.kbm-flash{position:absolute;inset:0;background:rgba(255,255,255,.18);animation:flash 4.5s infinite}
@keyframes flash{0%,88%,100%{opacity:0}90%{opacity:.9}92%{opacity:0}95%{opacity:.6}}
"""

    return """.kbm-sky{position:relative;overflow:hidden;border-radius:18px}"""


@st.cache_data(ttl=900, show_spinner=False)
def geocode(q: str):
    url = "https://geocoding-api.open-meteo.com/v1/search"
    r = requests.get(url, params={"name": q, "count": 5, "language": "nl", "format": "json"}, headers={"User-Agent": UA}, timeout=20)
    r.raise_for_status()
    data = r.json()
    return data.get("results", []) or []


@st.cache_data(ttl=600, show_spinner=False)
def forecast(lat: float, lon: float):
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "timezone": "auto",
        "current": "temperature_2m,weather_code,wind_speed_10m",
        "hourly": "temperature_2m,precipitation_probability,precipitation,weather_code,wind_speed_10m",
        "daily": "temperature_2m_max,temperature_2m_min,weather_code,precipitation_probability_max",
        "forecast_days": 7,
    }
    r = requests.get(url, params=params, headers={"User-Agent": UA}, timeout=20)
    r.raise_for_status()
    return r.json()


@st.cache_data(ttl=1800, show_spinner=False)
def knmi_text():
    try:
        url = "https://www.knmi.nl/nederland-nu/weer/verwachtingen"
        r = requests.get(url, headers={"User-Agent": UA}, timeout=20)
        r.raise_for_status()

        soup = BeautifulSoup(r.text, "html.parser")

        for t in soup(["script", "style", "noscript", "svg"]):
            t.decompose()

        main = soup.find("main")
        node = main if main else soup.body

        parts = []
        for el in node.find_all(["h2", "h3", "p", "li"]):
            txt = el.get_text(" ", strip=True)
            if not txt:
                continue

            low = txt.lower()
            bad = [
                "function ",
                "readcookie",
                "document.cookie",
                "datalayer",
                "verouderde browser",
                "naar de hoofd content",
                "cookie",
                "privacy",
                "tag manager",
                "stg_debug",
            ]
            if any(b in low for b in bad):
                continue

            if len(txt) < 25 and not txt.endswith(":"):
                continue

            parts.append(txt)

        out = []
        seen = set()
        for p in parts:
            key = p[:80].lower()
            if key in seen:
                continue
            seen.add(key)
            out.append(p)

        text = "\n\n".join(out[:40]).strip()
        return text if len(text) > 300 else None
    except Exception:
        return None


def pick_place_ui():
    st.markdown("### Weer")
    st.caption("Gratis, realtime-ish, zonder API-key. Radar via RainViewer. Verwachting via Open-Meteo. Tekst via KNMI (best effort).")

    c1, c2, c3 = st.columns([1.2, 0.6, 0.6], gap="small")
    with c1:
        q = st.text_input("Zoek plaats", value=st.session_state.get("wx_q", "Huizen"), placeholder="bijv. Huizen, Amsterdam…")
    with c2:
        quick = st.selectbox("Snelle keuze", ["Huizen", "Bodegraven", "Den Haag", "Gouda", "Utrecht", "Amsterdam"], index=0)
    with c3:
        use_quick = st.button("Gebruik", use_container_width=True)

    if use_quick:
        q = quick

    st.session_state["wx_q"] = q
    results = []
    if q.strip():
        try:
            results = geocode(q.strip())
        except Exception:
            results = []

    if not results:
        st.warning("Geen resultaten. Probeer een andere schrijfwijze.")
        return None

    def label(r):
        parts = [r.get("name"), r.get("admin1"), r.get("country")]
        return " • ".join([p for p in parts if p])

    choice = st.selectbox("Resultaat", results, format_func=label)
    return choice


# ---------------------------
# Page
# ---------------------------
place = pick_place_ui()
if not place:
    st.stop()

lat = float(place["latitude"])
lon = float(place["longitude"])
place_name = f"{place.get('name','')} ({place.get('admin1','')})"

data = forecast(lat, lon)
current = data.get("current", {}) or {}
code = int(current.get("weather_code", 0) or 0)
temp = current.get("temperature_2m", None)
wind = current.get("wind_speed_10m", None)

# Tabs
t1, t2, t3 = st.tabs(["Radar", "Weerkaart", "Weerbericht"])

# --- Radar
with t1:
    st.markdown("<div class='kbm-card'>", unsafe_allow_html=True)

    # RainViewer radar (centered on chosen place)
    zoom = 8
    rv_url = f"https://www.rainviewer.com/map.html?loc={lat:.4f},{lon:.4f},{zoom}&layer=radar&sm=1&sn=1"

    # label overlay
    css = fx_css(code)
    st.markdown(f"""<style>{css}</style>""", unsafe_allow_html=True)

    label_html = f"""
<div class="kbm-sky" style="width:100%;height:560px;">
  <iframe src="{rv_url}" style="width:100%;height:100%;border:0;border-radius:18px;"></iframe>

  <div style="
    position:absolute; top:16px; left:16px;
    background:white;
    padding:10px 14px;
    border-radius:14px;
    box-shadow:0 10px 28px rgba(0,0,0,.28);
    font-size:14px;
    line-height:1.25;
    z-index:9999;
    min-width: 180px;
  ">
    <div style="font-weight:900; font-size:15px;">
      {wx_emoji(code)} {place_name}
    </div>
    <div style="opacity:.85; margin-top:2px;">
      {temp if temp is not None else "—"}°C • {wx_label(code)} • wind {wind if wind is not None else "—"} km/u
    </div>
  </div>

  <div class="kbm-sunbeam"></div>
  <div class="kbm-cloud"></div>
  <div class="kbm-cloud b"></div>
  <div class="kbm-rain"></div>
  <div class="kbm-snow"></div>
  <div class="kbm-flash"></div>
</div>
"""
    st.components.v1.html(label_html, height=580)

    st.markdown("</div>", unsafe_allow_html=True)

# --- Weerkaart
with t2:
    st.markdown("<div class='kbm-card'>", unsafe_allow_html=True)
    st.markdown("#### Weerkaart")

    kaart = st.selectbox(
        "Kies kaart",
        [
            "Neerslag (RainViewer)",
            "Temperatuur (Windy)",
            "Wind (Windy)",
            "Bewolking (Windy)",
        ],
        index=0,
    )

    if kaart == "Neerslag (RainViewer)":
        st.components.v1.iframe(
            f"https://www.rainviewer.com/map.html?loc={lat:.4f},{lon:.4f},7&layer=radar&sm=1&sn=1",
            height=560,
            scrolling=True,
        )
    elif kaart == "Temperatuur (Windy)":
        st.components.v1.iframe(
            f"https://embed.windy.com/embed2.html?lat={lat:.4f}&lon={lon:.4f}&detailLat={lat:.4f}&detailLon={lon:.4f}&width=650&height=560&zoom=6&level=surface&overlay=temp&product=ecmwf",
            height=560,
        )
    elif kaart == "Wind (Windy)":
        st.components.v1.iframe(
            f"https://embed.windy.com/embed2.html?lat={lat:.4f}&lon={lon:.4f}&detailLat={lat:.4f}&detailLon={lon:.4f}&width=650&height=560&zoom=6&level=surface&overlay=wind&product=ecmwf",
            height=560,
        )
    elif kaart == "Bewolking (Windy)":
        st.components.v1.iframe(
            f"https://embed.windy.com/embed2.html?lat={lat:.4f}&lon={lon:.4f}&detailLat={lat:.4f}&detailLon={lon:.4f}&width=650&height=560&zoom=6&level=surface&overlay=clouds&product=ecmwf",
            height=560,
        )

    st.markdown("</div>", unsafe_allow_html=True)

# --- Weerbericht
with t3:
    st.markdown("<div class='kbm-card'>", unsafe_allow_html=True)
    st.markdown("#### Verwachtingen")

    txt = knmi_text()
    if txt:
        st.markdown(txt)
    else:
        st.info("KNMI-tekst kon niet netjes worden opgehaald (site-layout veranderd).")

    st.markdown("</div>", unsafe_allow_html=True)

# Small 6h timeline
st.markdown("### Uren (komende 6)")
hourly = data.get("hourly", {}) or {}
times = hourly.get("time", []) or []
temps = hourly.get("temperature_2m", []) or []
codes = hourly.get("weather_code", []) or []
pp = hourly.get("precipitation_probability", []) or []

now_idx = 0
try:
    # pick closest upcoming hour
    now = datetime.now()
    for i, t in enumerate(times):
        dt = datetime.fromisoformat(t)
        if dt >= now:
            now_idx = i
            break
except Exception:
    now_idx = 0

rows = []
for i in range(now_idx, min(now_idx + 6, len(times))):
    try:
        dt = datetime.fromisoformat(times[i]).astimezone()
        hh = dt.strftime("%H:%M")
    except Exception:
        hh = str(times[i])[-5:]
    rows.append(
        {
            "Tijd": hh,
            "Weer": f"{wx_emoji(int(codes[i] or 0))} {wx_label(int(codes[i] or 0))}",
            "Temp": f"{temps[i] if i < len(temps) else '—'}°C",
            "Kans neerslag": f"{pp[i] if i < len(pp) else '—'}%",
        }
    )

st.dataframe(rows, use_container_width=True, hide_index=True)
