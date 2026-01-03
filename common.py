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
# RTL direct scrape fallback (no Google News)
# ----------------------------
_RTL_LISTING_CACHE = {}
_RTL_OGIMG_CACHE = {}

def _tz_nl():
    # Best-effort NL tz without external deps; DST may be off by 1h around transitions, acceptable for "recent hours" filtering.
    return timezone(timedelta(hours=1))

def _abs(url: str) -> str:
    if not url:
        return ""
    if url.startswith("http"):
        return url
    if url.startswith("//"):
        return "https:" + url
    if url.startswith("/"):
        return "https://www.rtl.nl" + url
    return "https://www.rtl.nl/" + url.lstrip("/")

def _fetch_og_image(url: str, timeout: float = 8.0) -> str:
    if not url:
        return ""
    if url in _RTL_OGIMG_CACHE:
        return _RTL_OGIMG_CACHE[url]
    try:
        r = requests.get(url, headers=UA_HEADERS, timeout=timeout)
        if r.status_code >= 400:
            _RTL_OGIMG_CACHE[url] = ""
            return ""
        soup = BeautifulSoup(r.text, "lxml")
        m = soup.find("meta", attrs={"property": "og:image"}) or soup.find("meta", attrs={"name": "og:image"})
        img = (m.get("content") if m else "") or ""
        img = _abs(img)
        _RTL_OGIMG_CACHE[url] = img
        return img
    except Exception:
        _RTL_OGIMG_CACHE[url] = ""
        return ""

def fetch_rtl_listing(kind: str = "nieuws", timeout: float = 10.0, max_items: int = 80):
    """Scrape https://www.rtl.nl/nieuws or /boulevard and return items with optional section + time."""
    kind = (kind or "nieuws").strip().lower()
    url = "https://www.rtl.nl/nieuws" if kind == "nieuws" else "https://www.rtl.nl/boulevard"
    cache_key = f"rtl:{kind}"
    now = datetime.now(_tz_nl())
    # cache for 3 minutes
    hit = _RTL_LISTING_CACHE.get(cache_key)
    if hit and (time.time() - hit["ts"] < 180):
        return hit["items"]

    try:
        r = requests.get(url, headers=UA_HEADERS, timeout=timeout)
        r.raise_for_status()
        html = r.text
    except Exception:
        return []

    soup = BeautifulSoup(html, "lxml")

    # Collect sections: (section_title, list_of_links)
    sections = []
    current = "RTL " + ("Nieuws" if kind == "nieuws" else "Boulevard")
    collected = []

    # RTL pages have headings (h2/h3) and many <a> cards. We'll walk DOM roughly in order.
    for el in soup.find_all(["h2", "h3", "a"]):
        if el.name in ("h2", "h3"):
            # flush previous
            if collected:
                sections.append((current, collected))
                collected = []
            t = el.get_text(" ", strip=True)
            if t:
                current = t
            continue

        if el.name == "a":
            href = el.get("href") or ""
            txt = el.get_text(" ", strip=True)
            if not href or not txt:
                continue
            # keep news/boulevard/rtlz/sport subpaths
            if not (href.startswith("/") and ("/nieuws" in href or "/boulevard" in href or "/rtlz" in href or "/sport" in href)):
                continue
            full = _abs(href)

            # time can appear inside the anchor text like "01:53 ..." or appended; extract HH:MM if present
            hhmm = None
            m = re.search(r"\b(\d{1,2}:\d{2})\b", txt)
            if m:
                hhmm = m.group(1)
                # remove time from title text
                txt = re.sub(r"\b\d{1,2}:\d{2}\b\s*", "", txt).strip()

            dt = None
            if hhmm:
                try:
                    h, mi = hhmm.split(":")
                    cand = now.replace(hour=int(h), minute=int(mi), second=0, microsecond=0)
                    # if time in future (relative to now) assume it was yesterday
                    if cand > now + timedelta(minutes=2):
                        cand = cand - timedelta(days=1)
                    dt = cand
                except Exception:
                    dt = None

            collected.append({"title": txt, "link": full, "dt": dt, "section": current, "source": "rtl.nl"})
            if len(collected) >= max_items:
                break

    if collected:
        sections.append((current, collected))

    # Flatten, keep unique by link
    out = []
    seen = set()
    for sec, items in sections:
        for it in items:
            if it["link"] in seen:
                continue
            seen.add(it["link"])
            it["section"] = sec or it.get("section") or ""
            out.append(it)
            if len(out) >= max_items:
                break
        if len(out) >= max_items:
            break

    # Try to attach images for first handful (cheap-ish)
    for it in out[:18]:
        if not it.get("img"):
            it["img"] = _fetch_og_image(it["link"])

    _RTL_LISTING_CACHE[cache_key] = {"ts": time.time(), "items": out}
    return out

def rtl_items_for_section(kind: str, section_name: str | None):
    items = fetch_rtl_listing(kind=kind)
    if not section_name:
        return items
    target = section_name.strip().lower()
    return [x for x in items if (x.get("section","").strip().lower() == target)]

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

# RTL.nl (direct scrape)
"rtl_list_nieuws": "rtl:list:nieuws",
"rtl_list_boulevard": "rtl:list:boulevard",

# RTL sections (from /nieuws listing)
"rtl_list_binnenland": "rtl:list:nieuws:Binnenland",
"rtl_list_buitenland": "rtl:list:nieuws:Buitenland",
"rtl_list_sport": "rtl:list:nieuws:Sport",
"rtl_list_lifestyle": "rtl:list:nieuws:Lifestyle",
    "rtl_lifestyle": gn("lifestyle OR gezondheid OR wonen OR eten", days=45),
    "rtl_uitzendingen": gn("uitzendingen OR gemist OR kijken", days=45),
    "rtl_puzzels": gn("puzzels OR quiz OR spel", days=45),
}

CATEGORY_FEEDS = {
    "Net binnen": ["nos_binnenland","nos_buitenland","nu_algemeen","ad_home","rtv_mh","rtl_list_nieuws"],
    "Binnenland": ["nos_binnenland","nu_algemeen","ad_home","rtv_mh","rtl_list_binnenland"],
    "Buitenland": ["nos_buitenland","nu_algemeen","ad_home","rtl_list_buitenland"],
    "Show": ["nos_op3","nu_entertainment","ad_show","ad_sterren","rtl_list_boulevard"],
    "Lokaal": ["rtv_mh"],
    "Sport": ["nos_sport","nos_f1","nu_sport","rtl_list_sport"],
    "Tech": ["nos_tech","nu_tech","rtl_list_nieuws"],
    "Opmerkelijk": ["nos_opmerkelijk","nu_opmerkelijk","rtl_list_nieuws"],

    # RTL apart
    "RTL Nieuws": ["rtl_list_nieuws"],
    "RTL Boulevard": ["rtl_list_boulevard"],
    "RTL TV": ["rtl_tv"],
    "RTL Sport": ["rtl_list_sport"],
    "RTL Politiek": ["rtl_politiek"],
    "RTL Binnenland": ["rtl_list_binnenland"],
    "RTL Buitenland": ["rtl_list_buitenland"],
    "RTL Economie": ["rtl_economie"],
    "RTL Lifestyle": ["rtl_lifestyle"],
    "RTL Uitzendingen": ["rtl_uitzendingen"],
    "RTL Puzzels": ["rtl_puzzels"],
    "RTL Algemeen": ["rtl_list_nieuws"],
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
        return urlparse(url).netloc.replace("www.", "")
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

# RTL pseudo-feeds (direct scrape)
if isinstance(feed_url, str) and feed_url.startswith("rtl:list:"):
    # format: rtl:list:<kind>[:<section>]
    parts = feed_url.split(":", 3)
    kind = parts[2] if len(parts) > 2 else "nieuws"
    section = parts[3] if len(parts) > 3 else None
    rtl_items = rtl_items_for_section(kind=kind, section_name=section)
    for it in rtl_items[:max_per_feed]:
        title = _clean_text(it.get("title",""))
        link = _strip_tracking_params(it.get("link",""))
        dt = it.get("dt")
        items.append({
            "title": title,
            "link": link,
            "dt": dt,
            "img": it.get("img"),
            "rss_summary": None,
        })
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
