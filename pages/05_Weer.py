import streamlit as st
import requests, re
from common import BR6_BLUE
from style import inject_css

st.set_page_config(page_title="Weer • KbM Nieuws", page_icon="🌦️", layout="wide")
inject_css(st)

def require_login():
    pw = st.secrets.get("APP_PASSWORD", "").strip()
    if not pw:
        return
    if "kbm_ok" not in st.session_state:
        st.session_state.kbm_ok = False
    if st.session_state.kbm_ok:
        return
    st.markdown("### 🔒 Privé modus")
    inp = st.text_input("Wachtwoord", type="password")
    if st.button("Inloggen", use_container_width=True):
        st.session_state.kbm_ok = (inp == pw)
    if not st.session_state.kbm_ok:
        st.stop()

require_login()

OPEN_METEO_FORECAST = "https://api.open-meteo.com/v1/forecast"
OPEN_METEO_GEOCODE = "https://geocoding-api.open-meteo.com/v1/search"
UA = "KbMStreamlitWeather/2.0 (+Bas)"

DEFAULT_CITY = "Huizen"

@st.cache_data(ttl=300, show_spinner=False)
def geocode_city(name: str):
    params = {"name": name, "count": 5, "language": "nl", "format": "json"}
    r = requests.get(OPEN_METEO_GEOCODE, params=params, headers={"User-Agent": UA}, timeout=20)
    r.raise_for_status()
    return r.json()

@st.cache_data(ttl=300, show_spinner=False)
def forecast(lat: float, lon: float):
    params = {
        "latitude": lat,
        "longitude": lon,
        "current": "temperature_2m,apparent_temperature,precipitation,weather_code,wind_speed_10m",
        "hourly": "temperature_2m,precipitation,precipitation_probability,weather_code,wind_speed_10m",
        "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_sum",
        "timezone": "Europe/Amsterdam",
    }
    r = requests.get(OPEN_METEO_FORECAST, params=params, headers={"User-Agent": UA}, timeout=20)
    r.raise_for_status()
    return r.json()

def wx_type(code: int) -> str:
    c = int(code or 0)
    if c == 0: return "sun"
    if c in (1,2): return "partly"
    if c == 3: return "cloud"
    if c in (45,48): return "mist"
    if c in (71,73,75,77,85,86): return "snow"
    if c in (95,96,99): return "storm"
    if c in (51,53,55,56,57,61,63,65,66,67,80,81,82): return "rain"
    return "partly"

def wx_emoji(code: int) -> str:
    c = int(code or 0)
    if c == 0: return "☀️"
    if c in (1,2): return "⛅"
    if c == 3: return "☁️"
    if c in (45,48): return "🌫️"
    if c in (71,73,75,77,85,86): return "❄️"
    if c in (95,96,99): return "⛈️"
    if c in (51,53,55,56,57,61,63,65,66,67,80,81,82): return "🌧️"
    return "🌤️"

@st.cache_data(ttl=900, show_spinner=False)
def knmi_text():
    # Best effort scraping (layout kan wijzigen)
    try:
        url = "https://www.knmi.nl/nederland-nu/weer/verwachtingen"
        r = requests.get(url, headers={"User-Agent": UA}, timeout=20)
        if not r.ok:
            return None
        html = r.text
        html = re.sub(r"(?is)<(script|style).*?>.*?</\\1>", " ", html)
        txt = re.sub(r"(?is)<[^>]+>", " ", html)
        txt = re.sub(r"\\s+", " ", txt).strip()
        idx = txt.lower().find("verwachting")
        if idx != -1:
            return txt[idx:idx+1100]
        return txt[:1100]
    except Exception:
        return None

st.title("Weer")
st.caption("Radar via RainViewer • Verwachting via Open‑Meteo • Tekst (best effort) via KNMI.")

c1, c2, c3 = st.columns([1.2, 0.8, 1.0])
with c1:
    city = st.text_input("Zoek plaats", value=st.session_state.get("kbm_city", DEFAULT_CITY))
with c2:
    st.write("")
    go = st.button("Zoek", use_container_width=True)
with c3:
    st.write("")
    if st.button("Gebruik Huizen (snel)", use_container_width=True):
        city = DEFAULT_CITY
        go = True

if go or "kbm_city" not in st.session_state:
    st.session_state.kbm_city = city

g = geocode_city(st.session_state.kbm_city)
res = g.get("results") or []
if not res:
    st.warning("Plaats niet gevonden.")
    st.stop()

place = res[0]
lat, lon = float(place["latitude"]), float(place["longitude"])
place_name = f"{place.get('name','')} ({place.get('country_code','')})"

fx = forecast(lat, lon)
cur = fx.get("current", {})
temp = cur.get("temperature_2m")
app = cur.get("apparent_temperature")
code = cur.get("weather_code")
wind = cur.get("wind_speed_10m")
pr = cur.get("precipitation")
wtype = wx_type(code)

hero_html = f"""
<div style="border:1px solid rgba(0,0,0,.08); border-radius:18px; padding:16px; overflow:hidden; position:relative;
background: linear-gradient(180deg,
{'#d8f0ff' if wtype=='sun' else '#dbeafe' if wtype=='partly' else '#c7d2fe' if wtype=='cloud' else '#cbd5e1' if wtype=='mist' else '#c0eaff' if wtype=='rain' else '#e5e7eb' if wtype=='snow' else '#a5b4fc'},
#f4f7fb 70%);">
  <div style="position:relative; z-index:2;">
    <div style="font-weight:900; font-size:22px;">{wx_emoji(code)} {place_name}</div>
    <div style="color:#6b7280; margin-top:4px;">Nu: <b>{temp if temp is not None else '—'}°C</b> • gevoel {app if app is not None else '—'}°C • wind {wind if wind is not None else '—'} km/u • neerslag {pr if pr is not None else '—'} mm</div>
  </div>
  <canvas id="kbmParticles" style="position:absolute; inset:0; z-index:1;"></canvas>
</div>
<script>
(function(){{
  const c = document.getElementById('kbmParticles');
  const ctx = c.getContext('2d');
  function resize(){{ c.width = c.clientWidth*devicePixelRatio; c.height = c.clientHeight*devicePixelRatio; }}
  resize(); window.addEventListener('resize', resize);
  const type = "{wtype}";
  const n = (type==="snow") ? 90 : (type==="rain") ? 120 : (type==="mist") ? 45 : (type==="storm") ? 140 : (type==="sun") ? 22 : 35;
  const p=[]; for(let i=0;i<n;i++) p.push({{x:Math.random()*c.width,y:Math.random()*c.height,v:(type==="rain"||type==="storm")?(6+Math.random()*10):(1+Math.random()*3),s:(type==="snow")?(2+Math.random()*3):(1+Math.random()*2),a:0.25+Math.random()*0.55}});
  function step(){{
    ctx.clearRect(0,0,c.width,c.height);
    if(type==="sun"){{ for(const k of p){{ ctx.globalAlpha=k.a; ctx.beginPath(); ctx.arc(k.x,k.y,k.s,0,Math.PI*2); ctx.fillStyle="#fff"; ctx.fill(); k.y+=0.6; k.x+=Math.sin(k.y/60)*0.8; if(k.y>c.height+10){{k.y=-10;k.x=Math.random()*c.width;}} }} }}
    else if(type==="mist"||type==="cloud"||type==="partly"){{ for(const k of p){{ ctx.globalAlpha=k.a*0.55; ctx.fillStyle="#fff"; ctx.beginPath(); ctx.arc(k.x,k.y,k.s*6,0,Math.PI*2); ctx.fill(); k.x+=0.3+Math.random()*0.2; if(k.x>c.width+30){{k.x=-30;k.y=Math.random()*c.height;}} }} }}
    else if(type==="rain"||type==="storm"){{ ctx.strokeStyle="{BR6_BLUE}"; for(const k of p){{ ctx.globalAlpha=k.a; ctx.lineWidth=(type==="storm")?2:1.4; ctx.beginPath(); ctx.moveTo(k.x,k.y); ctx.lineTo(k.x+2,k.y+(12*k.s)); ctx.stroke(); k.y+=k.v*devicePixelRatio; k.x+=(type==="storm")?2.5:1.2; if(k.y>c.height+20){{k.y=-20;k.x=Math.random()*c.width;}} }} if(type==="storm"&&Math.random()<0.015){{ ctx.globalAlpha=0.35; ctx.fillStyle="#fff"; ctx.fillRect(0,0,c.width,c.height); }} }}
    else if(type==="snow"){{ for(const k of p){{ ctx.globalAlpha=k.a; ctx.fillStyle="#fff"; ctx.beginPath(); ctx.arc(k.x,k.y,k.s*devicePixelRatio,0,Math.PI*2); ctx.fill(); k.y+=k.v; k.x+=Math.sin(k.y/35)*1.2; if(k.y>c.height+10){{k.y=-10;k.x=Math.random()*c.width;}} }} }}
    requestAnimationFrame(step);
  }}
  step();
}})();
</script>
"""
st.components.v1.html(hero_html, height=150)

colL, colR = st.columns([1.45, 0.55], gap="large")
with colL:
    t1, t2, t3 = st.tabs(["Radar", "Weerkaart", "Weerbericht"])
    with t1:
        st.markdown("<div class='kbm-card'>", unsafe_allow_html=True)
        st.markdown(f"#### Buienradar (RainViewer) • {place_name}")
        rv_url = f"https://www.rainviewer.com/map.html?loc={lat:.4f},{lon:.4f},9&oFa=0&oC=0&oU=0&oCS=1&oF=0&oAP=0&c=3&o=83&lm=1&layer=radar&sm=1"
        st.components.v1.iframe(rv_url, height=560, scrolling=True)
        st.markdown("</div>", unsafe_allow_html=True)
    with t2:
        st.markdown("<div class='kbm-card'>", unsafe_allow_html=True)
        maps = {
            "Actueel weerbeeld": "https://cdn.knmi.nl/knmi/map/page/weer/waarschuwingen_verwachtingen/weerkaarten/actueel-weerbeeld.png",
            "Verwachting +1": "https://cdn.knmi.nl/knmi/map/page/weer/waarschuwingen_verwachtingen/weerkaarten/verwachting-1.png",
            "Verwachting +2": "https://cdn.knmi.nl/knmi/map/page/weer/waarschuwingen_verwachtingen/weerkaarten/verwachting-2.png",
        }
        pick = st.selectbox("Kaart", list(maps.keys()))
        st.image(maps[pick], use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)
    with t3:
        st.markdown("<div class='kbm-card'>", unsafe_allow_html=True)
        st.markdown("#### Tekstueel weerbericht (KNMI • best effort)")
        txt = knmi_text()
        st.write(txt if txt else "—")
        st.markdown("</div>", unsafe_allow_html=True)

with colR:
    st.markdown("<div class='kbm-card'>", unsafe_allow_html=True)
    st.markdown("#### Komende 6 uur")
    hourly = fx.get("hourly", {})
    times = hourly.get("time", [])[:6]
    prmm  = hourly.get("precipitation", [])[:6]
    prob  = hourly.get("precipitation_probability", [])[:6]
    t2m   = hourly.get("temperature_2m", [])[:6]
    rows=[]
    for i in range(min(6,len(times))):
        rows.append({"Uur": str(times[i])[11:16], "Temp (°C)": t2m[i] if i < len(t2m) else None, "Neerslag (mm)": prmm[i] if i < len(prmm) else None, "Kans (%)": prob[i] if i < len(prob) else None})
    st.dataframe(rows, use_container_width=True, hide_index=True)
    st.markdown("---")
    st.caption("Particles passen zich automatisch aan (zon/wolken/mist/regen/sneeuw/onweer).")
    st.markdown("</div>", unsafe_allow_html=True)

st.page_link("app.py", label="⬅️ Terug naar Home")
