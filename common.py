import time
import hashlib
import re
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse, unquote
import feedparser
import requests
from bs4 import BeautifulSoup

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) KbMStreamlit/1.0"

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

    # RTL (Google News RSS wrappers per sectie)
    "rtl_algemeen": "https://news.google.com/rss/search?q=site:rtl.nl%20nieuws&hl=nl&gl=NL&ceid=NL:nl",
    "rtl_binnenland": "https://news.google.com/rss/search?q=site:rtl.nl%20Binnenland&hl=nl&gl=NL&ceid=NL:nl",
    "rtl_buitenland": "https://news.google.com/rss/search?q=site:rtl.nl%20Buitenland&hl=nl&gl=NL&ceid=NL:nl",
    "rtl_economie": "https://news.google.com/rss/search?q=site:rtl.nl%20Economie&hl=nl&gl=NL&ceid=NL:nl",
    "rtl_sport": "https://news.google.com/rss/search?q=site:rtl.nl%20Sport&hl=nl&gl=NL&ceid=NL:nl",
    "rtl_boulevard": "https://news.google.com/rss/search?q=site:rtl.nl%20Boulevard&hl=nl&gl=NL&ceid=NL:nl",
}

# ----------------------------
# CATEGORIES (homepage blocks + pages)
# ----------------------------
CATEGORY_FEEDS = {
    "Net binnen": ["nos_binnenland", "nu_algemeen", "rtvmh", "rtl_algemeen"],
    "Binnenland": ["nos_binnenland", "nu_algemeen", "ad_home", "rtl_binnenland"],
    "Buitenland": ["nos_buitenland", "nu_algemeen", "ad_home", "rtl_buitenland"],
    "Show": ["nu_entertainment", "nu_achterklap", "ad_sterren", "ad_showbytes", "rtl_boulevard"],
    "Lokaal": ["rtvmh"],
    "Sport": ["nos_sport", "nu_sport", "rtl_sport"],
    "Tech": ["nos_tech", "nu_tech"],
    "Opmerkelijk": ["nos_opmerkelijk", "nu_opmerkelijk", "nu_goed"],
    "Economie": ["nos_economie", "nu_economie", "ad_geld", "rtl_economie"],
}

# ----------------------------
# Helpers
# ----------------------------
def host(url: str) -> str:
    try:
        if not url:
            return ""
        u = url
        if "news.google.com" in u:
            u = resolve_google_news_url(u)
        return urlparse(u).netloc.replace("www.", "")
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

def resolve_google_news_url(gn_url: str) -> str:
    """Resolve Google News RSS 'articles/...' links to the original publisher URL (best-effort)."""
    try:
        if not gn_url or "news.google.com" not in gn_url:
            return gn_url

        m = re.search(r"[?&]url=([^&\"']+)", gn_url)
        if m:
            return unquote(m.group(1))

        headers = {"User-Agent": UA, "Accept-Language": "nl-NL,nl;q=0.9,en;q=0.8"}
        r = requests.get(gn_url, headers=headers, timeout=10)
        html = r.text or ""

        m = re.search(r'<link[^>]+rel="canonical"[^>]+href="([^"]+)"', html)
        if m and m.group(1):
            cand = m.group(1)
            m2 = re.search(r"[?&]url=([^&\"']+)", cand)
            if m2:
                return unquote(m2.group(1))

        m = re.search(r"[?&]url=([^&\"']+)", html)
        if m:
            return unquote(m.group(1))

        m = re.search(r'data-n-au="([^"]+)"', html)
        if m and m.group(1):
            return unquote(m.group(1))
    except Exception:
        pass
    return gn_url

def _first_image_from_entry(entry) -> str | None:
    # media:content, enclosure, image in summary
    try:
        if "media_content" in entry:
            mc = entry.get("media_content") or []
            if mc and isinstance(mc, list) and mc[0].get("url"):
                return mc[0]["url"]
        if "enclosures" in entry:
            enc = entry.get("enclosures") or []
            for e in enc:
                if (e.get("type","").startswith("image") or e.get("type","") == "") and e.get("href"):
                    return e["href"]
        # some feeds store as links
        links = entry.get("links") or []
        for l in links:
            if l.get("type","").startswith("image") and l.get("href"):
                return l["href"]
        # try in summary html
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
    if cached and now - cached["t"] < _CACHE_TTL:
        return cached["d"]
    d = feedparser.parse(url)
    _FEED_CACHE[url] = {"t": now, "d": d}
    return d

def collect_items(feed_labels, query=None, max_per_feed=25, **_):
    items = []
    for label in feed_labels:
        url = FEEDS.get(label)
        if not url:
            continue
        feed = _fetch_feed(url)
        for entry in feed.entries[:max_per_feed]:
            title = (entry.get("title") or "").strip()
            link = (entry.get("link") or "").strip()
            if not title or not link:
                continue
            dt = None
            if getattr(entry, "published_parsed", None):
                dt = datetime.fromtimestamp(time.mktime(entry.published_parsed), tz=timezone.utc)
            img = _first_image_from_entry(entry)
            # resolve google news wrapper early so article page can use it
            if "news.google.com" in link:
                link = resolve_google_news_url(link)
            items.append({
                "title": title,
                "link": link,
                "dt": dt,
                "rss_summary": (entry.get("summary") or "").strip(),
                "img": img,
                "source_label": label,
            })
    if query:
        q = query.lower()
        items = [x for x in items if q in (x["title"] + " " + (x.get("rss_summary") or "")).lower()]
    items.sort(key=lambda x: x["dt"] or datetime(1970,1,1,tzinfo=timezone.utc), reverse=True)
    return items, {}

# ----------------------------
# Article extraction (best-effort, no bypass)
# ----------------------------
def fetch_readable_text(url: str) -> tuple[str, str]:
    """Return (title, text). Best effort with requests+bs4.
    If site requires JS/consent, may return empty text.
    """
    try:
        headers = {"User-Agent": UA, "Accept-Language": "nl-NL,nl;q=0.9,en;q=0.8"}
        r = requests.get(url, headers=headers, timeout=12)
        html = r.text or ""
        soup = BeautifulSoup(html, "lxml")
        title = ""
        if soup.title and soup.title.string:
            title = soup.title.string.strip()
        # common article containers
        candidates = soup.select("article") or soup.select("main") or []
        text_parts = []
        for c in candidates[:2]:
            ps = c.select("p")
            for p in ps:
                t = p.get_text(" ", strip=True)
                if len(t) > 40:
                    text_parts.append(t)
        text = "\n\n".join(text_parts).strip()
        return title, text
    except Exception:
        return "", ""

def find_related_items(all_items: list[dict], title: str, max_n: int = 3) -> list[dict]:
    """Very simple related matcher: overlap of keywords."""
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
    out = []
    seen = set()
    for _, it in scored:
        if it.get("link") in seen:
            continue
        seen.add(it.get("link"))
        out.append(it)
        if len(out) >= max_n:
            break
    return out

# ----------------------------
# OpenAI (Responses API) — optional
# ----------------------------
def openai_summarize(model: str, api_key: str, prompt: str) -> str:
    """Call OpenAI Responses API. Requires OPENAI_API_KEY in Streamlit secrets."""
    if not api_key:
        return ""
    try:
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        payload = {"model": model, "input": prompt}
        resp = requests.post("https://api.openai.com/v1/responses", headers=headers, json=payload, timeout=30)
        if resp.status_code >= 300:
            return ""
        data = resp.json()
        # Responses API: output text is in output[0].content[0].text for many cases
        out = []
        for o in data.get("output", []):
            for c in o.get("content", []):
                if c.get("type") == "output_text" and c.get("text"):
                    out.append(c["text"])
        return "\n\n".join(out).strip()
    except Exception:
        return ""
