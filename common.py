import re
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

import feedparser
import requests
from bs4 import BeautifulSoup

UA = "Mozilla/5.0 (KbMNieuwsStreamlit/2.2; +https://katbijtmuis.nl)"
TIMEOUT = 20

FEED_URLS = {
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

    "rtvmh": "https://rtvmiddenholland.nl/feed/",
}

CATEGORY_FEEDS = {
    "Net binnen": ["rtvmh","nos_binnenland","nos_buitenland","nos_politiek","nos_economie","nos_tech","nos_opmerkelijk",
                   "nu_home","nu_algemeen","nu_economie","nu_tech","nu_entertainment","nu_opmerkelijk",
                   "ad_home","ad_geld","ad_sterren","ad_showbytes"],
    "Binnenland": ["rtvmh","nos_binnenland","nos_politiek","nu_algemeen","ad_home"],
    "Buitenland": ["nos_buitenland","nu_home","ad_home"],
    "Show": ["nu_entertainment","nu_achterklap","ad_sterren","ad_showbytes","ad_royalty","nos_cultuur"],
    "Lokaal": ["rtvmh"],
    "Sport": ["nos_sport","nos_f1","nu_sport"],
    "Tech": ["nos_tech","nu_tech"],
    "Opmerkelijk": ["nos_opmerkelijk","nu_opmerkelijk"],
    "Weer": [],
}

def host(url: str) -> str:
    try:
        return urlparse(url).netloc.replace("www.", "")
    except Exception:
        return ""

def item_id(it: dict) -> str:
    link = (it.get("link") or "").strip()
    title = (it.get("title") or "").strip()
    base = (link or title).encode("utf-8", errors="ignore")
    import hashlib
    return hashlib.sha1(base).hexdigest()[:16]

def pretty_dt(dt) -> str:
    if not dt:
        return "—"
    try:
        return dt.astimezone().strftime("%d-%m %H:%M")
    except Exception:
        return "—"

def parse_dt(entry):
    t = getattr(entry, "published_parsed", None) or getattr(entry, "updated_parsed", None)
    if not t:
        return None
    try:
        return datetime.fromtimestamp(time.mktime(t), tz=timezone.utc)
    except Exception:
        return None

def within_hours(dt, hours: int) -> bool:
    if not dt:
        return False
    return dt >= (datetime.now(timezone.utc) - timedelta(hours=hours))

def _clean_ws(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "")).strip()

def fetch_html(url: str):
    try:
        r = requests.get(url, headers={"User-Agent": UA}, timeout=TIMEOUT)
        r.raise_for_status()
        return r.text
    except Exception:
        return None

def extract_main_text(html: str):
    soup = BeautifulSoup(html, "html.parser")
    for t in soup(["script","style","noscript","svg"]):
        t.decompose()

    title = _clean_ws(soup.title.string) if soup.title and soup.title.string else ""
    article = soup.find("article")
    node = article if article else soup.body

    paras = []
    if node:
        for p in node.find_all(["p","h2","h3"], limit=250):
            txt = _clean_ws(p.get_text(" ", strip=True))
            if not txt:
                continue
            low = txt.lower()
            bad = ["cookie", "privacy", "voorwaarden", "abonneer", "inloggen", "advertentie", "nieuwsbrief", "deel dit"]
            if any(b in low for b in bad):
                continue
            if len(txt) < 35 and not txt.endswith(":"):
                continue
            paras.append(txt)

    return title, "\n\n".join(paras).strip()

def journalistieke_samenvatting(text: str, max_bullets: int = 16) -> str:
    if not text:
        return ""
    sents = re.split(r"(?<=[\.!\?])\s+", _clean_ws(text))
    sents = [s.strip() for s in sents if len(s.strip()) >= 30]
    if not sents:
        return (_clean_ws(text)[:280] + "…") if len(text) > 280 else _clean_ws(text)

    lead = sents[0]
    keywords = ["volgens", "meldt", "zegt", "neemt", "krijgt", "besluit", "onderzoek", "politie", "minister", "brand", "ongeval", "rechtbank"]
    scored = []
    for s in sents[1:]:
        low = s.lower()
        score = min(len(s) / 160, 2.0)
        if any(k in low for k in keywords):
            score += 1.0
        if any(ch.isdigit() for ch in s):
            score += 0.5
        scored.append((score, s))
    scored.sort(key=lambda x: x[0], reverse=True)
    bullets = [b for _, b in scored[:max_bullets]]

    context = [b for b in bullets if 70 <= len(b) <= 220][:6]
    p1 = " ".join(context[:3]).strip()
    p2 = " ".join(context[3:6]).strip()

    out = [f"**Lead:** {lead}"]
    if p1:
        out += ["", "**Duiding:** " + p1]
    if p2:
        out += ["", "**Meer context:** " + p2]
    if bullets:
        out += ["", "**Kernpunten:**"]
        for b in bullets:
            bb = b[:260].rstrip() + ("…" if len(b) > 260 else "")
            out.append(f"- {bb}")
    return "\n".join(out).strip()

def enrich_item_with_summary(item: dict, force_fetch: bool = True) -> dict:
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
        item["summary"] = journalistieke_samenvatting(text, max_bullets=16)
        excerpt = _clean_ws(text)[:520]
        if len(_clean_ws(text)) > 520:
            excerpt += "…"
        item["excerpt"] = excerpt
    if not item.get("title") and t_title:
        item["title"] = t_title
    return item

def _pick_image(entry):
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
    try:
        summ = getattr(entry, "summary", "") or ""
        m = re.search(r'<img[^>]+src="([^"]+)"', summ)
        if m:
            return m.group(1)
    except Exception:
        pass
    return None

def collect_items(feed_labels, query: str | None = None, max_per_feed: int = 25, force_fetch: bool = True):
    items = []
    q = (query or "").strip().lower()
    for label in feed_labels:
        url = FEED_URLS.get(label)
        if not url:
            continue
        parsed = feedparser.parse(url)
        for e in parsed.entries[:max_per_feed]:
            title = _clean_ws(getattr(e, "title", ""))
            link = getattr(e, "link", "") or ""
            dt = parse_dt(e)
            img = _pick_image(e)

            if q:
                hay = (title + " " + _clean_ws(getattr(e, "summary", ""))).lower()
                if q not in hay:
                    continue

            it = {"title": title, "link": link, "dt": dt, "img": img, "source": host(link) or label, "summary": "", "excerpt": ""}
            it = enrich_item_with_summary(it, force_fetch=force_fetch)
            it["id"] = item_id(it)
            items.append(it)

    def sort_key(x):
        h = (x.get("source") or "").lower()
        is_local = 1 if "rtvmiddenholland" in h else 0
        dt = x.get("dt") or datetime(1970,1,1,tzinfo=timezone.utc)
        return (is_local, dt)

    items.sort(key=sort_key, reverse=True)
    return items, {}

def load_article(url: str, force_fetch: bool = True) -> dict:
    it = {"title": "", "link": url, "dt": None, "img": None, "source": host(url), "summary": "", "excerpt": "", "id": ""}
    it = enrich_item_with_summary(it, force_fetch=force_fetch)
    it["id"] = item_id(it)
    return it
