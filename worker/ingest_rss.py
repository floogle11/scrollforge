"""Zero-token RSS and Reddit ingestion with isolated source failures."""
from __future__ import annotations

import hashlib
import html
import re
import unicodedata
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from calendar import timegm
from typing import Any

SOURCES = [
    {"name": "broncos", "url": "https://www.denverbroncos.com/rss/news", "category": "SPORTS"},
    {"name": "nfl", "url": "https://www.nfl.com/feeds-rs/news", "category": "NEWS"},
    {"name": "reddit_engineeringstudents", "url": "https://www.reddit.com/r/EngineeringStudents/.rss", "category": "STORY"},
    {"name": "reddit_askhistorians", "url": "https://www.reddit.com/r/AskHistorians/.rss", "category": "STORY"},
    {"name": "reddit_techsupport", "url": "https://www.reddit.com/r/talesfromtechsupport/.rss", "category": "STORY"},
    {"name": "reddit_broncos", "url": "https://www.reddit.com/r/DenverBroncos/.rss", "category": "STORY"},
    {"name": "reddit_nfl", "url": "https://www.reddit.com/r/nfl/.rss", "category": "STORY"},
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


def _entry_timestamp(entry: Any) -> str:
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
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def normalize_entry(entry: Any, source: dict[str, str]) -> dict[str, Any] | None:
    title = sanitize_text(entry.get("title", ""), 160)
    if not title:
        return None
    link = str(entry.get("link") or "").strip()
    if not link.startswith(("http://", "https://")):
        link = ""
    body = sanitize_text(entry.get("summary") or entry.get("description") or title)
    if not body:
        body = title
    identity = str(entry.get("id") or link or "")
    stable_parts = ((source["name"], identity) if identity else
                    (source["name"], str(entry.get("published") or entry.get("updated") or ""), title))
    stable = hashlib.sha256("\0".join(stable_parts).encode("utf-8")).hexdigest()[:18]
    return {
        "id": f"rss_{source['name']}_{stable}",
        "created_at": _entry_timestamp(entry),
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
                                headers={"User-Agent": "ScrollForge/1.0 (+https://github.com)"})
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
    for source in (sources if sources is not None else SOURCES):
        items, error = fetch_source(source, timeout=timeout, limit=limit_per_source)
        cards.extend(items)
        status[source["name"]] = {"count": len(items), "error": error}
    return {"cards": cards, "sources": status}


def fetch_feeds(**kwargs: Any) -> dict[str, Any]:
    """Compatibility alias for callers that prefer an action-oriented name."""
    return ingest_all(**kwargs)
