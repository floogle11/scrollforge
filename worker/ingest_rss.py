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
    {"name": "espn_nhl", "url": "https://www.espn.com/espn/rss/nhl/news", "category": "SPORTS", "sport": "hockey"},
    {"name": "nhl_mammoth", "url": "https://www.nhl.com/utah/news", "format": "nhl", "category": "SPORTS", "sport": "hockey", "team": "Utah Mammoth"},
    {"name": "nhl_avalanche", "url": "https://www.nhl.com/avalanche/news", "format": "nhl", "category": "SPORTS", "sport": "hockey", "team": "Colorado Avalanche"},
    {"name": "espn_avalanche", "url": "https://www.espn.com/espn/rss/nhl/news?teamId=17", "category": "SPORTS", "sport": "hockey", "team": "Colorado Avalanche"},
    {"name": "espn_mammoth", "url": "https://www.espn.com/espn/rss/nhl/news?teamId=129764", "category": "SPORTS", "sport": "hockey", "team": "Utah Mammoth"},
    {"name": "reddit_avalanche", "url": "https://www.reddit.com/r/ColoradoAvalanche/hot/.rss?limit=50", "category": "SPORTS", "sport": "hockey", "team": "Colorado Avalanche"},
    {"name": "reddit_mammoth", "url": "https://www.reddit.com/r/UtahMammoth/hot/.rss?limit=50", "category": "SPORTS", "sport": "hockey", "team": "Utah Mammoth"},
    {"name": "reddit_utahhockey", "url": "https://www.reddit.com/r/Utah_Hockey/.rss?limit=50", "category": "SPORTS", "sport": "hockey", "team": "Utah Mammoth"},
    {"name": "reddit_hockey", "url": "https://www.reddit.com/r/hockey/hot/.rss?limit=50", "category": "SPORTS", "sport": "hockey"},
    {"name": "reddit_broncos", "url": "https://www.reddit.com/r/DenverBroncos/hot/.rss?limit=25", "category": "SPORTS"},
    {"name": "reddit_news", "url": "https://www.reddit.com/r/news/hot/.rss?limit=25", "category": "NEWS"},
    {"name": "reddit_worldnews", "url": "https://www.reddit.com/r/worldnews/hot/.rss?limit=25", "category": "NEWS"},
    {"name": "reddit_todayilearned", "url": "https://www.reddit.com/r/todayilearned/hot/.rss?limit=25", "category": "STORY"},
    {"name": "reddit_space", "url": "https://www.reddit.com/r/space/hot/.rss?limit=25", "category": "STORY"},
    {"name": "nasa", "url": "https://www.nasa.gov/feed/", "category": "STORY"},
    {"name": "smithsonian", "url": "https://www.smithsonianmag.com/rss/latest_articles/", "category": "STORY"},
    {"name": "reddit_askhistorians", "url": "https://www.reddit.com/r/AskHistorians/.rss", "category": "STORY"},
    {"name": "reddit_techsupport", "url": "https://www.reddit.com/r/talesfromtechsupport/.rss", "category": "STORY"},
    {"name": "reddit_boru", "url": "https://www.reddit.com/r/BestofRedditorUpdates/top/.rss?t=week&limit=50", "category": "STORY", "topic": "drama"},
    {"name": "reddit_borupdates", "url": "https://www.reddit.com/r/BORUpdates/.rss?limit=50", "category": "STORY", "topic": "drama"},
    {"name": "reddit_aita", "url": "https://www.reddit.com/r/AmItheAsshole/.rss?limit=50", "category": "STORY", "topic": "drama"},
    {"name": "reddit_hobbydrama", "url": "https://www.reddit.com/r/HobbyDrama/top/.rss?t=month&limit=50", "category": "STORY", "topic": "drama"},
    {"name": "reddit_subredditdrama", "url": "https://www.reddit.com/r/SubredditDrama/.rss?limit=50", "category": "STORY", "topic": "drama"},
    {"name": "reddit_pettyrevenge", "url": "https://www.reddit.com/r/pettyrevenge/.rss?limit=50", "category": "STORY", "topic": "drama"},
    {"name": "reddit_maliciouscompliance", "url": "https://www.reddit.com/r/MaliciousCompliance/top/.rss?t=week&limit=50", "category": "STORY", "topic": "drama"},
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
            try:
                parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
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
        if "not supported on old Reddit" in body:
            body = "Open the original Reddit post to see its media and discussion."
    # Publish a short excerpt and send readers to the original post or article.
    if len(body) > 600:
        body = body[:597].rsplit(" ", 1)[0] + "…"
    if not body:
        body = title
    if source.get("team") and source["name"].startswith("espn_"):
        pattern = r"\b(?:utah|mammoth)\b" if source["team"] == "Utah Mammoth" else r"\b(?:colorado|avalanche|avs)\b"
        if not re.search(pattern, title + " " + body, re.I):
            return None  # Team RSS can include unrelated league-wide headlines.
    identity = str(entry.get("id") or link or "")
    stable_parts = ((source["name"], identity) if identity else
                    (source["name"], str(entry.get("published") or entry.get("updated") or ""), title))
    stable = hashlib.sha256("\0".join(stable_parts).encode("utf-8")).hexdigest()[:18]
    card = {
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
    for field in ("sport", "team", "topic"):
        if source.get(field):
            card[field] = source[field]
    image = entry.get("image_url")
    if isinstance(image, str) and image.startswith("https://"):
        card["image_url"] = image
    return card


def fetch_source(source: dict[str, str], *, timeout: float = 8,
                 limit: int = 50) -> tuple[list[dict[str, Any]], str | None]:
    """Fetch one configured RSS source. Returns cards and an optional error string."""
    try:
        import feedparser
        import requests
        response = requests.get(source["url"], timeout=timeout,
                                headers={"User-Agent": "ScrollForge/1.0 (+https://github.com/floogle11/scrollforge)"})
        response.raise_for_status()
        if source.get("format") == "nhl":
            from .ingest_nhl import fetch_articles
            entries = fetch_articles(source, response.text, timeout=timeout, limit=limit)
            cards = [card for entry in entries if (card := normalize_entry(entry, source))]
            return cards, None
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
               limit_per_source: int = 50) -> dict[str, Any]:
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
