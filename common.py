# common.py (RTL via Google News RSS patch)
# - Adds RTL.nl items via Google News RSS site:rtl.nl queries
# - Keeps your existing collect_items signature compatible (force_fetch/ai_on)
# - Merges RTL into existing categories + offers separate RTL pages (see pages/*.py)

import re
import time
import hashlib
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse, urlunparse, urlencode, parse_qsl, quote_plus

import requests
import feedparser
from bs4 import BeautifulSoup

try:
    from dateutil import parser as dtparser
except Exception:
    dtparser = None

# ----------------------------
# FEEDS / CATEGORIES
# ----------------------------
def _gn(site_query: str, days: int = 30) -> str:
    # Google News RSS search (NL)
    q = f"site:rtl.nl {site_query} when:{days}d".strip()
    return (
        "https://news.google.com/rss/search?q="
        + quote_plus(q)
        + "&hl=nl&gl=NL&ceid=NL:nl"
    )

CATEGORY_FEEDS = {
    # Existing main buckets (now also include RTL where it makes sense)
    "Net binnen": [
        "nos_binnenland", "nos_buitenland", "nu_algemeen", "ad_home", "rtv_mh",
        "rtl_algemeen",
    ],
    "Binnenland": [
        "nos_binnenland", "nu_algemeen", "ad_home", "rtv_mh",
        "rtl_binnenland",
    ],
    "Buitenland": [
        "nos_buitenland", "nu_algemeen", "ad_home",
        "rtl_buitenland",
    ],
    "Show": [
        "nos_op3", "nu_entertainment", "ad_show", "ad_sterren",
        "rtl_boulevard",
    ],
    "Lokaal": [
        "rtv_mh",
    ],
    "Sport": [
        "nos_sport", "nos_f1", "nu_sport",
        "rtl_sport",
    ],
    "Tech": [
        "nos_tech", "nu_tech",
        "rtl_algemeen",
    ],
    "Opmerkelijk": [
        "nos_opmerkelijk", "nu_opmerkelijk",
        "rtl_algemeen",
    ],

    # Separate RTL sections (for menu/pages)
    "RTL Nieuws": ["rtl_nieuws"],
    "RTL Boulevard": ["rtl_boulevard"],
    "RTL TV": ["rtl_tv"],
    "RTL Sport": ["rtl_sport"],
    "RTL Politiek": ["rtl_politiek"],
    "RTL Binnenland": ["rtl_binnenland"],
    "RTL Buitenland": ["rtl_buitenland"],
    "RTL Economie": ["rtl_economie"],
    "RTL Lifestyle": ["rtl_lifestyle"],
    "RTL Uitzendingen": ["rtl_uitzendingen"],
    "RTL Puzzels": ["rtl_puzzels"],
    "RTL Algemeen": ["rtl_algemeen"],
}

FEEDS = {
    # NOS
    "nos_binnenland": "https://feeds.nos.nl/nosnieuwsbinnenland",
    "nos_buitenland": "https://feeds.nos.nl/nosnieuwsbuitenland",
    "nos_opmerkelijk": "https://feeds.nos.nl/nosnieuwsopmerkelijk",
    "nos_tech": "https://feeds.nos.nl/nosnieuwstech",
    "nos_sport": "https://feeds.nos.nl/nossportalgemeen",
    "nos_f1": "https://feeds.nos.nl/nossportformule1",
    "nos_op3": "https://feeds.nos.nl/nosop3",

    # NU
    "nu_algemeen": "https://www.nu.nl/rss/Algemeen",
    "nu_sport": "https://www.nu.nl/rss/Sport",
    "nu_entertainment": "https://www.nu.nl/rss/entertainment",
    "nu_opmerkelijk": "https://www.nu.nl/rss/Opmerkelijk",
    "nu_tech": "https://www.nu.nl/rss/tech-wetenschap",

    # AD
    "ad_home": "https://www.ad.nl/home/rss.xml",
    "ad_show": "https://www.ad.nl/showbytes/rss.xml",
    "ad_sterren": "https://www.ad.nl/sterren/rss.xml",

    # RTV Midden Holland
    "rtv_mh": "https://rtvmiddenholland.nl/feed/",

    # RTL.nl via Google News RSS search
    "rtl_algemeen": _gn("", days=30),
    "rtl_nieuws": _gn("nieuws", days=30),
    "rtl_boulevard": _gn("boulevard", days=30),
    "rtl_tv": _gn("tv", days=30),
    "rtl_sport": _gn("sport", days=30),
    "rtl_politiek": _gn("politiek", days=30),
    "rtl_binnenland": _gn("binnenland", days=30),
    "rtl_buitenland": _gn("buitenland", days=30),
    "rtl_economie": _gn("economie OR geld OR beurs", days=30),
    "rtl_lifestyle": _gn("lifestyle OR gezondheid OR wonen OR eten", days=30),
    "rtl_uitzendingen": _gn("uitzendingen OR gemist OR kijken", days=30),
    "rtl_puzzels": _gn("puzzels OR quiz OR spel", days=30),
}

# ----------------------------
# HTTP
# ----------------------------
_SESSION = requests.Session()
_SESSION.headers.update(
    {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/122.0 Safari/537.36"
        ),
        "Accept-Language": "nl,en;q=0.8",
    }
)
_TIMEOUT = 12

_FEED_CACHE = {}
_FEED_CACHE_TTL = 90  # seconds


def clear_feed_caches():
    _FEED_CACHE.clear()


# ----------------------------
# UTIL
# ----------------------------
def host(url: str) -> str:
    try:
        return urlparse(url).netloc.replace("www.", "")
    except Exception:
        return ""


def _parse_dt(entry) -> datetime | None:
    for key in ("published_parsed", "updated_parsed"):
        val = getattr(entry, key, None)
        if val:
            try:
                return datetime.fromtimestamp(time.mktime(val), tz=timezone.utc)
            except Exception:
                pass
    for key in ("published", "updated"):
        s = getattr(entry, key, None)
        if s and dtparser:
            try:
                dt = dtparser.parse(s)
                if not dt.tzinfo:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt.astimezone(timezone.utc)
            except Exception:
                pass
    return None


def pretty_dt(dt: datetime | None) -> str:
    if not dt:
        return ""
    try:
        local = dt.astimezone()
        return local.strftime("%d-%m %H:%M")
    except Exception:
        return ""


def within_hours(dt: datetime | None, hours: int) -> bool:
    if not dt:
        return False
    now = datetime.now(timezone.utc)
    return dt >= now - timedelta(hours=hours)


def item_id(it: dict) -> str:
    base = (it.get("link") or "") + "|" + (it.get("title") or "")
    return hashlib.sha1(base.encode("utf-8", errors="ignore")).hexdigest()[:16]


def _clean_text(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip()


def _strip_tracking_params(url: str) -> str:
    try:
        u = urlparse(url)
        q = [
            (k, v)
            for (k, v) in parse_qsl(u.query, keep_blank_values=True)
            if not k.lower().startswith(("utm_", "fbclid", "gclid"))
        ]
        return urlunparse((u.scheme, u.netloc, u.path, u.params, urlencode(q), u.fragment))
    except Exception:
        return url


# ----------------------------
# RSS COLLECTION
# ----------------------------
def fetch_feed(feed_url: str):
    now = time.time()
    cached = _FEED_CACHE.get(feed_url)
    if cached and now - cached["t"] < _FEED_CACHE_TTL:
        return cached["d"]

    d = feedparser.parse(feed_url)
    _FEED_CACHE[feed_url] = {"t": now, "d": d}
    return d


def _extract_image_from_entry(entry) -> str | None:
    mc = entry.get("media_content") or entry.get("media_thumbnail")
    if isinstance(mc, list) and mc:
        url = mc[0].get("url")
        if url:
            return url

    for l in entry.get("links", []) or []:
        if l.get("rel") == "enclosure" and (l.get("type") or "").startswith("image/"):
            return l.get("href")

    html = entry.get("summary", "") or ""
    if "<img" in html:
        try:
            soup = BeautifulSoup(html, "lxml")
            img = soup.find("img")
            if img and img.get("src"):
                return img["src"]
        except Exception:
            pass
    return None


def collect_items(
    feed_labels: list[str],
    query: str | None = None,
    max_per_feed: int = 25,
    force_fetch: bool = False,
    ai_on: bool = False,
):
    # force_fetch/ai_on are present for compatibility with your UI
    items: list[dict] = []
    for label in feed_labels:
        feed_url = FEEDS.get(label)
        if not feed_url:
            continue
        if force_fetch:
            _FEED_CACHE.pop(feed_url, None)
        d = fetch_feed(feed_url)

        for entry in (d.entries or [])[:max_per_feed]:
            link = _strip_tracking_params(entry.get("link", "") or "")
            title = _clean_text(entry.get("title", "") or "")
            if not link or not title:
                continue

            dt = _parse_dt(entry)
            summary = entry.get("summary", "") or entry.get("description", "") or ""
            summary_txt = (
                _clean_text(BeautifulSoup(summary, "lxml").get_text(" ", strip=True)) if summary else ""
            )
            img = _extract_image_from_entry(entry)

            items.append(
                {
                    "title": title,
                    "link": link,
                    "dt": dt,
                    "rss_summary": summary_txt,
                    "img": img,
                    "source": host(link),
                    "feed_label": label,
                }
            )

    if query:
        q = query.lower()
        items = [
            x
            for x in items
            if q in (x.get("title", "").lower() + " " + (x.get("rss_summary", "").lower()))
        ]

    items.sort(key=lambda x: x.get("dt") or datetime(1970, 1, 1, tzinfo=timezone.utc), reverse=True)
    return items, {"count": len(items)}
