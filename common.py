# common.py — KbM Streamlit (patched for OG/Twitter video+audio detection)
import time
import hashlib
import re
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

import feedparser
import requests
from bs4 import BeautifulSoup

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36 KbMStreamlit/1.0"
HEADERS = {"User-Agent": UA, "Accept-Language": "nl-NL,nl;q=0.9,en;q=0.8"}

# ----------------------------
# CACHE
# ----------------------------
_FEED_CACHE = {}
_CACHE_TTL = 180  # seconds

def clear_feed_caches():
    _FEED_CACHE.clear()

# ----------------------------
# FEEDS
# ----------------------------
FEEDS = {
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

    # AD
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

    # RTV Midden Holland
    "rtvmh": "https://rtvmiddenholland.nl/feed/",

    # RTL (DIRECT, not Google RSS) — handled specially
    "rtl_nieuws": "RTL_DIRECT_NEWS",
    "rtl_boulevard": "RTL_DIRECT_BOULEVARD",
}

CATEGORY_FEEDS = {
    "Net binnen": ["nos_binnenland", "nu_algemeen", "rtvmh", "rtl_nieuws"],
    "Binnenland": ["nos_binnenland", "nu_algemeen", "ad_home", "rtl_nieuws"],
    "Buitenland": ["nos_buitenland", "nu_algemeen", "ad_home", "rtl_nieuws"],
    "Show": ["nu_entertainment", "nu_achterklap", "ad_sterren", "ad_showbytes", "rtl_boulevard"],
    "Lokaal": ["rtvmh"],
    "Sport": ["nos_sport", "nu_sport", "rtl_nieuws"],
    "Tech": ["nos_tech", "nu_tech"],
    "Opmerkelijk": ["nos_opmerkelijk", "nu_opmerkelijk", "nu_goed"],
    "Economie": ["nos_economie", "nu_economie", "ad_geld", "rtl_nieuws"],
    "RTL Nieuws": ["rtl_nieuws"],
    "RTL Boulevard": ["rtl_boulevard"],
}

def host(url: str) -> str:
    try:
        if not url:
            return ""
        return urlparse(url).netloc.replace("www.", "")
    except Exception:
        return ""

def pretty_dt(dt: datetime | None) -> str:
    if not dt:
        return ""
    return dt.astimezone().strftime("%d-%m %H:%M")

def pretty(dt: datetime | None) -> str:
    return pretty_dt(dt)

def within_hours(dt: datetime | None, hours: int) -> bool:
    if not dt:
        return False
    return dt >= datetime.now(timezone.utc) - timedelta(hours=hours)

def item_id(item: dict) -> str:
    base = (item.get("link","") + item.get("title","")).encode("utf-8", "ignore")
    return hashlib.sha1(base).hexdigest()[:16]

def _first_image_from_entry(entry) -> str | None:
    try:
        mc = entry.get("media_content") or []
        if mc and isinstance(mc, list) and mc[0].get("url"):
            return mc[0]["url"]
        enc = entry.get("enclosures") or []
        for e in enc:
            if e.get("href") and (e.get("type","").startswith("image") or e.get("type","")== ""):
                return e["href"]
        links = entry.get("links") or []
        for l in links:
            if l.get("type","").startswith("image") and l.get("href"):
                return l["href"]
        summ = entry.get("summary","") or ""
        m = re.search(r'<img[^>]+src="([^"]+)"', summ)
        if m:
            return m.group(1)
    except Exception:
        pass
    return None

def _fetch_feed(url: str):
    # Always fetch via requests (headers+timeout), then feedparser.parse(bytes).
    now = time.time()
    cached = _FEED_CACHE.get(url)
    if cached and now - cached["t"] < _CACHE_TTL:
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

# ----------------------------
# RTL DIRECT SCRAPE (listing)
# ----------------------------
def _abs(url: str) -> str:
    if not url:
        return ""
    if url.startswith("//"):
        return "https:" + url
    return url

def _scrape_rtl_listing(list_url: str, max_items: int = 40) -> list[dict]:
    """Scrape RTL listing pages for article cards (best-effort)."""
    out = []
    try:
        r = requests.get(list_url, headers=HEADERS, timeout=15)
        if not r.ok:
            return out
        soup = BeautifulSoup(r.text or "", "lxml")

        link_candidates = []
        for sel in ["a[href*='/nieuws/']", "a[href*='/boulevard/']", "a[href^='/nieuws/']", "a[href^='/boulevard/']"]:
            link_candidates.extend(soup.select(sel))

        seen = set()
        for a in link_candidates:
            href = a.get("href") or ""
            href = _abs(href)
            if href.startswith("/"):
                href = "https://www.rtl.nl" + href
            if "rtl.nl" not in href:
                continue
            if href in seen:
                continue
            seen.add(href)

            title = a.get_text(" ", strip=True) or ""
            title = re.sub(r"\s+", " ", title).strip()
            if len(title) < 15:
                continue

            out.append({"title": title, "link": href, "dt": None, "rss_summary": "", "img": None, "source_label": "rtl_direct"})
            if len(out) >= max_items:
                break
    except Exception:
        return out
    return out

# ----------------------------
# MAIN COLLECTOR
# ----------------------------
def collect_items(feed_labels, query=None, max_per_feed=25, **_):
    items = []

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
        items = [x for x in items if q in (x["title"] + " " + (x.get("rss_summary") or "")).lower()]

    items.sort(key=lambda x: x.get("dt") or datetime(1970,1,1,tzinfo=timezone.utc), reverse=True)
    return items, {}

# -------- Article extraction --------
def _clean_text(s: str) -> str:
    s = re.sub(r"\s+", " ", s).strip()
    return s

def fetch_readable_text(url: str) -> tuple[str, str]:
    """Return (title, text). Best-effort for open sites incl. RTVMH and RTL."""
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        html = r.text or ""
        soup = BeautifulSoup(html, "lxml")

        title = ""
        h1 = soup.select_one("h1")
        if h1:
            title = _clean_text(h1.get_text(" ", strip=True))
        if not title and soup.title and soup.title.string:
            title = _clean_text(soup.title.string)

        for tag in soup.select("script, style, noscript, iframe"):
            tag.decompose()

        containers = []
        containers += soup.select("article")
        containers += soup.select(".entry-content, .post-content, .post__content, .content, .article__body, .article-content, main")
        if not containers:
            containers = [soup.body] if soup.body else []

        paras = []
        for c in containers[:3]:
            for p in c.select("p, li"):
                t = _clean_text(p.get_text(" ", strip=True))
                if len(t) >= 40:
                    paras.append(t)

        out = []
        seen = set()
        for t in paras:
            key = t[:120]
            if key in seen:
                continue
            seen.add(key)
            out.append(t)

        text = "\n\n".join(out).strip()
        return title, text
    except Exception:
        return "", ""

# -------- OG/Twitter media detection --------
def _meta(soup: BeautifulSoup, key: str) -> str:
    tag = soup.find("meta", attrs={"property": key}) or soup.find("meta", attrs={"name": key})
    if tag and tag.get("content"):
        return tag["content"].strip()
    return ""

def fetch_article_media(url: str) -> dict:
    """Return dict: image/video/audio urls (best-effort)."""
    media = {"image": "", "video": "", "audio": "", "poster": "", "provider": ""}
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        html = r.text or ""
        soup = BeautifulSoup(html, "lxml")

        img = _meta(soup, "og:image") or _meta(soup, "twitter:image")
        vid = _meta(soup, "og:video") or _meta(soup, "og:video:url") or _meta(soup, "twitter:player")
        aud = _meta(soup, "og:audio") or _meta(soup, "og:audio:url")

        if not vid:
            v = soup.find("video")
            if v:
                vid = v.get("src") or ""
                if not vid:
                    s = v.find("source")
                    if s and s.get("src"):
                        vid = s.get("src")

        if not aud:
            a = soup.find("audio")
            if a:
                aud = a.get("src") or ""
                if not aud:
                    s = a.find("source")
                    if s and s.get("src"):
                        aud = s.get("src")

        poster = ""
        v2 = soup.find("video")
        if v2 and v2.get("poster"):
            poster = v2.get("poster")

        media["image"] = img
        media["video"] = vid
        media["audio"] = aud
        media["poster"] = poster
        media["provider"] = host(url)
    except Exception:
        return media
    return media

# -------- Related finder --------
def find_related_items(all_items: list[dict], title: str, max_n: int = 3) -> list[dict]:
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
    out, seen = [], set()
    for _, it in scored:
        if it.get("link") in seen:
            continue
        seen.add(it.get("link"))
        out.append(it)
        if len(out) >= max_n:
            break
    return out

find_related = find_related_items  # backward compat

# -------- OpenAI (optional) --------
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
        out = []
        for o in data.get("output", []):
            for c in o.get("content", []):
                if c.get("type") == "output_text" and c.get("text"):
                    out.append(c["text"])
        return "\n\n".join(out).strip()
    except Exception:
        return ""
