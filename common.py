# common.py — STABIELE BASISVERSIE
# Compatibel met app.py + kbm_ui.py

import time
import hashlib
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse
import feedparser

# ----------------------------
# CACHE
# ----------------------------

_FEED_CACHE = {}
_CACHE_TTL = 120  # seconden

def clear_feed_caches():
    _FEED_CACHE.clear()

# ----------------------------
# CATEGORIEËN & FEEDS
# ----------------------------

CATEGORY_FEEDS = {
    "Net binnen": ["nos_binnenland", "nu_algemeen"],
    "Binnenland": ["nos_binnenland"],
    "Buitenland": ["nos_buitenland"],
    "Sport": ["nos_sport"],
    "Tech": ["nos_tech"],
    "Opmerkelijk": ["nos_opmerkelijk"],
}

FEEDS = {
    "nos_binnenland": "https://feeds.nos.nl/nosnieuwsbinnenland",
    "nos_buitenland": "https://feeds.nos.nl/nosnieuwsbuitenland",
    "nos_opmerkelijk": "https://feeds.nos.nl/nosnieuwsopmerkelijk",
    "nos_tech": "https://feeds.nos.nl/nosnieuwstech",
    "nos_sport": "https://feeds.nos.nl/nossportalgemeen",
    "nu_algemeen": "https://www.nu.nl/rss/Algemeen",
}

# ----------------------------
# HULPFUNCTIES
# ----------------------------

def host(url: str) -> str:
    try:
        return urlparse(url).netloc.replace("www.", "")
    except Exception:
        return ""

def pretty_dt(dt: datetime | None) -> str:
    if not dt:
        return ""
    return dt.astimezone().strftime("%d-%m %H:%M")

# alias voor kbm_ui
def pretty(dt: datetime | None) -> str:
    return pretty_dt(dt)

def within_hours(dt: datetime | None, hours: int) -> bool:
    if not dt:
        return False
    return dt >= datetime.now(timezone.utc) - timedelta(hours=hours)

def item_id(item: dict) -> str:
    base = (item.get("link","") + item.get("title","")).encode("utf-8", "ignore")
    return hashlib.sha1(base).hexdigest()[:16]

# ----------------------------
# RSS VERZAMELEN
# ----------------------------

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
            title = entry.get("title","").strip()
            link = entry.get("link","").strip()
            if not title or not link:
                continue

            dt = None
            if getattr(entry, "published_parsed", None):
                dt = datetime.fromtimestamp(
                    time.mktime(entry.published_parsed),
                    tz=timezone.utc
                )

            items.append({
                "title": title,
                "link": link,
                "dt": dt,
                "rss_summary": entry.get("summary",""),
                "img": None,
            })

    if query:
        q = query.lower()
        items = [x for x in items if q in (x["title"] + x["rss_summary"]).lower()]

    items.sort(
        key=lambda x: x["dt"] or datetime(1970,1,1,tzinfo=timezone.utc),
        reverse=True
    )

    return items, {}
