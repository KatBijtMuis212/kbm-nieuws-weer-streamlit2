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
# Google News RSS helpers (RTL)
# ----------------------------
def gn(site_query: str, days: int = 45) -> str:
    q = f"site:rtl.nl {site_query} when:{days}d".strip()
    return "https://news.google.com/rss/search?q=" + quote_plus(q) + "&hl=nl&gl=NL&ceid=NL:nl"

# ----------------------------
# FEEDS / CATEGORIES
# ----------------------------
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

    # RTL.nl via Google News RSS
    "rtl_algemeen": gn("", days=45),
    "rtl_nieuws": gn("nieuws", days=45),
    "rtl_boulevard": gn("boulevard", days=45),
    "rtl_tv": gn("tv", days=45),
    "rtl_sport": gn("sport", days=45),
    "rtl_politiek": gn("politiek", days=45),
    "rtl_binnenland": gn("binnenland", days=45),
    "rtl_buitenland": gn("buitenland", days=45),
    "rtl_economie": gn("economie OR geld OR beurs", days=45),
    "rtl_lifestyle": gn("lifestyle OR gezondheid OR wonen OR eten", days=45),
    "rtl_uitzendingen": gn("uitzendingen OR gemist OR kijken", days=45),
    "rtl_puzzels": gn("puzzels OR quiz OR spel", days=45),
}

CATEGORY_FEEDS = {
    "Net binnen": ["nos_binnenland","nos_buitenland","nu_algemeen","ad_home","rtv_mh","rtl_algemeen"],
    "Binnenland": ["nos_binnenland","nu_algemeen","ad_home","rtv_mh","rtl_binnenland"],
    "Buitenland": ["nos_buitenland","nu_algemeen","ad_home","rtl_buitenland"],
    "Show": ["nos_op3","nu_entertainment","ad_show","ad_sterren","rtl_boulevard"],
    "Lokaal": ["rtv_mh"],
    "Sport": ["nos_sport","nos_f1","nu_sport","rtl_sport"],
    "Tech": ["nos_tech","nu_tech","rtl_algemeen"],
    "Opmerkelijk": ["nos_opmerkelijk","nu_opmerkelijk","rtl_algemeen"],

    # RTL apart
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

# ----------------------------
# HTTP + CACHES
# ----------------------------
_SESSION = requests.Session()
_SESSION.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0 Safari/537.36",
    "Accept-Language": "nl,en;q=0.8",
})
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
        u = url
        if "news.google.com" in u:
            u = resolve_google_news_url(u)
        return urlparse(u).netloc.replace("www.", "")
    except Exception:
        return ""

def _clean_text(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip()

def _strip_tracking_params(url: str) -> str:
    try:
        u = urlparse(url)
        q = [(k, v) for (k, v) in parse_qsl(u.query, keep_blank_values=True)
             if not k.lower().startswith(("utm_","fbclid","gclid"))]
        return urlunparse((u.scheme, u.netloc, u.path, u.params, urlencode(q), u.fragment))
    except Exception:
        return url

def _parse_dt(entry) -> datetime | None:
    for key in ("published_parsed","updated_parsed"):
        val = getattr(entry, key, None)
        if val:
            try:
                return datetime.fromtimestamp(time.mktime(val), tz=timezone.utc)
            except Exception:
                pass
    for key in ("published","updated"):
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
        return dt.astimezone().strftime("%d-%m %H:%M")
    except Exception:
        return ""

def within_hours(dt: datetime | None, hours: int) -> bool:
    if not dt:
        return False
    return dt >= (datetime.now(timezone.utc) - timedelta(hours=hours))

def item_id(it: dict) -> str:
    base = (it.get("link") or "") + "|" + (it.get("title") or "")
    return hashlib.sha1(base.encode("utf-8", errors="ignore")).hexdigest()[:16]

# ----------------------------
# Google News URL resolve
# ----------------------------
def resolve_google_news_url(url: str) -> str:
    if not url:
        return url
    try:
        u = urlparse(url)
        if "news.google.com" not in u.netloc:
            return _strip_tracking_params(url)
        qs = dict(parse_qsl(u.query, keep_blank_values=True))
        if "url" in qs:
            return _strip_tracking_params(unquote(qs["url"]))
        html = _fetch_html(url)
        m = re.search(r"[?&]url=([^&"']+)", html)
        if m:
            return _strip_tracking_params(unquote(m.group(1)))
        # last resort: follow redirects
        r = _SESSION.get(url, timeout=_TIMEOUT, allow_redirects=True)
        return _strip_tracking_params(r.url)
    except Exception:
        return url

# ----------------------------
# RSS fetch
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
        u = mc[0].get("url")
        if u:
            return u
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

def collect_items(feed_labels: list[str], query: str | None = None, max_per_feed: int = 25,
                  force_fetch: bool = False, ai_on: bool = False):
    # ai_on kept for compatibility; AI happens in article page
    items = []
    for label in feed_labels:
        feed_url = FEEDS.get(label)
        if not feed_url:
            continue
        if force_fetch:
            _FEED_CACHE.pop(feed_url, None)
        d = fetch_feed(feed_url)
        for entry in (d.entries or [])[:max_per_feed]:
            raw_link = entry.get("link","") or ""
            link = resolve_google_news_url(raw_link) if "news.google.com" in raw_link else _strip_tracking_params(raw_link)
            title = _clean_text(entry.get("title","") or "")
            if not link or not title:
                continue
            dt = _parse_dt(entry)
            summary = entry.get("summary","") or entry.get("description","") or ""
            summary_txt = _clean_text(BeautifulSoup(summary, "lxml").get_text(" ", strip=True)) if summary else ""
            img = _extract_image_from_entry(entry)
            items.append({
                "title": title,
                "link": link,
                "raw_link": raw_link,
                "dt": dt,
                "rss_summary": summary_txt,
                "img": img,
                "source": host(link),
                "feed_label": label,
            })
    if query:
        q = query.lower()
        items = [x for x in items if q in ((x.get("title","")+ " " + x.get("rss_summary","")).lower())]
    items.sort(key=lambda x: x.get("dt") or datetime(1970,1,1,tzinfo=timezone.utc), reverse=True)
    return items, {"count": len(items)}

# ----------------------------
# Article fetch (best-effort, no bypass)
# ----------------------------
def _fetch_html(url: str) -> str:
    r = _SESSION.get(url, timeout=_TIMEOUT, allow_redirects=True)
    r.raise_for_status()
    r.encoding = r.encoding or "utf-8"
    return r.text

def _looks_like_gate(html: str) -> bool:
    h = (html or "").lower()
    return ("enable javascript" in h) or ("you need to enable javascript" in h) or ("privacy gate" in h) or ("cookie" in h and "consent" in h)

def _extract_text_from_html(html: str) -> tuple[str, str, str | None]:
    soup = BeautifulSoup(html, "lxml")

    title = ""
    ogt = soup.find("meta", property="og:title")
    if ogt and ogt.get("content"):
        title = _clean_text(ogt["content"])
    elif soup.title:
        title = _clean_text(soup.title.get_text(" ", strip=True))

    img = None
    ogi = soup.find("meta", property="og:image")
    if ogi and ogi.get("content"):
        img = ogi["content"]

    container = soup.find("article") or soup.find("main") or soup.body
    if not container:
        return title, "", img

    for tag in container.find_all(["script","style","noscript","svg","form","iframe"]):
        tag.decompose()

    paras = []
    for p in container.find_all(["p","h2","li"]):
        t = _clean_text(p.get_text(" ", strip=True))
        if t and len(t) >= 30:
            paras.append(t)
    text = "\n\n".join(paras).strip()
    text = re.sub(r"\n{3,}", "\n\n", text)
    return title, text, img

def fetch_article_text(url: str) -> dict:
    if not url:
        return {"ok": False, "title":"", "text":"", "img":None, "error":"no_url"}

    url = _strip_tracking_params(url)
    now = time.time()
    cached = _ARTICLE_CACHE.get(url)
    if cached and now - cached["t"] < _ARTICLE_CACHE_TTL:
        return cached["v"]

    try:
        html = _fetch_html(url)
        if _looks_like_gate(html):
            res = {"ok": False, "title":"", "text":"", "img":None, "error":"gate"}
        else:
            title, text, img = _extract_text_from_html(html)
            ok = bool(text and len(text) >= 800)
            res = {"ok": ok, "title": title, "text": text, "img": img, "error": "" if ok else "no_text"}
    except Exception as e:
        res = {"ok": False, "title":"", "text":"", "img":None, "error": str(e)}

    _ARTICLE_CACHE[url] = {"t": now, "v": res}
    return res

# ----------------------------
# AI (OpenAI Responses API)
# ----------------------------
def _openai_client():
    try:
        from openai import OpenAI
    except Exception:
        return None
    try:
        import streamlit as st
        api_key = (st.secrets.get("OPENAI_API_KEY") or "").strip()
        if not api_key:
            return None
        return OpenAI(api_key=api_key)
    except Exception:
        return None

def ai_long_summary(title: str, text: str, source: str = "") -> str | None:
    client = _openai_client()
    if not client:
        return None
    try:
        import streamlit as st
        model = (st.secrets.get("OPENAI_MODEL") or "").strip() or "gpt-4o-mini"
    except Exception:
        model = "gpt-4o-mini"

    # Keep input size safe-ish
    if len(text) > 120_000:
        text = text[:120_000] + "…"

    prompt = f"""Schrijf een zeer uitgebreide Nederlandstalige samenvatting/achtergrond bij dit nieuwsbericht.
Stijl: journalistiek, helder, feitelijk, met context en duiding.
Vorm:
- Begin met een lead (3–5 zinnen).
- Daarna een chronologisch overzicht (kopjes + paragrafen).
- Leg begrippen/achtergrond kort uit waar nodig.
- Eindig met: 'Wat nu?' en 10–20 kernpunten in bullets.
Lengte: zo lang als nodig (mag heel lang), maar blijf bij de inhoud van de tekst (geen verzinsels).

Bron: {source}
Titel: {title}

TEKST:
{text}
"""
    try:
        resp = client.responses.create(model=model, input=prompt)
        out = getattr(resp, "output_text", None)
        if out:
            return out.strip()
    except Exception:
        return None
    return None

def ai_multi_source_background(main_title: str, snippets: list[dict]) -> str | None:
    client = _openai_client()
    if not client:
        return None
    try:
        import streamlit as st
        model = (st.secrets.get("OPENAI_MODEL") or "").strip() or "gpt-4o-mini"
    except Exception:
        model = "gpt-4o-mini"

    lines = []
    for i, s in enumerate(snippets, 1):
        lines.append(f"[{i}] {s.get('source','')} • {s.get('title','')} • {s.get('dt','')}")
        body = (s.get("text") or s.get("rss_summary") or "").strip()
        if len(body) > 6000:
            body = body[:6000] + "…"
        lines.append(body)
        lines.append("")
    evidence = "\n".join(lines).strip()

    prompt = f"""Maak één Nederlandstalig achtergrondstuk op basis van meerdere bron-snippets.
Regels:
- Gebruik uitsluitend info uit de snippets; geen aannames.
- Schrijf als een nieuwsredacteur: rustig, precies, context erbij.
Structuur:
1) Lead (2–4 zinnen)
2) Wat weten we zeker (details)
3) Context & achtergrond
4) Wat gebeurt er nu / wat volgt
5) Kernpunten (10–25 bullets)
Lengte: zo lang als nodig.

Onderwerp: {main_title}

SNIPPETS:
{evidence}
"""
    try:
        resp = client.responses.create(model=model, input=prompt)
        out = getattr(resp, "output_text", None)
        if out:
            return out.strip()
    except Exception:
        return None
    return None

def _tokenize(s: str) -> set[str]:
    s = (s or "").lower()
    s = re.sub(r"[^a-z0-9áéíóúàèìòùäëïöüñç\s-]", " ", s)
    toks = {t for t in re.split(r"\s+", s) if len(t) >= 4}
    stop = {"vandaag","gisteren","deze","maar","zoals","wordt","werden","heeft","hebben","door","voor","over","naar","niet","meer","gaat","gaan","nieuws","bericht","dit","dat","zijn"}
    return {t for t in toks if t not in stop}

def build_related_snippets(main_url: str, main_title: str, window_hours: int = 48, k: int = 7) -> list[dict]:
    main_tokens = _tokenize(main_title)
    if not main_tokens:
        return []
    now = datetime.now(timezone.utc)

    items = []
    for label in list(FEEDS.keys()):
        its, _ = collect_items([label], query=None, max_per_feed=25, force_fetch=False, ai_on=False)
        for it in its:
            if not it.get("title") or not it.get("link"):
                continue
            if it["link"] == main_url:
                continue
            dt = it.get("dt")
            if dt and dt < now - timedelta(hours=window_hours):
                continue
            tks = _tokenize(it["title"])
            inter = len(main_tokens.intersection(tks))
            if inter >= 2:
                it["_score"] = inter
                items.append(it)

    items.sort(key=lambda x: (x.get("_score",0), x.get("dt") or datetime(1970,1,1,tzinfo=timezone.utc)), reverse=True)

    picked = []
    domains_seen = {}
    for it in items:
        dom = host(it.get("link",""))
        domains_seen[dom] = domains_seen.get(dom, 0) + 1
        if domains_seen[dom] > 2:
            continue
        picked.append(it)
        if len(picked) >= k:
            break

    out = []
    for it in picked:
        src = it.get("link","")
        art = fetch_article_text(src)
        out.append({
            "source": host(src),
            "title": it.get("title",""),
            "dt": pretty_dt(it.get("dt")),
            "text": art.get("text","") if art.get("ok") else "",
            "rss_summary": it.get("rss_summary",""),
            "link": src,
        })
    return out


def resolve_google_news_url(gn_url: str) -> str:
    """Resolve Google News RSS 'articles/...' links to the original publisher URL (best-effort)."""
    try:
        if not gn_url or "news.google.com" not in gn_url:
            return gn_url

        # Sometimes url= already exists (either in the rss link or canonical)
        m = re.search(r"[?&]url=([^&\"']+)", gn_url)
        if m:
            return unquote(m.group(1))

        headers = {
            "User-Agent": UA,
            "Accept-Language": "nl-NL,nl;q=0.9,en;q=0.8",
        }
        r = requests.get(gn_url, headers=headers, timeout=10)
        html = r.text or ""

        # Canonical link may contain url=...
        m = re.search(r'<link[^>]+rel="canonical"[^>]+href="([^"]+)"', html)
        if m and m.group(1):
            cand = m.group(1)
            m2 = re.search(r"[?&]url=([^&\"']+)", cand)
            if m2:
                return unquote(m2.group(1))

        # Look for url=... anywhere in HTML
        m = re.search(r"[?&]url=([^&\"']+)", html)
        if m:
            return unquote(m.group(1))

        # Alternative: data-n-au sometimes contains the real url
        m = re.search(r'data-n-au="([^"]+)"', html)
        if m and m.group(1):
            return unquote(m.group(1))
    except Exception:
        pass
    return gn_url



def pretty(dt: datetime | None) -> str:
    return pretty_dt(dt)
