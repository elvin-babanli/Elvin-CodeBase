import os
import time
import requests
import feedparser
from datetime import datetime, timezone
from django.core.cache import cache

CACHE_KEY = "home_feed_v1"
CACHE_TTL = int(os.getenv("CACHE_TTL_SECONDS", "1800"))  # 30 dəq

def _utc(dt):
    if isinstance(dt, datetime):
        return dt.astimezone(timezone.utc)
    return dt

def fetch_hn(limit=15):
    """Hacker News (Algolia) — dev xəbərləri"""
    query = os.getenv("HN_QUERY", "python OR django OR ai")
    url = "https://hn.algolia.com/api/v1/search_by_date"
    r = requests.get(url, params={"query": query, "tags": "story", "hitsPerPage": limit}, timeout=15)
    r.raise_for_status()
    items = []
    for h in r.json().get("hits", []):
        title = h.get("title") or h.get("story_title")
        url = h.get("url") or f"https://news.ycombinator.com/item?id={h.get('objectID')}"
        if not title or not url:
            continue
        published = h.get("created_at")  # ISO 8601
        items.append({
            "title": title,
            "url": url,
            "source": "Hacker News",
            "source_url": "https://news.ycombinator.com/",
            "published_at": published,
            "image_url": None,
            "topic": "Programming",
            "summary": h.get("story_text") or "",
        })
    return items

def fetch_devto(limit=12):
    """DEV.to — dev məqalələri"""
    tag = os.getenv("DEVTO_TAG")  # məsələn: python
    params = {"per_page": limit}
    if tag:
        params["tag"] = tag
    r = requests.get("https://dev.to/api/articles", params=params,
                     headers={"User-Agent": "PortfolioFeed/1.0"}, timeout=15)
    r.raise_for_status()
    items = []
    for a in r.json():
        items.append({
            "title": a["title"],
            "url": a["url"],
            "source": "DEV Community",
            "source_url": "https://dev.to/",
            "published_at": a.get("published_at"),
            "image_url": a.get("cover_image"),
            "topic": "Programming",
            "summary": (a.get("description") or "")[:300],
        })
    return items

def fetch_arxiv(limit=12):
    """arXiv — AI/LG/CL tədqiqatları (RSS/Atom)"""
    q = "cat:cs.AI+OR+cs.LG+OR+cs.CL"
    url = f"http://export.arxiv.org/api/query?search_query={q}&sortBy=submittedDate&sortOrder=descending&max_results={limit}"
    feed = feedparser.parse(url)
    items = []
    for e in feed.entries:
        pub = None
        if getattr(e, "published_parsed", None):
            pub = datetime(*e.published_parsed[:6], tzinfo=timezone.utc).isoformat()
        items.append({
            "title": e.title,
            "url": e.link,
            "source": "arXiv",
            "source_url": "https://arxiv.org/",
            "published_at": pub,
            "image_url": None,
            "topic": "AI/Research",
            "summary": getattr(e, "summary", "")[:400],
        })
    return items

def fetch_press(limit_per_feed=8):
    """Apple & NVIDIA press RSS — BigTech xəbərləri"""
    feeds = [
        "https://www.apple.com/newsroom/rss-feed.rss",
        "https://nvidianews.nvidia.com/rss",
    ]
    items = []
    for f in feeds:
        parsed = feedparser.parse(f)
        for e in parsed.entries[:limit_per_feed]:
            pub = None
            if getattr(e, "published_parsed", None):
                pub = datetime(*e.published_parsed[:6], tzinfo=timezone.utc).isoformat()
            items.append({
                "title": e.title,
                "url": e.link,
                "source": parsed.feed.get("title", "Press"),
                "source_url": parsed.feed.get("link"),
                "published_at": pub,
                "image_url": None,
                "topic": "BigTech",
                "summary": getattr(e, "summary", "")[:400],
            })
    return items

def _sort_and_dedup(items):
    # dedup URL üzrə
    seen = set()
    clean = []
    for it in items:
        u = it.get("url")
        if not u or u in seen:
            continue
        seen.add(u)
        clean.append(it)
    # tarixə görə azalan
    def keyfn(x):
        # published_at ola bilməyə də bilər — o halda indiki zaman
        ts = x.get("published_at")
        try:
            return datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except Exception:
            return datetime.fromtimestamp(0, tz=timezone.utc)
    clean.sort(key=keyfn, reverse=True)
    return clean

def get_home_feed(force_refresh=False):
    if not force_refresh:
        cached = cache.get(CACHE_KEY)
        if cached:
            return cached
    try:
        # Mənbələr: HN + DEV + arXiv + Press
        data = []
        data += fetch_hn(limit=15)
        data += fetch_devto(limit=12)
        data += fetch_arxiv(limit=12)
        data += fetch_press(limit_per_feed=8)
        data = _sort_and_dedup(data)[:50]
        cache.set(CACHE_KEY, data, CACHE_TTL)
        return data
    except Exception as e:
        # Xəta olsa, ən azı boş siyahı qaytarırıq (sayt dayanmasın)
        return []
