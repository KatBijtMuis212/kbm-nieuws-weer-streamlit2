import re
import time
import hashlib
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse, urlunparse, urlencode, parse_qsl

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
# Keep your existing CATEGORY_FEEDS / FEEDS if you already customized them.
CATEGORY_FEEDS = {
    "Net binnen": ["nos_binnenland", "nos_buitenland", "nu_algemeen", "ad_home", "rtv_mh"],
    "Binnenland": ["nos_binnenland", "nu_algemeen", "ad_home", "rtv_mh"],
    "Buitenland": ["nos_buitenland", "nu_algemeen", "ad_home"],
    "Show": ["nos_op3", "nu_entertainment", "ad_show", "ad_sterren"],
    "Lokaal": ["rtv_mh"],
    "Sport": ["nos_sport", "nos_f1", "nu_sport"],
    "Tech": ["nos_tech", "nu_tech"],
    "Opmerkelijk": ["nos_opmerkelijk", "nu_opmerkelijk"],
}

FEEDS = {
    "nos_binnenland": "https://feeds.nos.nl/nosnieuwsbinnenland",
    "nos_buitenland": "https://feeds.nos.nl/nosnieuwsbuitenland",
    "nos_opmerkelijk": "https://feeds.nos.nl/nosnieuwsopmerkelijk",
    "nos_tech": "https://feeds.nos.nl/nosnieuwstech",
    "nos_sport": "https://feeds.nos.nl/nossportalgemeen",
    "nos_f1": "https://feeds.nos.nl/nossportformule1",
    "nos_op3": "https://feeds.nos.nl/nosop3",
    "nu_algemeen": "https://www.nu.nl/rss/Algemeen",
    "nu_sport": "https://www.nu.nl/rss/Sport",
    "nu_entertainment": "https://www.nu.nl/rss/entertainment",
    "nu_opmerkelijk": "https://www.nu.nl/rss/Opmerkelijk",
    "nu_tech": "https://www.nu.nl/rss/tech-wetenschap",
    "ad_home": "https://www.ad.nl/home/rss.xml",
    "ad_show": "https://www.ad.nl/showbytes/rss.xml",
    "ad_sterren": "https://www.ad.nl/sterren/rss.xml",
    "rtv_mh": "https://rtvmiddenholland.nl/feed/",
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
_FEED_CACHE_TTL = 60  # seconds


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


def _tokenize(s: str) -> set[str]:
    s = (s or "").lower()
    s = re.sub(r"[^a-z0-9áéíóúàèìòùäëïöüñç\s-]", " ", s)
    toks = {t for t in re.split(r"\s+", s) if len(t) >= 4}
    stop = {
        "live", "video", "update", "vandaag", "gisteren", "deze", "waarom", "maar",
        "daarom", "ondertussen", "namelijk", "zoals", "wordt", "werden", "heeft",
        "hebben", "door", "voor", "over", "naar", "niet", "meer", "gaat", "gaan",
        "nieuws", "bericht", "dit", "dat", "zijn", "waar", "wie", "wanneer"
    }
    return {t for t in toks if t not in stop}


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
):
    items: list[dict] = []
    for label in feed_labels:
        feed_url = FEEDS.get(label)
        if not feed_url:
            continue
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
    return items


# ----------------------------
# ARTICLE FETCH + TEXT EXTRACTION
# ----------------------------
def _looks_like_privacy_gate(html: str) -> bool:
    h = (html or "").lower()
    return ("dpg media privacy gate" in h) or ("privacy gate" in h and "dpg" in h) or (
        "stg.start" in h and "cookie" in h
    )


def _candidate_urls_for_article(url: str) -> list[str]:
    url = _strip_tracking_params(url)
    u = urlparse(url)
    candidates = [url]

    if u.netloc.endswith("ad.nl"):
        base = urlunparse((u.scheme, u.netloc, u.path.rstrip("/") + "/", "", "", ""))
        candidates.append(base + "amp/")
        candidates.append(base + "print/")
        candidates.append(
            urlunparse((u.scheme, u.netloc, u.path, u.params, urlencode([("output", "1")]), u.fragment))
        )

    if u.netloc.endswith("nu.nl"):
        q = dict(parse_qsl(u.query, keep_blank_values=True))
        q.setdefault("output", "1")
        candidates.append(
            urlunparse((u.scheme, u.netloc, u.path, u.params, urlencode(list(q.items())), u.fragment))
        )

    seen = set()
    out = []
    for c in candidates:
        if c not in seen:
            seen.add(c)
            out.append(c)
    return out


def _fetch_html(url: str) -> str:
    r = _SESSION.get(url, timeout=_TIMEOUT, allow_redirects=True)
    r.raise_for_status()
    r.encoding = r.encoding or "utf-8"
    return r.text


def _extract_article_text_from_html(html: str) -> tuple[str, str]:
    soup = BeautifulSoup(html, "lxml")

    title = ""
    if soup.title and soup.title.get_text(strip=True):
        title = _clean_text(soup.title.get_text(" ", strip=True))
    ogt = soup.find("meta", property="og:title")
    if ogt and ogt.get("content"):
        title = _clean_text(ogt["content"])

    container = soup.find("article")
    if not container:
        container = soup.find("main") or soup.body

    for tag in container.find_all(["script", "style", "noscript", "svg", "form", "iframe"]):
        tag.decompose()

    paras = []
    for p in container.find_all(["p", "h2", "li"]):
        t = _clean_text(p.get_text(" ", strip=True))
        if t and len(t) >= 30:
            paras.append(t)

    text = "\n\n".join(paras)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return title, text


# ----------------------------
# AI (OpenAI) - optional
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


def ai_backgrounder(
    main_title: str,
    main_source: str,
    snippets: list[dict],
) -> str | None:
    """Write a deeper, multi-source explainer when full text isn't fetchable."""
    client = _openai_client()
    if not client:
        return None

    try:
        import streamlit as st
        model = (st.secrets.get("OPENAI_MODEL") or "").strip() or "gpt-5.2"
    except Exception:
        model = "gpt-5.2"

    # Build evidence pack
    lines = []
    for i, s in enumerate(snippets, 1):
        lines.append(f"[{i}] {s.get('source','')} • {s.get('title','')} • {s.get('dt','')}")
        body = (s.get("text") or s.get("rss_summary") or "").strip()
        # keep input bounded but still rich
        if len(body) > 6000:
            body = body[:6000] + "…"
        lines.append(body)
        lines.append("")

    evidence = "\n".join(lines).strip()

    prompt = f"""Schrijf een Nederlandstalig achtergrondstuk op basis van meerdere bronnen (hieronder).
Belangrijk:
- Gebruik alleen informatie die in de bron-snippets staat. Geen wilde aannames.
- Schrijf in een rustige nieuws-stijl: helder, feitelijk, maar met context.
- Structuur:
  1) Lead (2–3 zinnen: wat is er aan de hand?)
  2) Wat weten we zeker (met concrete details)
  3) Context & achtergrond (waarom dit speelt)
  4) Wat er nu gebeurt / wat er nog volgt
  5) Kernpunten (7–12 bullets)
- Lengte: zo lang als nodig (mag uitgebreid).

Hoofd-titel: {main_title}
Hoofd-bron: {main_source}

BRON-SNIPPETS:
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


def _format_dt(dt: datetime | None) -> str:
    if not dt:
        return ""
    try:
        return dt.astimezone().strftime("%d-%m %H:%M")
    except Exception:
        return ""


def build_related_snippets(main_url: str, main_title: str, window_hours: int = 24, k: int = 6) -> list[dict]:
    """Collect related items from all feeds using keyword overlap."""
    main_tokens = _tokenize(main_title)
    if not main_tokens:
        return []

    now = datetime.now(timezone.utc)
    all_labels = list(FEEDS.keys())

    items = []
    for label in all_labels:
        for it in collect_items([label], query=None, max_per_feed=25):
            if not it.get("title") or not it.get("link"):
                continue
            if it["link"] == main_url:
                continue
            dt = it.get("dt")
            if dt and dt < now - timedelta(hours=window_hours):
                continue
            tks = _tokenize(it["title"])
            inter = len(main_tokens.intersection(tks))
            if inter >= 2:  # small but meaningful
                it["_score"] = inter
                items.append(it)

    items.sort(key=lambda x: (x.get("_score", 0), x.get("dt") or datetime(1970,1,1,tzinfo=timezone.utc)), reverse=True)
    picked = []
    seen_hosts = set()
    for it in items:
        h = it.get("source") or host(it.get("link",""))
        # keep diversity: max 2 per host
        if sum(1 for p in picked if (p.get("source") or "") == h) >= 2:
            continue
        picked.append(it)
        if len(picked) >= k:
            break

    # Try to fetch some text for picked (best-effort, static only)
    out = []
    for it in picked:
        src = it.get("link","")
        txt = ""
        try:
            for cu in _candidate_urls_for_article(src):
                html = _fetch_html(cu)
                if _looks_like_privacy_gate(html):
                    continue
                _, txt = _extract_article_text_from_html(html)
                if txt and len(txt) > 400:
                    break
        except Exception:
            txt = ""

        out.append(
            {
                "source": it.get("source") or host(src),
                "title": it.get("title",""),
                "dt": _format_dt(it.get("dt")),
                "text": txt,
                "rss_summary": it.get("rss_summary",""),
                "link": src,
            }
        )
    return out


def load_article(url: str) -> dict:
    url = _strip_tracking_params(url)
    candidates = _candidate_urls_for_article(url)

    last_err = None
    for cu in candidates:
        try:
            html = _fetch_html(cu)
            if _looks_like_privacy_gate(html):
                last_err = "privacy_gate"
                continue
            title, text = _extract_article_text_from_html(html)
            if text and len(text) > 500:
                return {
                    "url": url,
                    "fetched_url": cu,
                    "title": title or "",
                    "text": text,
                    "ok": True,
                }
            last_err = "no_text"
        except Exception as e:
            last_err = str(e)

    return {
        "url": url,
        "fetched_url": "",
        "title": "DPG Media Privacy Gate" if last_err == "privacy_gate" else "",
        "text": "",
        "ok": False,
        "error": last_err or "unknown",
    }
