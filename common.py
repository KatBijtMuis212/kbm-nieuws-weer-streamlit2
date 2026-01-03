# common.py — shared utilities for KbM Streamlit app
import re, time
from datetime import datetime, timezone, timedelta
from urllib.parse import urlparse

import requests
import feedparser

try:
    from bs4 import BeautifulSoup
except Exception:
    BeautifulSoup = None

UA = "KbMStreamlitNews/2.0 (+Bas)"
BR6_BLUE = "#214c6e"

FEEDS = {
    "NOS • Binnenland": "https://feeds.nos.nl/nosnieuwsbinnenland",
    "NOS • Buitenland": "https://feeds.nos.nl/nosnieuwsbuitenland",
    "NOS • Politiek": "https://feeds.nos.nl/nosnieuwspolitiek",
    "NOS • Economie": "https://feeds.nos.nl/nosnieuwseconomie",
    "NOS • Opmerkelijk": "https://feeds.nos.nl/nosnieuwsopmerkelijk",
    "NOS • Koningshuis": "https://feeds.nos.nl/nosnieuwskoningshuis",
    "NOS • Cultuur & Media": "https://feeds.nos.nl/nosnieuwscultuurenmedia",
    "NOS • Tech": "https://feeds.nos.nl/nosnieuwstech",
    "NOS • Sport": "https://feeds.nos.nl/nossportalgemeen",
    "NOS • Formule 1": "https://feeds.nos.nl/nossportformule1",
    "NOS • OP3": "https://feeds.nos.nl/nosop3",

    "NU.nl • Home": "https://www.nu.nl/rss",
    "NU.nl • Algemeen": "https://www.nu.nl/rss/Algemeen",
    "NU.nl • Economie": "https://www.nu.nl/rss/Economie",
    "NU.nl • Sport": "https://www.nu.nl/rss/Sport",
    "NU.nl • Entertainment": "https://www.nu.nl/rss/entertainment",
    "NU.nl • Achterklap": "https://www.nu.nl/rss/Achterklap",
    "NU.nl • Opmerkelijk": "https://www.nu.nl/rss/Opmerkelijk",
    "NU.nl • Slimmer Leven": "https://www.nu.nl/rss/slimmer-leven",
    "NU.nl • Tech/Wetenschap": "https://www.nu.nl/rss/tech-wetenschap",
    "NU.nl • Goed Nieuws": "https://www.nu.nl/rss/goed-nieuws",

    "AD • Home": "https://www.ad.nl/home/rss.xml",
    "AD • Geld": "https://www.ad.nl/geld/rss.xml",
    "AD • Sterren": "https://www.ad.nl/sterren/rss.xml",
    "AD • Film": "https://www.ad.nl/film/rss.xml",
    "AD • Songfestival": "https://www.ad.nl/songfestival/rss.xml",
    "AD • Muziek": "https://www.ad.nl/muziek/rss.xml",
    "AD • Showbytes": "https://www.ad.nl/showbytes/rss.xml",
    "AD • Royalty": "https://www.ad.nl/royalty/rss.xml",
    "AD • Cultuur": "https://www.ad.nl/cultuur/rss.xml",
    "AD • Series": "https://www.ad.nl/series/rss.xml",

    "RTV Midden Holland": "https://rtvmiddenholland.nl/feed/",
}

CATEGORY_FEEDS = {
    "Net binnen": list(FEEDS.keys()),
    "Binnenland": [
        "NOS • Binnenland", "NOS • Politiek", "NOS • Economie", "NOS • Koningshuis",
        "NU.nl • Algemeen", "NU.nl • Home",
        "AD • Home", "AD • Geld",
    ],
    "Buitenland": ["NOS • Buitenland", "NU.nl • Home", "AD • Home"],
    "Show": [
        "NU.nl • Entertainment", "NU.nl • Achterklap",
        "AD • Sterren", "AD • Film", "AD • Showbytes", "AD • Royalty",
        "AD • Muziek", "AD • Songfestival", "AD • Cultuur", "AD • Series",
        "NOS • Cultuur & Media", "NOS • OP3",
    ],
    "Sport": ["NOS • Sport", "NOS • Formule 1", "NU.nl • Sport"],
    "Tech": ["NOS • Tech", "NU.nl • Tech/Wetenschap", "NU.nl • Slimmer Leven"],
    "Opmerkelijk": ["NOS • Opmerkelijk", "NU.nl • Opmerkelijk", "NU.nl • Goed Nieuws"],
    "Lokaal": ["RTV Midden Holland"],
}

def safe_text(x: str) -> str:
    return re.sub(r"\s+", " ", (x or "")).strip()

def host(u: str) -> str:
    try:
        return urlparse(u).netloc.replace("www.", "")
    except Exception:
        return ""

def entry_dt(entry) -> datetime | None:
    for key in ("published_parsed", "updated_parsed"):
        v = getattr(entry, key, None)
        if v:
            try:
                return datetime.fromtimestamp(time.mktime(v), tz=timezone.utc)
            except Exception:
                pass
    return None

def strip_html(html: str) -> str:
    if not html:
        return ""
    if BeautifulSoup:
        try:
            return BeautifulSoup(html, "html.parser").get_text(" ", strip=True)
        except Exception:
            pass
    return re.sub(r"<[^>]+>", " ", html)

def image_from_entry(entry) -> str | None:
    if "media_content" in entry and entry.media_content:
        u = entry.media_content[0].get("url")
        if u: return u
    if "media_thumbnail" in entry and entry.media_thumbnail:
        u = entry.media_thumbnail[0].get("url")
        if u: return u
    if "enclosures" in entry and entry.enclosures:
        for e in entry.enclosures:
            if e.get("type","").startswith("image") and e.get("href"):
                return e["href"]
    summ = entry.get("summary","") or entry.get("description","")
    if summ and BeautifulSoup:
        try:
            soup = BeautifulSoup(summ, "html.parser")
            img = soup.find("img")
            if img and img.get("src"):
                return img["src"]
        except Exception:
            pass
    return None

def fetch_url(url: str, timeout=20) -> str:
    r = requests.get(url, headers={"User-Agent": UA}, timeout=timeout)
    r.raise_for_status()
    return r.text

def parse_feed(url: str):
    return feedparser.parse(fetch_url(url))

def og_image(url: str) -> str | None:
    if not BeautifulSoup:
        return None
    try:
        html = fetch_url(url, timeout=20)
        soup = BeautifulSoup(html, "html.parser")
        m = soup.find("meta", property="og:image")
        if m and m.get("content"):
            return m["content"]
    except Exception:
        return None
    return None

def readable_text(url: str) -> str | None:
    if not BeautifulSoup:
        return None
    try:
        html = fetch_url(url, timeout=20)
        soup = BeautifulSoup(html, "html.parser")
        for t in soup(["script","style","noscript"]):
            t.decompose()
        ps = [p.get_text(" ", strip=True) for p in soup.find_all("p")]
        ps = [safe_text(p) for p in ps if safe_text(p)]
        txt = "\n".join(ps[:40])
        return txt if len(txt) > 400 else None
    except Exception:
        return None

def quick_summary(entry, force_fetch: bool) -> str:
    s = safe_text(strip_html(entry.get("summary","") or entry.get("description","")))
    if len(s) >= 140:
        return s[:420].rstrip() + ("…" if len(s) > 420 else "")
    if force_fetch:
        txt = readable_text(entry.get("link",""))
        if txt:
            parts = re.split(r"(?<=[.!?])\s+", safe_text(txt))
            parts = [p.strip() for p in parts if p.strip()]
            out = " ".join(parts[:3])
            return out[:520].rstrip() + ("…" if len(out) > 520 else "")
    return s

def collect_items(feed_labels: list[str], query: str | None, max_per_feed: int, force_fetch: bool):
    items = []
    stats = []
    for label in feed_labels:
        url = FEEDS.get(label)
        if not url:
            continue
        try:
            d = parse_feed(url)
            entries = d.entries or []
            kept = 0
            for e in entries[:max_per_feed]:
                title = safe_text(e.get("title",""))
                link = e.get("link","")
                if not title or not link:
                    continue
                if query:
                    q = query.lower()
                    hay = (title + " " + safe_text(strip_html(e.get("summary","") or e.get("description","")))).lower()
                    if q not in hay:
                        continue
                img = image_from_entry(e) or og_image(link)
                dt = entry_dt(e)
                summ = quick_summary(e, force_fetch=force_fetch)
                items.append({"source": label, "title": title, "link": link, "img": img, "dt": dt, "summary": summ})
                kept += 1
            stats.append((label, len(entries), kept))
        except Exception:
            stats.append((label, 0, 0))
    items.sort(key=lambda x: x["dt"] or datetime(1970,1,1,tzinfo=timezone.utc), reverse=True)
    return items, stats

def within_hours(dt: datetime | None, hours: int) -> bool:
    if not dt:
        return False
    now = datetime.now(timezone.utc)
    return dt >= (now - timedelta(hours=hours))
