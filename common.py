# common.py (RTL via Google News) — resolve original URL, try image + full-text extraction where possible
# Notes:
# - For Google News RSS items, entry.link often points to news.google.com. We resolve to the original publisher URL.
# - We then try to fetch the article HTML and extract readable text (best-effort). If blocked/JS/consent, we fall back to RSS snippet.
# - This does NOT bypass paywalls/consent walls; it only works when the content is accessible via a normal HTTP GET.

import re
import time
import hashlib
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse, urlunparse, urlencode, parse_qsl, quote_plus, unquote

import requests
import feedparser
from bs4 import BeautifulSoup

try:
    from dateutil import parser as dtparser
except Exception:
    dtparser = None

# ----------------------------
# Google News RSS helpers
# ----------------------------
def _gn(site_query: str, days: int = 30) -> str:
    q = f"site:rtl.nl {site_query} when:{days}d".strip()
    return "https://news.google.com/rss/search?q=" + quote_plus(q) + "&hl=nl&gl=NL&ceid=NL:nl"

# ----------------------------
# FEEDS / CATEGORIES
# ----------------------------
CATEGORY_FEEDS = {
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

    # RTL separate
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
_TIMEOUT = 14

_FEED_CACHE = {}
_FEED_CACHE_TTL = 90  # seconds

_ARTICLE_CACHE = {}
_ARTICLE_CACHE_TTL = 15 * 60  # seconds

def clear_feed_caches():
    _FEED_CACHE.clear()
    _ARTICLE_CACHE.clear()

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
# Google News: resolve original url
# ----------------------------
def resolve_google_news_url(url: str) -> str:
    """Turn a news.google.com RSS link into the original publisher URL (best-effort)."""
    if not url:
        return url
    try:
        u = urlparse(url)
        if "news.google.com" not in u.netloc:
            return _strip_tracking_params(url)
        # Some links have ?url=... embedded
        qs = dict(parse_qsl(u.query, keep_blank_values=True))
        if "url" in qs:
            return _strip_tracking_params(unquote(qs["url"]))
        # Otherwise fetch the redirect page and look for a real URL
        html = _fetch_html(url)
        # Try meta refresh or canonical
        soup = BeautifulSoup(html, "lxml")
        canon = soup.find("link", rel="canonical")
        if canon and canon.get("href") and "news.google.com" not in canon["href"]:
            return _strip_tracking_params(canon["href"])
        # Look for "url=" in the page HTML
        m = re.search(r"[?&]url=([^&"']+)", html)
        if m:
            return _strip_tracking_params(unquote(m.group(1)))
        # As last resort, return the final URL after requests redirects
        try:
            r = _SESSION.get(url, timeout=_TIMEOUT, allow_redirects=True)
            return _strip_tracking_params(r.url)
        except Exception:
            return url
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
    # media:content or media:thumbnail
    mc = entry.get("media_content") or entry.get("media_thumbnail")
    if isinstance(mc, list) and mc:
        url = mc[0].get("url")
        if url:
            return url
    # enclosure
    for l in entry.get("links", []) or []:
        if l.get("rel") == "enclosure" and (l.get("type") or "").startswith("image/"):
            return l.get("href")
    # summary <img>
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

def _fetch_html(url: str) -> str:
    r = _SESSION.get(url, timeout=_TIMEOUT, allow_redirects=True)
    r.raise_for_status()
    r.encoding = r.encoding or "utf-8"
    return r.text

def _looks_like_consent_or_js_gate(html: str) -> bool:
    h = (html or "").lower()
    # very generic signals
    return ("enable javascript" in h) or ("you need to enable javascript" in h) or ("consent" in h and "cookie" in h)

def _extract_text_from_html(html: str) -> tuple[str, str, str | None]:
    soup = BeautifulSoup(html, "lxml")

    # title
    title = ""
    ogt = soup.find("meta", property="og:title")
    if ogt and ogt.get("content"):
        title = _clean_text(ogt["content"])
    elif soup.title:
        title = _clean_text(soup.title.get_text(" ", strip=True))

    # image
    img = None
    ogi = soup.find("meta", property="og:image")
    if ogi and ogi.get("content"):
        img = ogi["content"]

    # pick main container
    container = soup.find("article") or soup.find("main") or soup.body

    for tag in container.find_all(["script", "style", "noscript", "svg", "form", "iframe"]):
        tag.decompose()

    paras = []
    for p in container.find_all(["p", "h2", "li"]):
        t = _clean_text(p.get_text(" ", strip=True))
        if t and len(t) >= 30:
            paras.append(t)
    text = "\n\n".join(paras).strip()
    text = re.sub(r"\n{3,}", "\n\n", text)
    return title, text, img

def fetch_article_text(url: str) -> dict:
    """Best-effort article fetch: returns {ok,title,text,img,error,fetched_url}."""
    if not url:
        return {"ok": False, "title": "", "text": "", "img": None, "error": "no_url", "fetched_url": ""}

    url = _strip_tracking_params(url)

    now = time.time()
    cached = _ARTICLE_CACHE.get(url)
    if cached and now - cached["t"] < _ARTICLE_CACHE_TTL:
        return cached["v"]

    # Try direct fetch
    try:
        html = _fetch_html(url)
        if _looks_like_consent_or_js_gate(html):
            res = {"ok": False, "title": "", "text": "", "img": None, "error": "consent_or_js", "fetched_url": url}
        else:
            title, text, img = _extract_text_from_html(html)
            ok = bool(text and len(text) >= 800)
            res = {"ok": ok, "title": title, "text": text, "img": img, "error": "" if ok else "no_text", "fetched_url": url}
    except Exception as e:
        res = {"ok": False, "title": "", "text": "", "img": None, "error": str(e), "fetched_url": url}

    _ARTICLE_CACHE[url] = {"t": now, "v": res}
    return res

def collect_items(
    feed_labels: list[str],
    query: str | None = None,
    max_per_feed: int = 25,
    force_fetch: bool = False,
    ai_on: bool = False,
):
    """Backwards-compatible signature; ai_on is handled downstream (Artikel-page)."""
    items: list[dict] = []
    for label in feed_labels:
        feed_url = FEEDS.get(label)
        if not feed_url:
            continue
        if force_fetch:
            _FEED_CACHE.pop(feed_url, None)
        d = fetch_feed(feed_url)

        for entry in (d.entries or [])[:max_per_feed]:
            raw_link = entry.get("link", "") or ""
            link = resolve_google_news_url(raw_link) if "news.google.com" in raw_link else _strip_tracking_params(raw_link)
            title = _clean_text(entry.get("title", "") or "")
            if not link or not title:
                continue

            dt = _parse_dt(entry)
            summary = entry.get("summary", "") or entry.get("description", "") or ""
            summary_txt = _clean_text(BeautifulSoup(summary, "lxml").get_text(" ", strip=True)) if summary else ""

            img = _extract_image_from_entry(entry)

            # If this is an RTL google-news item and RSS has no image, try og:image quickly (cached)
            if (not img) and label.startswith("rtl_"):
                art = fetch_article_text(link)
                if art.get("img"):
                    img = art["img"]

            items.append(
                {
                    "title": title,
                    "link": link,
                    "dt": dt,
                    "rss_summary": summary_txt,
                    "img": img,
                    "source": host(link),
                    "feed_label": label,
                    "raw_link": raw_link,
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
