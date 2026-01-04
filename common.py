# common.py — KbM Streamlit (feeds expanded: Regionaal + Kranten + ICT)
from __future__ import annotations

import os
import hashlib
import re
import time
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple, Any
from urllib.parse import urlparse, urljoin, quote

import feedparser
import requests
import streamlit as st
from bs4 import BeautifulSoup


# ============================================================
# --- OV / Vertrektijd.info helpers ---
# ============================================================

VT_BASE = "https://api.vertrektijd.info"

def _vt_key() -> str:
    # werkt op Streamlit Cloud + lokaal
    k = None
    try:
        k = st.secrets.get("VERTREKTIJD_API_KEY")
    except Exception:
        k = None
    if not k:
        k = (os.environ.get("VERTREKTIJD_API_KEY") if "os" in globals() else None) or ""
    return k.strip()

def _vt_headers() -> dict:
    key = _vt_key()
    return {
        "X-Vertrektijd-Client-Api-Key": key,
        "Accept": "application/json",
        "User-Agent": "KbMNieuws/1.0 (Streamlit)"
    }

def vt_get(path: str, params: dict | None = None, timeout: int = 12) -> dict:
    url = f"{VT_BASE}{path}"
    r = requests.get(url, headers=_vt_headers(), params=params, timeout=timeout)
    r.raise_for_status()
    return r.json()

def vt_find_stops_by_name(stop_name: str) -> list[dict]:
    stop_name = stop_name.strip()
    if not stop_name:
        return []
    data = vt_get("/stop/_name/" + quote(stop_name) + "/")
    if isinstance(data, dict) and "obj" in data:
        return data["obj"] or []
    if isinstance(data, list):
        return data
    return []

def vt_find_stops_by_name_town(stop_name: str, town: str) -> list[dict]:
    stop_name = stop_name.strip()
    town = town.strip()
    if not stop_name or not town:
        return []
    data = vt_get("/stop/_nametown/" + quote(town) + "/" + quote(stop_name) + "/")
    if isinstance(data, dict) and "obj" in data:
        return data["obj"] or []
    if isinstance(data, list):
        return data
    return []

def vt_find_stops_by_geo(lat: float, lon: float, distance_km: float = 1.0) -> list[dict]:
    params = {"latitude": lat, "longitude": lon, "distance": distance_km}
    data = vt_get("/stop/_geo/", params=params)
    if isinstance(data, dict) and "obj" in data:
        return data["obj"] or []
    if isinstance(data, list):
        return data
    return []

def vt_departures_by_town_stop(town: str, stop: str) -> dict:
    town = town.strip()
    stop = stop.strip()
    if not town or not stop:
        return {}
    return vt_get("/departures/_nametown/" + quote(town) + "/" + quote(stop) + "/")
    
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36 KbMStreamlit/1.0"
HEADERS = {"User-Agent": UA, "Accept-Language": "nl-NL,nl;q=0.9,en;q=0.8"}

_FEED_CACHE: Dict[str, Dict[str, Any]] = {}
_CACHE_TTL = 180  # seconds

def clear_feed_caches() -> None:
    _FEED_CACHE.clear()

FEEDS: Dict[str, str] = {
    # NOS
    "nos_binnenland": "https://feeds.nos.nl/nosnieuwsbinnenland",
    "nos_buitenland": "https://feeds.nos.nl/nosnieuwsbuitenland",
    "nos_politiek": "https://feeds.nos.nl/nosnieuwspolitiek",
    "nos_economie": "https://feeds.nos.nl/nosnieuwseconomie",
    "nos_opmerkelijk": "https://feeds.nos.nl/nosnieuwsopmerkelijk",
    "nos_koningshuis": "https://feeds.nos.nl/nosnieuwskoningshuis",
    "nos_cultuur": "https://feeds.nos.nl/nosnieuwscultuurenmedia",
    "nos_tech": "https://feeds.nos.nl/nosnieuwstech",
    "nos_sport": "https://feeds.nos.nl/nossportalgemeen",
    "nos_f1": "https://feeds.nos.nl/nossportformule1",
    "nos_op3": "https://feeds.nos.nl/nosop3",

    # NU.nl
    "nu_home": "https://www.nu.nl/rss",
    "nu_algemeen": "https://www.nu.nl/rss/Algemeen",
    "nu_economie": "https://www.nu.nl/rss/Economie",
    "nu_sport": "https://www.nu.nl/rss/Sport",
    "nu_entertainment": "https://www.nu.nl/rss/entertainment",
    "nu_achterklap": "https://www.nu.nl/rss/Achterklap",
    "nu_opmerkelijk": "https://www.nu.nl/rss/Opmerkelijk",
    "nu_slimmer": "https://www.nu.nl/rss/slimmer-leven",
    "nu_tech": "https://www.nu.nl/rss/tech-wetenschap",
    "nu_goed": "https://www.nu.nl/rss/goed-nieuws",

    # AD algemeen + extra
    "ad_home": "https://www.ad.nl/home/rss.xml",
    "ad_geld": "https://www.ad.nl/geld/rss.xml",
    "ad_sterren": "https://www.ad.nl/sterren/rss.xml",
    "ad_film": "https://www.ad.nl/film/rss.xml",
    "ad_songfestival": "https://www.ad.nl/songfestival/rss.xml",
    "ad_muziek": "https://www.ad.nl/muziek/rss.xml",
    "ad_showbytes": "https://www.ad.nl/showbytes/rss.xml",
    "ad_royalty": "https://www.ad.nl/royalty/rss.xml",
    "ad_cultuur": "https://www.ad.nl/cultuur/rss.xml",
    "ad_series": "https://www.ad.nl/series/rss.xml",
    "ad_bizar": "https://www.ad.nl/bizar/rss.xml",
    "ad_show": "https://www.ad.nl/show/rss.xml",

    # AD Regio
    "ad_den_haag": "https://www.ad.nl/den-haag/rss.xml",
    "ad_rotterdam": "https://www.ad.nl/rotterdam/rss.xml",
    "ad_alphen": "https://www.ad.nl/alphen/rss.xml",
    "ad_groene_hart": "https://www.ad.nl/groene-hart/rss.xml",
    "ad_gouda": "https://www.ad.nl/gouda/rss.xml",
    "ad_woerden": "https://www.ad.nl/woerden/rss.xml",

    # RTV Midden Holland
    "rtvmh": "https://rtvmiddenholland.nl/feed/",

    # Omroep West
    "west_algemeen": "https://www.omroepwest.nl/rss/index.xml",
    "west_sport": "https://www.omroepwest.nl/rss/sport.xml",
    "west_economie": "https://www.omroepwest.nl/rss/economie.xml",
    "west_opsporing": "https://www.omroepwest.nl/rss/opsporing.xml",
    "west_bodegraven": "https://www.omroepwest.nl/rss/bodegraven-reeuwijk.xml",
    "west_gouda": "https://www.omroepwest.nl/rss/gouda.xml",
    "west_rijswijk": "https://www.omroepwest.nl/rss/rijswijk.xml",
    "west_alphen": "https://www.omroepwest.nl/rss/alphen-aan-den-rijn.xml",
    "west_delft": "https://www.omroepwest.nl/rss/delft.xml",
    "west_leiden": "https://www.omroepwest.nl/rss/leiden.xml",
    "west_westland": "https://www.omroepwest.nl/rss/westland.xml",
    "west_denhaag": "https://www.omroepwest.nl/rss/denhaag.xml",
    # vodcasts (best-effort)
    "west_vodcast_1": "https://omroepwest.bbvms.com/vodcast/1509025993954667",
    "west_vodcast_2": "https://omroepwest.bbvms.com/vodcast/1525261761416200",
    "west_vodcast_3": "https://omroepwest.bbvms.com/vodcast/1586159164787391",
    "west_vodcast_4": "https://omroepwest.bbvms.com/vodcast/1671303576617029",

    # NH Nieuws
    "nh_gooi": "https://rss.nhnieuws.nl/rss/nhgooi",

    # Volkskrant
    "vk_voorpagina": "https://www.volkskrant.nl/voorpagina/rss.xml",
    "vk_cultuur": "https://www.volkskrant.nl/cultuur-media/rss.xml",
    "vk_economie": "https://www.volkskrant.nl/economie/rss.xml",
    "vk_wetenschap": "https://www.volkskrant.nl/wetenschap/rss.xml",
    "vk_achtergrond": "https://www.volkskrant.nl/nieuws-achtergrond/rss.xml",

    # NRC
    "nrc_main": "https://www.nrc.nl/rss/",
    "nrc_feedburner": "http://feeds.feedburner.com/nrc/FmXV",
    "nrc_cultuur": "http://www.nrc.nl/nieuws/categorie/cultuur/rss.php",
    "nrc_economie": "http://www.nrc.nl/rss/economie",
    "nrc_sport": "http://www.nrc.nl/rss/sport",
    "nrc_wetenschap": "http://www.nrc.nl/nieuws/categorie/wetenschap/rss.php",

    # Trouw
    "trouw_voorpagina": "https://www.trouw.nl/voorpagina/rss.xml",
    "trouw_tijdgeest": "https://www.trouw.nl/tijdgeest/rss.xml",
    "trouw_columnisten": "https://www.trouw.nl/columnisten/rss.xml",
    "trouw_verdieping": "https://www.trouw.nl/verdieping/rss.xml",
    "trouw_duurzaamheid": "https://www.trouw.nl/duurzaamheid-economie/rss.xml",
    "trouw_opinie": "https://www.trouw.nl/opinie/rss.xml",
    "trouw_cultuur": "https://www.trouw.nl/cultuur-media/rss.xml",
    "trouw_politiek": "https://www.trouw.nl/politiek/rss.xml",
    "trouw_sport": "https://www.trouw.nl/sport/rss.xml",
    "trouw_wetenschap": "https://www.trouw.nl/wetenschap/rss.xml",
    "trouw_cartoons": "https://www.trouw.nl/cartoons/rss.xml",

    # Nederlands Dagblad
    "nd_nieuws": "http://www.nd.nl/rss/nieuws",
    "nd_binnenland": "http://www.nd.nl/rss/binnenland",
    "nd_buitenland": "http://www.nd.nl/rss/buitenland",
    "nd_economie": "http://www.nd.nl/rss/economie",
    "nd_cultuur": "http://www.nd.nl/rss/cultuur",

    # ICT/Tech
    "ict_pcmweb": "https://feeds.feedburner.com/pcmweb_nieuws",
    "ict_computable": "https://feeds.feedburner.com/ComputableRss",

    # RTL direct scrape markers
    "rtl_nieuws": "RTL_DIRECT_NEWS",
    "rtl_boulevard": "RTL_DIRECT_BOULEVARD",
    "rtl_binnenland": "RTL_DIRECT_BINNENLAND",
    "rtl_buitenland": "RTL_DIRECT_BUITENLAND",
    "rtl_economie": "RTL_DIRECT_ECONOMIE",
    "rtl_sport": "RTL_DIRECT_SPORT",
    "rtl_tech": "RTL_DIRECT_TECH",
    "rtl_royalty": "RTL_DIRECT_ROYALTY",
    "rtl_show": "RTL_DIRECT_SHOW",
}

CATEGORY_FEEDS: Dict[str, List[str]] = {
    "Net binnen": ["nos_binnenland", "nu_algemeen", "rtvmh", "west_algemeen", "nh_gooi", "rtl_nieuws"],

    "Binnenland": ["nos_binnenland","nos_politiek","nd_binnenland","rtl_binnenland"],
    "Buitenland": ["nos_buitenland","nd_buitenland","rtl_buitenland"],
    "Show": ["rtl_boulevard","rtl_show","nu_entertainment","ad_show","ad_sterren"],
    "Lokaal": ["rtvmh", "west_bodegraven", "west_gouda", "west_alphen"],
    "Sport": ["nos_sport", "nos_f1", "nu_sport", "west_sport", "nrc_sport", "trouw_sport", "rtl_nieuws"],
    "Tech": ["nos_tech","rtl_tech","ict_computable","ict_pcmweb"],
    "Opmerkelijk": ["nos_opmerkelijk", "nu_opmerkelijk", "nu_goed", "ad_bizar", "trouw_cartoons"],
    "Economie": ["nos_economie","nd_economie","rtl_economie"],

    "Regionaal": [
        "west_algemeen", "west_opsporing", "west_denhaag", "west_delft", "west_leiden", "west_westland",
        "west_rijswijk", "west_gouda", "west_alphen", "west_bodegraven",
        "nh_gooi",
        "ad_den_haag", "ad_rotterdam", "ad_alphen", "ad_groene_hart", "ad_gouda", "ad_woerden",
        "rtvmh",
        "west_vodcast_1", "west_vodcast_2", "west_vodcast_3", "west_vodcast_4",
    ],

    "Krant & Opinie": ["vk_voorpagina", "vk_achtergrond", "nrc_main", "trouw_opinie", "trouw_columnisten", "nd_nieuws"],
    "Cultuur & Media": ["nos_cultuur", "vk_cultuur", "nrc_cultuur", "trouw_cultuur", "nd_cultuur", "ad_cultuur", "ad_muziek", "ad_film", "ad_series"],
    "Wetenschap": ["vk_wetenschap", "nrc_wetenschap", "trouw_wetenschap", "nos_tech"],
    "Politiek": ["nos_politiek", "trouw_politiek", "vk_achtergrond", "nrc_main"],

    "RTL Nieuws": ["rtl_nieuws"],
    "RTL Binnenland": ["rtl_binnenland"],
    "RTL Boulevard": ["rtl_boulevard"],
}

def host(url: str) -> str:
    try:
        return urlparse(url).netloc.replace("www.", "")
    except Exception:
        return ""

def pretty_dt(dt: Optional[datetime]) -> str:
    if not dt:
        return ""
    return dt.astimezone().strftime("%d-%m %H:%M")

def within_hours(dt: Optional[datetime], hours: int) -> bool:
    if not dt:
        return False
    return dt >= datetime.now(timezone.utc) - timedelta(hours=hours)

def item_id(item: Dict[str, Any]) -> str:
    base = (item.get("link","") + item.get("title","")).encode("utf-8", "ignore")
    return hashlib.sha1(base).hexdigest()[:16]

def _first_image_from_entry(entry: Any) -> Optional[str]:
    try:
        mc = entry.get("media_content") or []
        if isinstance(mc, list) and mc and mc[0].get("url"):
            return mc[0]["url"]

        enc = entry.get("enclosures") or []
        for e in enc:
            href = e.get("href")
            if href and (e.get("type","").startswith("image") or e.get("type","")== ""):
                return href

        links = entry.get("links") or []
        for l in links:
            if (l.get("type","") or "").startswith("image") and l.get("href"):
                return l["href"]

        summ = entry.get("summary","") or ""
        m = re.search(r'<img[^>]+src="([^"]+)"', summ)
        if m:
            return m.group(1)
    except Exception:
        pass
    return None

def _fetch_feed(url: str):
    now = time.time()
    cached = _FEED_CACHE.get(url)
    if cached and (now - cached["t"] < _CACHE_TTL):
        return cached["d"]

    stale = cached["d"] if cached else None
    try:
        r = requests.get(url, headers=HEADERS, timeout=12)
        content = r.content if r.ok else b""
        d = feedparser.parse(content)
        _FEED_CACHE[url] = {"t": now, "d": d}
        return d
    except Exception:
        return stale if stale is not None else feedparser.parse(b"")

def _abs(href: str) -> str:
    if not href:
        return ""
    if href.startswith("//"):
        return "https:" + href
    return href

def _scrape_rtl_listing(list_url: str, max_items: int = 40) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    try:
        r = requests.get(list_url, headers=HEADERS, timeout=15)
        if not r.ok:
            return out
        soup = BeautifulSoup(r.text or "", "lxml")

        anchors = soup.find_all("a", href=True)
        seen = set()
        for a in anchors:
            href = _abs(a.get("href",""))
            if href.startswith("/"):
                href = urljoin("https://www.rtl.nl", href)

            if "rtl.nl" not in href:
                continue
            if "/nieuws/" not in href and "/boulevard/" not in href:
                continue
            if href in seen:
                continue
            seen.add(href)

            title = a.get_text(" ", strip=True) or ""
            title = re.sub(r"\s+", " ", title).strip()
            if len(title) < 12:
                continue

            # try to grab a thumbnail from the listing (img tag or inline background-image)
            img_url = None
            img_tag = a.find("img")
            if img_tag:
                img_url = img_tag.get("src") or img_tag.get("data-src") or img_tag.get("data-lazy-src")
            if not img_url:
                # sometimes the image is on a wrapping element as background-image
                cand = a
                for _ in range(3):
                    style = (cand.get("style") or "").strip()
                    m = re.search(r"background-image:\s*url\(['\"]?(.*?)['\"]?\)", style, flags=re.I)
                    if m:
                        img_url = m.group(1)
                        break
                    cand = cand.parent if getattr(cand, "parent", None) else cand
            if img_url and img_url.startswith("/"):
                img_url = urljoin("https://www.rtl.nl", img_url)

            out.append({
                "title": title,
                "link": href,
                "dt": None,
                "rss_summary": "",
                "img": img_url,
                "source_label": "rtl_direct",
            })
            if len(out) >= max_items:
                break
    except Exception:
        return out
    return out

def collect_items(feed_labels: List[str], query: Optional[str]=None, max_per_feed: int=25, **_ignored) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    for label in feed_labels:
        url = FEEDS.get(label)
        if not url:
            continue

        if url == "RTL_DIRECT_NEWS":
            items.extend(_scrape_rtl_listing("https://www.rtl.nl/nieuws", max_items=max_per_feed))
            continue
        if url == "RTL_DIRECT_BOULEVARD":
            items.extend(_scrape_rtl_listing("https://www.rtl.nl/boulevard", max_items=max_per_feed))
            continue

        if url == "RTL_DIRECT_BINNENLAND":
            items.extend(_scrape_rtl_listing("https://www.rtl.nl/nieuws/binnenland", max_items=max_per_feed))
            continue
        if url == "RTL_DIRECT_BUITENLAND":
            items.extend(_scrape_rtl_listing("https://www.rtl.nl/nieuws/buitenland", max_items=max_per_feed))
            continue
        if url == "RTL_DIRECT_ECONOMIE":
            items.extend(_scrape_rtl_listing("https://www.rtl.nl/nieuws/economie", max_items=max_per_feed))
            continue
        if url == "RTL_DIRECT_SPORT":
            items.extend(_scrape_rtl_listing("https://www.rtl.nl/sport", max_items=max_per_feed))
            continue
        if url == "RTL_DIRECT_TECH":
            items.extend(_scrape_rtl_listing("https://www.rtl.nl/nieuws/tech", max_items=max_per_feed))
            continue
        if url == "RTL_DIRECT_ROYALTY":
            items.extend(_scrape_rtl_listing("https://www.rtl.nl/nieuws/koningshuis", max_items=max_per_feed))
            continue
        if url == "RTL_DIRECT_SHOW":
            items.extend(_scrape_rtl_listing("https://www.rtl.nl/boulevard/entertainment", max_items=max_per_feed))
            continue

        feed = _fetch_feed(url)
        for entry in (feed.entries or [])[:max_per_feed]:
            title = (entry.get("title") or "").strip()
            link = (entry.get("link") or "").strip()
            if not title or not link:
                continue

            dt = None
            try:
                if getattr(entry, "published_parsed", None):
                    dt = datetime.fromtimestamp(time.mktime(entry.published_parsed), tz=timezone.utc)
            except Exception:
                dt = None

            items.append({
                "title": title,
                "link": link,
                "dt": dt,
                "rss_summary": (entry.get("summary") or "").strip(),
                "img": _first_image_from_entry(entry),
                "source_label": label,
            })

    if query:
        q = query.lower()
        items = [x for x in items if q in (x.get("title","") + " " + (x.get("rss_summary") or "")).lower()]

    items.sort(key=lambda x: x.get("dt") or datetime(1970,1,1,tzinfo=timezone.utc), reverse=True)
    return items, {}

def _clean_text(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "")).strip()

def fetch_readable_text(url: str) -> Tuple[str, str]:
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        if not r.ok:
            return "", ""
        soup = BeautifulSoup(r.text or "", "lxml")

        title = ""
        h1 = soup.select_one("h1")
        if h1:
            title = _clean_text(h1.get_text(" ", strip=True))
        if not title and soup.title and soup.title.string:
            title = _clean_text(soup.title.string)

        for tag in soup.select("script, style, noscript, iframe"):
            tag.decompose()

        containers = soup.select("article")
        if not containers:
            containers = soup.select(".entry-content, .post-content, .post__content, .content, .article__body, .article-content, main")
        if not containers and soup.body:
            containers = [soup.body]

        paras: List[str] = []
        for c in containers[:3]:
            for p in c.select("p, li"):
                t = _clean_text(p.get_text(" ", strip=True))
                if len(t) >= 40:
                    paras.append(t)

        out: List[str] = []
        seen = set()
        for t in paras:
            key = t[:140]
            if key in seen:
                continue
            seen.add(key)
            out.append(t)

        return title, "\n\n".join(out).strip()
    except Exception:
        return "", ""

def _meta(soup: BeautifulSoup, key: str) -> str:
    tag = soup.find("meta", attrs={"property": key}) or soup.find("meta", attrs={"name": key})
    if tag and tag.get("content"):
        return (tag.get("content") or "").strip()
    return ""

def fetch_article_media(url: str) -> Dict[str, str]:
    media = {"image":"", "video":"", "audio":"", "poster":"", "provider":host(url)}
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        if not r.ok:
            return media
        soup = BeautifulSoup(r.text or "", "lxml")
        media["image"] = _meta(soup, "og:image") or _meta(soup, "twitter:image")
        media["video"] = _meta(soup, "og:video") or _meta(soup, "og:video:url") or _meta(soup, "twitter:player")
        media["audio"] = _meta(soup, "og:audio") or _meta(soup, "og:audio:url")
    except Exception:
        return media
    return media

def find_related_items(all_items: List[Dict[str, Any]], title: str, max_n: int=3) -> List[Dict[str, Any]]:
    words = [w.lower() for w in re.findall(r"[A-Za-zÀ-ÿ0-9]{4,}", title or "")]
    if not words:
        return []
    keyset = set(words[:10])
    scored = []
    for it in all_items:
        t = (it.get("title") or "").lower()
        score = sum(1 for w in keyset if w in t)
        if score:
            scored.append((score, it))
    scored.sort(key=lambda x: x[0], reverse=True)
    out: List[Dict[str, Any]] = []
    seen = set()
    for _, it in scored:
        link = it.get("link")
        if not link or link in seen:
            continue
        seen.add(link)
        out.append(it)
        if len(out) >= max_n:
            break
    return out

find_related = find_related_items

def openai_summarize(model: str, api_key: str, prompt: str) -> str:
    if not api_key:
        return ""
    try:
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        payload = {"model": model, "input": prompt}
        resp = requests.post("https://api.openai.com/v1/responses", headers=headers, json=payload, timeout=45)
        if resp.status_code >= 300:
            return ""
        data = resp.json()
        out_parts: List[str] = []
        for o in data.get("output", []) or []:
            for c in o.get("content", []) or []:
                if c.get("type") == "output_text" and c.get("text"):
                    out_parts.append(c["text"])
        return "\n\n".join(out_parts).strip()
    except Exception:
        return ""


# --- Backwards compatibility helper (used by older UI code) ---

def pre(text: str) -> str:
    return text
