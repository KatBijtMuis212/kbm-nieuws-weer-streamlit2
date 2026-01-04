
import os
import requests
from urllib.parse import quote

API_BASE = "https://api.vertrektijd.info"
DEFAULT_VERSION = "1.5.0"

def _api_key() -> str | None:
    # Prefer Streamlit secrets, then env var
    try:
        import streamlit as st  # lazy import
        k = st.secrets.get("VERTREKTIJD_API_KEY", None)
        if k:
            return str(k).strip()
    except Exception:
        pass
    k = os.getenv("VERTREKTIJD_API_KEY")
    return k.strip() if k else None

def vt_headers(api_key: str | None = None, version: str = DEFAULT_VERSION) -> dict:
    api_key = api_key or _api_key()
    if not api_key:
        raise RuntimeError("Geen VERTREKTIJD_API_KEY gevonden. Zet 'VERTREKTIJD_API_KEY' in Streamlit secrets of env.")
    return {
        "X-Vertrektijd-Client-Api-Key": api_key,
        "Accept-Version": version,
        "User-Agent": "KbM-nieuws/1.0 (Streamlit)",
        "Accept": "application/json",
    }

def _get(url: str, params: dict | None = None, timeout: int = 12) -> dict:
    r = requests.get(url, headers=vt_headers(), params=params, timeout=timeout)
    r.raise_for_status()
    return r.json()

def search_stops(stop_query: str, town: str | None = None) -> list[dict]:
    """
    Search stops by name, optionally narrowing by town.

    Best-effort parsing:
    - If town provided => /stop/_nametown/{town}/{stop}/
    - Else => /stop/_name/{stop}
    """
    stop_query = (stop_query or "").strip()
    if not stop_query:
        return []
    if town:
        url = f"{API_BASE}/stop/_nametown/{quote(town)}/{quote(stop_query)}/"
        return _get(url) or []
    url = f"{API_BASE}/stop/_name/{quote(stop_query)}"
    return _get(url) or []

def search_stops_smart(user_input: str) -> list[dict]:
    """
    Single input field helper.
    Tries:
      1) If input contains ',' or '—' or '-' => interpret left as town, right as stop
      2) If input has >=2 words => try first token as town, rest as stop
      3) Fallback: /stop/_name/{full}
    """
    s = (user_input or "").strip()
    if not s:
        return []
    # separators
    for sep in [",", "—", "-", "–", "/"]:
        if sep in s:
            left, right = [x.strip() for x in s.split(sep, 1)]
            if left and right:
                res = search_stops(right, town=left)
                if res:
                    return res
    parts = s.split()
    if len(parts) >= 2:
        town = parts[0]
        stop = " ".join(parts[1:])
        try:
            res = search_stops(stop, town=town)
            if res:
                return res
        except Exception:
            pass
    return search_stops(s)

def nearby_stops(lat: float, lon: float, distance_m: int = 700) -> list[dict]:
    url = f"{API_BASE}/stop/_geo/{lat}/{lon}/{distance_m}/"
    return _get(url) or []

def departures_by_stopcode(stop_code: str) -> dict:
    """
    Returns dict with keys TRAIN and BTMF (arrays). Use BTMF for bus/tram/metro/ferry.
    """
    stop_code = str(stop_code).strip()
    if not stop_code:
        return {"TRAIN": [], "BTMF": []}
    url = f"{API_BASE}/departures/_stopcode/{quote(stop_code)}/"
    return _get(url) or {"TRAIN": [], "BTMF": []}
