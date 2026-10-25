"""Zero-token RSS and Reddit ingestion with isolated source failures."""
from __future__ import annotations

import hashlib
import html
import re
import unicodedata
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from calendar import timegm
from concurrent.futures import ThreadPoolExecutor
from typing import Any

SOURCES = [
    {"name": "broncos", "url": "https://www.denverbroncos.com/rss/news", "category": "SPORTS"},
    {"name": "espn_nfl", "url": "https://www.espn.com/espn/rss/nfl/news", "category": "SPORTS"},
    {"name": "nfl", "url": "https://www.nfl.com/feeds-rs/news", "category": "SPORTS"},
    {"name": "bbc_world", "url": "https://feeds.bbci.co.uk/news/world/rss.xml", "category": "NEWS"},
    {"name": "npr", "url": "https://feeds.npr.org/1001/rss.xml", "category": "NEWS"},
    {"name": "guardian_us", "url": "https://www.theguardian.com/us-news/rss", "category": "NEWS"},
    {"name": "bbc_technology", "url": "https://feeds.bbci.co.uk/news/technology/rss.xml", "category": "NEWS"},
    {"name": "reddit_nfl", "url": "https://www.reddit.com/r/nfl/hot/.rss?limit=25", "category": "SPORTS"},
    {"name": "reddit_broncos", "url": "https://www.reddit.com/r/DenverBroncos/hot/.rss?limit=25", "category": "SPORTS"},
    {"name": "reddit_news", "url": "https://www.reddit.com/r/news/hot/.rss?limit=25", "category": "NEWS"},
    {"name": "reddit_worldnews", "url": "https://www.reddit.com/r/worldnews/hot/.rss?limit=25", "category": "NEWS"},
    {"name": "reddit_todayilearned", "url": "https://www.reddit.com/r/todayilearned/hot/.rss?limit=25", "category": "STORY"},
    {"name": "reddit_space", "url": "https://www.reddit.com/r/space/hot/.rss?limit=25", "category": "STORY"},
    {"name": "nasa", "url": "https://www.nasa.gov/feed/", "category": "STORY"},
    {"name": "smithsonian", "url": "https://www.smithsonianmag.com/rss/latest_articles/", "category": "STORY"},
    {"name": "reddit_askhistorians", "url": "https://www.reddit.com/r/AskHistorians/.rss", "category": "STORY"},
    {"name": "reddit_techsupport", "url": "https://www.reddit.com/r/talesfromtechsupport/.rss", "category": "STORY"},
]


def sanitize_text(value: Any, limit: int = 12000) -> str:
    """Strip markup, normalize whitespace, and bound untrusted feed text."""
    raw = html.unescape(str(value or ""))
    raw = re.sub(r"(?is)<(script|style).*?>.*?</\1\s*>", " ", raw)
    raw = re.sub(r"(?s)<[^>]+>", " ", raw)
    raw = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", raw)
    raw = unicodedata.normalize("NFKC", raw)
    raw = "".join(ch for ch in raw if ch in "\n\t" or unicodedata.category(ch)[0] != "C")
    return re.sub(r"\s+", " ", raw).strip()[:limit]


def _entry_timestamp(entry: Any) -> str | None:
    struct = entry.get("published_parsed") or entry.get("updated_parsed")
    if struct:
        return datetime.fromtimestamp(timegm(struct), timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    for field in ("published", "updated", "created"):
        value = entry.get(field)
        if not value:
            continue
        try:
            parsed = parsedate_to_datetime(value)
            parsed = parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)
            return parsed.isoformat(timespec="seconds").replace("+00:00", "Z")
        except (TypeError, ValueError, OverflowError):
            continue
    # Unknown publication age must not masquerade as fresh on every refresh.
    return None


def normalize_entry(entry: Any, source: dict[str, str]) -> dict[str, Any] | None:
    title = sanitize_text(entry.get("title", ""), 160)
    published = _entry_timestamp(entry)
    if not title or published is None:
        return None
    link = str(entry.get("link") or "").strip()
    if not link.startswith(("http://", "https://")):
        link = ""
    content = entry.get("content") or []
    body = sanitize_text(entry.get("summary") or entry.get("description") or
                         (content[0].get("value") if content else None) or title)
    if source["name"].startswith("reddit_"):
        # Atom entries include navigation and author boilerplate after the excerpt.
        body = re.split(r"\s*submitted by\s*", body, maxsplit=1, flags=re.I)[0]
        body = re.sub(r"\[\s*(?:link|comments)\s*\]", "", body, flags=re.I).strip()
    # Publish a short excerpt and send readers to the original post or article.
    if len(body) > 600:
        body = body[:597].rsplit(" ", 1)[0] + "…"
    if not body:
        body = title
    identity = str(entry.get("id") or link or "")
    stable_parts = ((source["name"], identity) if identity else
                    (source["name"], str(entry.get("published") or entry.get("updated") or ""), title))
    stable = hashlib.sha256("\0".join(stable_parts).encode("utf-8")).hexdigest()[:18]
    return {
        "id": f"rss_{source['name']}_{stable}",
        "created_at": published,
        "category": source["category"],
        "course_tag": None,
        "title": title,
        "body_markdown": body,
        "solution_markdown": None,
        "source_url": link or None,
        "parent_card_id": None,
        "comments": [],
    }


def fetch_source(source: dict[str, str], *, timeout: float = 8,
                 limit: int = 15) -> tuple[list[dict[str, Any]], str | None]:
    """Fetch one configured RSS source. Returns cards and an optional error string."""
    try:
        import feedparser
        import requests
        response = requests.get(source["url"], timeout=timeout,
                                headers={"User-Agent": "ScrollForge/1.0 (+https://github.com/floogle11/scrollforge)"})
        response.raise_for_status()
        parsed = feedparser.parse(response.content)
        if getattr(parsed, "bozo", False) and not getattr(parsed, "entries", None):
            raise ValueError(str(getattr(parsed, "bozo_exception", "invalid feed"))[:180])
        cards = []
        for entry in parsed.entries[:limit]:
            card = normalize_entry(entry, source)
            if card:
                cards.append(card)
        return cards, None
    except Exception as exc:
        return [], f"{type(exc).__name__}: source unavailable or invalid"


def ingest_all(*, sources: list[dict[str, str]] | None = None, timeout: float = 8,
               limit_per_source: int = 15) -> dict[str, Any]:
    """Fetch sources independently; one unavailable feed never drops others."""
    cards: list[dict[str, Any]] = []
    status: dict[str, dict[str, Any]] = {}
    configured = sources if sources is not None else SOURCES
    with ThreadPoolExecutor(max_workers=5) as pool:
        results = pool.map(lambda source: fetch_source(source, timeout=timeout, limit=limit_per_source), configured)
        for source, (items, error) in zip(configured, results):
            cards.extend(items)
            status[source["name"]] = {"count": len(items), "error": error}
    return {"cards": cards, "sources": status}


def fetch_feeds(**kwargs: Any) -> dict[str, Any]:
    """Compatibility alias for callers that prefer an action-oriented name."""
    return ingest_all(**kwargs)
