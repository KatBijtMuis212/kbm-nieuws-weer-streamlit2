from __future__ import annotations

import os
import datetime as dt
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote

import requests

API_BASE = "https://api.vertrektijd.info"
UA = "KbMNieuwsOV/3.0 (Streamlit)"


def _api_key() -> str:
    # Streamlit secrets -> env var
    try:
        import streamlit as st  # lazy
        k = st.secrets.get("VERTREKTIJD_API_KEY", "") or ""
    except Exception:
        k = ""
    if not k:
        k = os.environ.get("VERTREKTIJD_API_KEY", "") or ""
    return k.strip()


def _headers() -> Dict[str, str]:
    k = _api_key()
    h = {"Accept": "application/json", "User-Agent": UA}
    if k:
        h["X-Vertrektijd-Client-Api-Key"] = k
    return h


def _get(url: str, timeout: int = 15) -> Any:
    r = requests.get(url, headers=_headers(), timeout=timeout)
    r.raise_for_status()
    if not r.text:
        return None
    return r.json()


# ---------- Stops ----------
def search_stops_name(stop_query: str) -> List[dict]:
    stop_query = (stop_query or "").strip()
    if not stop_query:
        return []
    url = f"{API_BASE}/stop/_name/{quote(stop_query)}"
    data = _get(url)
    return data if isinstance(data, list) else []


def search_stops_nametown(town: str, stop_query: str) -> List[dict]:
    town = (town or "").strip()
    stop_query = (stop_query or "").strip()
    if not town or not stop_query:
        return []
    url = f"{API_BASE}/stop/_nametown/{quote(town)}/{quote(stop_query)}/"
    data = _get(url)
    return data if isinstance(data, list) else []


def search_stops_smart(user_input: str) -> List[dict]:
    """
    Accepts: "Town / Stop"  or "Stop"  or "Town Stop"
    Returns list of dicts (best-effort).
    """
    s = (user_input or "").strip()
    if not s:
        return []

    # 1) explicit "town / stop"
    if "/" in s:
        a, b = [x.strip() for x in s.split("/", 1)]
        if a and b:
            res = search_stops_nametown(a, b)
            if res:
                return res

    # 2) plain name
    res = search_stops_name(s)
    if res:
        return res

    # 3) if "Utrecht Centraal" -> try town=first token
    parts = s.split()
    if len(parts) >= 2:
        town_guess = parts[0]
        stop_guess = " ".join(parts[1:])
        res = search_stops_nametown(town_guess, stop_guess)
        if res:
            return res

    return []


def nearby_stops(lat: float, lon: float, distance_m: int = 700) -> List[dict]:
    url = f"{API_BASE}/stop/_geo/{lat}/{lon}/{int(distance_m)}/"
    data = _get(url)
    return data if isinstance(data, list) else []


# ---------- Departures ----------
def departures_by_stopcode(stop_code: str) -> dict:
    stop_code = (stop_code or "").strip()
    if not stop_code:
        return {"TRAIN": [], "BTMF": []}
    url = f"{API_BASE}/departures/_stopcode/{quote(stop_code)}/"
    data = _get(url)
    return data if isinstance(data, dict) else {"TRAIN": [], "BTMF": []}


def departures_by_nametown(town: str, stop: str) -> Any:
    town = (town or "").strip()
    stop = (stop or "").strip()
    if not town or not stop:
        return []
    url = f"{API_BASE}/departures/_nametown/{quote(town)}/{quote(stop)}/"
    return _get(url)


# ---------- Normalization ----------
@dataclass
class Departure:
    departure_time: dt.datetime
    line: str
    destination: str
    mode: str  # BUS/TRAM/METRO/TREIN/...
    platform: str = ""
    delay_min: int = 0
    status: str = ""


def _to_dt(s: str) -> Optional[dt.datetime]:
    if not s:
        return None
    try:
        x = s.replace("Z", "+00:00")
        d = dt.datetime.fromisoformat(x)
        if d.tzinfo is None:
            d = d.replace(tzinfo=dt.timezone.utc)
        return d.astimezone(dt.timezone.utc)
    except Exception:
        return None


def _mins_until(t: dt.datetime, now: Optional[dt.datetime] = None) -> int:
    now = now or dt.datetime.now(dt.timezone.utc)
    return int(round((t - now).total_seconds() / 60))


def normalize_departures(dep_json: Any) -> List[Departure]:
    """
    Accepts Vertrektijd dict format (TRAIN/BTMF blocks) OR list format (nametown endpoint)
    Returns sorted list of Departure.
    """
    deps: List[Departure] = []

    def add_from_record(d: dict, fallback_mode: str = ""):
        exp = d.get("ExpectedDeparture") or d.get("expectedDeparture") or d.get("departure") or ""
        plan = d.get("PlannedDeparture") or d.get("plannedDeparture") or ""
        exp_dt = _to_dt(exp) or _to_dt(plan)
        if not exp_dt:
            return

        line = str(d.get("LineNumber") or d.get("LineName") or d.get("line") or "—")
        dest = str(d.get("Destination") or d.get("destination") or "—")
        mode = str(d.get("TransportType") or d.get("Mode") or d.get("type") or fallback_mode or "—").upper()

        # delay: Expected vs Planned
        delay = 0
        pdt = _to_dt(plan)
        if pdt and exp_dt:
            delay = max(0, int(round((exp_dt - pdt).total_seconds() / 60)))

        plat = str(d.get("Platform") or d.get("platform") or "")
        status = str(d.get("VehicleStatus") or d.get("status") or "")

        deps.append(
            Departure(
                departure_time=exp_dt,
                line=line,
                destination=dest,
                mode=mode,
                platform=plat,
                delay_min=delay,
                status=status,
            )
        )

    def walk(node: Any):
        if isinstance(node, dict):
            # if it's a departure record, try parse
            if any(k in node for k in ("ExpectedDeparture", "PlannedDeparture", "Destination", "LineNumber")):
                add_from_record(node)
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    # dict format
    if isinstance(dep_json, dict) and ("TRAIN" in dep_json or "BTMF" in dep_json):
        for blk in dep_json.get("TRAIN") or []:
            for d in (blk.get("Departures") or []):
                add_from_record(d, "TREIN")
        for blk in dep_json.get("BTMF") or []:
            for d in (blk.get("Departures") or []):
                add_from_record(d, "BTMF")
        deps.sort(key=lambda x: x.departure_time)
        return deps

    # list format (nametown)
    walk(dep_json)
    deps.sort(key=lambda x: x.departure_time)
    return deps


def group_by_mode(deps: List[Departure]) -> Dict[str, List[Departure]]:
    out: Dict[str, List[Departure]] = {}
    for d in deps:
        mode = d.mode
        # normalize common labels
        if "TRAIN" in mode or "TREIN" in mode:
            mode = "TREIN"
        elif "METRO" in mode:
            mode = "METRO"
        elif "TRAM" in mode:
            mode = "TRAM"
        elif "BUS" in mode:
            mode = "BUS"
        out.setdefault(mode, []).append(d)
    return out
