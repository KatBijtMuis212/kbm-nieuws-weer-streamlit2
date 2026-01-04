# -*- coding: utf-8 -*-
"""
KbM OV module (NL) — realtime vertrektijden + simpele reisplanner-link.

Provider fallback:
- OVAPI (KV78Turbo) via v0.ovapi.nl (geen API key nodig) voor bus/tram/metro/veer.
  Endpoints (JSON):
    https://v0.ovapi.nl/stopareacode/{CODE}/departures
    https://v0.ovapi.nl/tpc/{TPC}/departures

Optioneel (mooier zoeken op halte-naam + plaats):
- Vertrektijd.info Client API (API key nodig) — niet verplicht voor de basis.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
import requests
import datetime as dt

DEFAULT_TIMEOUT = 10

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
    """
    OVAPI uses ISO-like timestamps. Parse best-effort.
    """
    if not ts:
        return None
    try:
        # Example often: "2026-01-04T12:34:56+01:00"
        return dt.datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except Exception:
        return None

def fetch_ovapi_departures(code: str, kind: str = "stopareacode", timeout: int = DEFAULT_TIMEOUT) -> Tuple[List[Departure], dict]:
    """
    kind: 'stopareacode' or 'tpc'
    Returns (departures_sorted, raw_json)
    """
    kind = kind.lower().strip()
    if kind not in ("stopareacode", "tpc"):
        raise ValueError("kind must be 'stopareacode' or 'tpc'")
    url = f"https://v0.ovapi.nl/{kind}/{code}/departures"
    r = requests.get(url, timeout=timeout, headers={"User-Agent": "KbMNieuws/1.0 (+streamlit)"})
    r.raise_for_status()
    data = r.json()

    deps: List[Departure] = []

    # Response shape:
    # stopareacode: { "StopAreaCode": { "STOP": { "Passes": { ... }}}}
    # tpc:          { "TimingPointCode": { "Passes": { ... }}}
    # We'll normalize by walking all dicts and collecting entries with expected keys.
    def ingest_pass(p: dict):
        t = _to_dt(p.get("ExpectedDepartureTime") or p.get("TargetDepartureTime") or p.get("DepartureTime"))
        if not t:
            return
        line = str(p.get("LineNumber") or p.get("LinePlanningNumber") or p.get("LinePlanningNumber") or "").strip()
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
    return deps, data

def human_departure(d: Departure, now: Optional[dt.datetime] = None) -> str:
    now = now or dt.datetime.now(dt.timezone.utc)
    t = d.departure_time
    if t.tzinfo is None:
        t = t.replace(tzinfo=dt.timezone.utc)
    delta = (t - now).total_seconds()
    mins = int(round(delta / 60))
    hhmm = t.astimezone().strftime("%H:%M")
    if mins >= 0:
        return f"{hhmm} (over {mins} min)"
    return f"{hhmm} ({abs(mins)} min geleden)"

def build_9292_link(from_q: str, to_q: str) -> str:
    """
    Simpele planner-link (geen scraping): open 9292 met ingevulde velden.
    """
    import urllib.parse
    base = "https://9292.nl/reisadvies"
    qs = {
        "van": from_q,
        "naar": to_q,
    }
    return base + "?" + urllib.parse.urlencode(qs)
