import re
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

import feedparser
import requests
from bs4 import BeautifulSoup

UA = "Mozilla/5.0 (KbMNieuwsStreamlit/2.1; +https://katbijtmuis.nl)"
TIMEOUT = 20

# ---------------------------
# Feeds per categorie (labels -> feed urls)
# Je bestaande structuur blijft werken: CATEGORY_FEEDS is mapping categorie -> list of labels
# en FEED_URLS is mapping label -> url
# ---------------------------

FEED_URLS = {
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
    "nu_slimmerleven": "https://www.nu.nl/rss/slimmer-leven",
    "nu_tech": "https://www.nu.nl/rss/tech-wetenschap",
    "nu_goednieuws": "https://www.nu.nl/rss/goed-nieuws",

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
}

CATEGORY_FEEDS = {
    "Net binnen": [
        "nos_binnenland","nos_buitenland","nos_politiek","nos_economie","nos_tech","nos_opmerkelijk",
        "nu_home","nu_algemeen","nu_economie","nu_tech","nu_entertainment","nu_opmerkelijk",
        "ad_home","ad_geld","ad_sterren","ad_showbytes",
        "rtvmh"
    ],
    "Binnenland": ["nos_binnenland","nos_politiek","nu_algemeen","ad_home","rtvmh"],
    "Buitenland": ["nos_buitenland","nu_home","ad_home"],
    "Show": ["nu_entertainment","nu_achterklap","ad_sterren","ad_showbytes","ad_royalty","nos_cultuur"],
    "Lokaal": ["rtvmh"],
    "Sport": ["nos_sport","nos_f1","nu_sport"],
    "Tech": ["nos_tech","nu_tech"],
    "Opmerkelijk": ["nos_opmerkelijk","nu_opmerkelijk"],
    "Weer": [],
}

# ---------------------------
# Utilities
# ---------------------------

def host(url: str) -> str:
    try:
        h = urlparse(url).netloc.replace("www.", "")
        return h
    except Exception:
        return ""

def parse_dt(entry) -> datetime | None:
    # feedparser provides published_parsed / updated_parsed
    t = getattr(entry, "published_parsed", None) or getattr(entry, "updated_parsed", None)
    if not t:
        return None
    try:
        return datetime.fromtimestamp(time.mktime(t), tz=timezone.utc)
    except Exception:
        return None

def within_hours(dt: datetime | None, hours: int) -> bool:
    if not dt:
        return False
    now = datetime.now(timezone.utc)
    return dt >= (now - timedelta(hours=hours))

def _clean_ws(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "")).strip()

# ---------------------------
# Article text extraction (best-effort)
# NOTE: We do NOT show full copyrighted articles. We extract for summary + short excerpt.
# ---------------------------

def fetch_html(url: str) -> str | None:
    try:
        r = requests.get(url, headers={"User-Agent": UA}, timeout=TIMEOUT)
        r.raise_for_status()
        return r.text
    except Exception:
        return None

def extract_main_text(html: str) -> tuple[str, str]:
    """Return (title, text) best-effort from html."""
    soup = BeautifulSoup(html, "html.parser")
    for t in soup(["script","style","noscript","svg"]):
        t.decompose()

    title = ""
    if soup.title and soup.title.string:
        title = _clean_ws(soup.title.string)

    # Prefer <article>
    article = soup.find("article")
    node = article if article else soup.body

    # Collect paragraphs
    paras = []
    if node:
        for p in node.find_all(["p","h2","h3"], limit=200):
            txt = _clean_ws(p.get_text(" ", strip=True))
            if not txt:
                continue
            # Skip boilerplate
            low = txt.lower()
            bad = ["cookie", "privacy", "voorwaarden", "abonneer", "inloggen", "advertentie", "deel dit", "nieuwsbrief"]
            if any(b in low for b in bad):
                continue
            if len(txt) < 40 and not txt.endswith(":"):
                continue
            paras.append(txt)

    text = "\n\n".join(paras)
    text = text.strip()
    return title, text

def naive_summary(text: str, max_sentences: int = 3) -> str:
    """Simple extractive-ish summary: pick first well-formed sentences."""
    if not text:
        return ""
    # sentence split (rough)
    sents = re.split(r"(?<=[\.!\?])\s+", _clean_ws(text))
    good = []
    for s in sents:
        s = s.strip()
        if 40 <= len(s) <= 240:
            good.append(s)
        if len(good) >= max_sentences:
            break
    if not good:
        # fallback to first 220 chars
        return (_clean_ws(text)[:220] + "…") if len(text) > 220 else _clean_ws(text)
    return " ".join(good)

def enrich_item_with_summary(item: dict, force_fetch: bool = True) -> dict:
    """Fetch article, generate our own summary + short excerpt. Safe for Streamlit display."""
    if not force_fetch:
        return item

    url = item.get("link") or ""
    if not url:
        return item

    html = fetch_html(url)
    if not html:
        return item

    t_title, text = extract_main_text(html)
    if text:
        # summary + excerpt
        item["summary"] = naive_summary(text, max_sentences=3)
        # short excerpt only (avoid full article reproduction)
        excerpt = _clean_ws(text)[:450]
        if len(_clean_ws(text)) > 450:
            excerpt += "…"
        item["excerpt"] = excerpt
    # prefer feed title; keep html title as fallback
    if not item.get("title") and t_title:
        item["title"] = t_title
    return item

# ---------------------------
# RSS aggregation
# ---------------------------

def _pick_image(entry) -> str | None:
    # Try media:content / enclosure / summary img
    try:
        if "media_content" in entry and entry.media_content:
            for m in entry.media_content:
                u = m.get("url")
                if u:
                    return u
    except Exception:
        pass
    try:
        for l in getattr(entry, "links", []) or []:
            if l.get("rel") == "enclosure" and (l.get("type","").startswith("image/")):
                return l.get("href")
    except Exception:
        pass
    # try summary html img
    try:
        summ = getattr(entry, "summary", "") or ""
        m = re.search(r'<img[^>]+src="([^"]+)"', summ)
        if m:
            return m.group(1)
    except Exception:
        pass
    return None

def collect_items(feed_labels: list[str], query: str | None = None, max_per_feed: int = 25, force_fetch: bool = True):
    items = []
    counts = {}

    q = (query or "").strip().lower()

    for label in feed_labels:
        url = FEED_URLS.get(label)
        if not url:
            continue

        parsed = feedparser.parse(url)
        entries = parsed.entries[:max_per_feed]
        counts[label] = len(entries)

        for e in entries:
            title = _clean_ws(getattr(e, "title", ""))
            link = getattr(e, "link", "") or ""
            dt = parse_dt(e)
            img = _pick_image(e)

            if q:
                hay = (title + " " + _clean_ws(getattr(e, "summary", ""))).lower()
                if q not in hay:
                    continue

            it = {
                "title": title,
                "link": link,
                "dt": dt,
                "img": img,
                "source": host(link) or label,
                "summary": "",   # filled by enrich
                "excerpt": "",   # short excerpt only
            }

            it = enrich_item_with_summary(it, force_fetch=force_fetch)
            items.append(it)

    # sort newest first
    items.sort(key=lambda x: x["dt"] or datetime(1970,1,1,tzinfo=timezone.utc), reverse=True)
    return items, counts
