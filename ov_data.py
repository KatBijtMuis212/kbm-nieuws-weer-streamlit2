# -*- coding: utf-8 -*-
"""
KbM OV v2 — zoeken op HALTENAAM/PLAATS (+ optioneel LIVE locatie) zonder codes.

1) Vertrektijd.info (aanrader) — ondersteunt departures via /departures/_nametown/{town}/{stop}
   -> Vereist API key in Streamlit Secrets: VERTREKTIJD_API_KEY

2) OVAPI fallback — werkt zonder key, maar vereist TPC of StopAreaCode.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
import datetime as dt
import requests

UA = "KbMNieuwsOV/2.0 (+streamlit)"
HEADERS = {"User-Agent": UA, "Accept-Language": "nl-NL,nl;q=0.9,en;q=0.8"}

DEFAULT_TIMEOUT = 12

@dataclass
class Departure:
    line: str
    destination: str
    departure_time: dt.datetime
    delay_sec: int | None
    transport_type: str | None
    operator: str | None
    platform: str | None
    realtime: bool
    raw: dict

def _to_dt(ts: str) -> Optional[dt.datetime]:
    if not ts:
        return None
    try:
        return dt.datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except Exception:
        return None

# ---------- OVAPI (codes) ----------
def fetch_ovapi_departures(code: str, kind: str = "tpc", timeout: int = DEFAULT_TIMEOUT) -> List[Departure]:
    kind = kind.lower().strip()
    if kind not in ("stopareacode", "tpc"):
        raise ValueError("kind must be 'stopareacode' or 'tpc'")
    url = f"https://v0.ovapi.nl/{kind}/{code}/departures"
    r = requests.get(url, timeout=timeout, headers=HEADERS)
    r.raise_for_status()
    data = r.json()

    deps: List[Departure] = []

    def ingest_pass(p: dict):
        t = _to_dt(p.get("ExpectedDepartureTime") or p.get("TargetDepartureTime") or p.get("DepartureTime"))
        if not t:
            return
        line = str(p.get("LinePublicNumber") or p.get("LineNumber") or p.get("LinePlanningNumber") or "").strip()
        dest = str(p.get("DestinationName50") or p.get("DestinationName") or "").strip()
        delay = p.get("DelaySeconds")
        try:
            delay = int(delay) if delay is not None else None
        except Exception:
            delay = None
        deps.append(Departure(
            line=line or "—",
            destination=dest or "—",
            departure_time=t,
            delay_sec=delay,
            transport_type=p.get("TransportType"),
            operator=p.get("DataOwnerCode") or p.get("Operator"),
            platform=p.get("TargetPlatform") or p.get("ActualPlatform") or p.get("Platform") or None,
            realtime=bool(p.get("IsRealtime") or p.get("Realtime") or (delay is not None)),
            raw=p,
        ))

    def walk(node: Any):
        if isinstance(node, dict):
            if "Passes" in node and isinstance(node["Passes"], dict):
                for _k, p in node["Passes"].items():
                    if isinstance(p, dict):
                        ingest_pass(p)
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(data)
    deps.sort(key=lambda d: d.departure_time)
    return deps

# ---------- Vertrektijd.info (naam + plaats) ----------
def fetch_vertrektijd_departures(town: str, stop: str, api_key: str, timeout: int = DEFAULT_TIMEOUT) -> List[Departure]:
    """
    Uses: https://api.vertrektijd.info/departures/_nametown/{town}/{stop}/
    Auth header: X-Vertrektijd-Client-Api-Key
    """
    town = town.strip()
    stop = stop.strip()
    if not (town and stop):
        return []
    url = f"https://api.vertrektijd.info/departures/_nametown/{requests.utils.quote(town)}/{requests.utils.quote(stop)}/"
    headers = dict(HEADERS)
    headers["X-Vertrektijd-Client-Api-Key"] = api_key
    r = requests.get(url, headers=headers, timeout=timeout)
    r.raise_for_status()
    data = r.json()

    out: List[Departure] = []
    # shape: list of departures, each with time fields. We'll parse best-effort.
    for p in data if isinstance(data, list) else data.get("departures", []):
        t = _to_dt(p.get("departure") or p.get("expected_departure") or p.get("planned_departure"))
        if not t:
            continue
        delay_sec = None
        if p.get("delay"):
            try:
                # delay is often minutes; accept both
                delay_sec = int(p["delay"]) * 60
            except Exception:
                delay_sec = None
        out.append(Departure(
            line=str(p.get("line") or p.get("line_public_number") or "—"),
            destination=str(p.get("destination") or "—"),
            departure_time=t,
            delay_sec=delay_sec,
            transport_type=p.get("type"),
            operator=p.get("operator"),
            platform=p.get("platform") or p.get("track"),
            realtime=True if (p.get("expected_departure") or p.get("realtime")) else False,
            raw=p,
        ))
    out.sort(key=lambda d: d.departure_time)
    return out

def human_minutes(d: Departure, now: Optional[dt.datetime] = None) -> tuple[str,int]:
    now = now or dt.datetime.now(dt.timezone.utc)
    t = d.departure_time
    if t.tzinfo is None:
        t = t.replace(tzinfo=dt.timezone.utc)
    mins = int(round((t - now).total_seconds() / 60))
    return (t.astimezone().strftime("%H:%M"), mins)
