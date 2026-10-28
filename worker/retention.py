"""Publication-age limits and article identity; comments never renew a headline."""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

MAX_AGE_DAYS = {"SPORTS": 7, "NEWS": 7, "STORY": 30}
TRACKING_KEYS = {"fbclid", "gclid", "mc_cid", "mc_eid", "ref", "ref_src"}


def parse_time(value: str) -> datetime:
    stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return stamp.replace(tzinfo=timezone.utc) if stamp.tzinfo is None else stamp.astimezone(timezone.utc)


def canonical_url(value: str | None) -> str | None:
    if not value:
        return None
    parts = urlsplit(value)
    query = [(key, val) for key, val in parse_qsl(parts.query, keep_blank_values=True)
             if not key.lower().startswith("utm_") and key.lower() not in TRACKING_KEYS]
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path.rstrip("/"),
                       urlencode(sorted(query)), ""))


def is_fresh(card: dict, now: datetime) -> bool:
    days = MAX_AGE_DAYS.get(card["category"])
    return days is None or parse_time(card["created_at"]) >= now - timedelta(days=days)


def retain_cards(cards: list[dict], *, now: str | None = None,
                 protected_ids: set[str] | None = None) -> list[dict]:
    """Drop expired unthreaded leisure, preserving published IDs across RSS refreshes.

    Old threads remain in JSON for the inbox; the browser separately excludes
    their expired headlines. Unknown pending parents are protected by the caller.
    """
    current = parse_time(now) if now else datetime.now(timezone.utc)
    protected_ids = protected_ids or set()
    result: list[dict] = []
    articles: dict[tuple, dict] = {}
    for original in cards:
        card = dict(original)
        if not is_fresh(card, current) and not card.get("comments") and card["id"] not in protected_ids:
            continue
        if card["category"] not in MAX_AGE_DAYS:
            result.append(card)
            continue
        url = canonical_url(card.get("source_url"))
        key = ("url", url) if url else ("title", card["category"],
              re.sub(r"\W+", " ", card["title"].casefold()).strip(), card["created_at"][:10])
        previous = articles.get(key)
        # Keep parent identities of distinct live conversations addressable.
        if previous and (card.get("comments") or card["id"] in protected_ids):
            if previous["id"] != card["id"]:
                result.append(card)
                continue
        if previous:
            # Preserve the original identity/date so a new title or tracking URL
            # cannot turn an already-seen article back into an unseen card.
            previous["created_at"] = min(previous["created_at"], card["created_at"], key=parse_time)
            continue
        articles[key] = card
        result.append(card)
    # SVG boards are larger than text posts. Bound generated interest inventory
    # independently of the archive cap, retaining starter lessons and conversations.
    interests = [card for card in result if card["category"] == "INTEREST"
                 and not card["id"].startswith("chess_italian_")
                 and not card.get("comments") and card["id"] not in protected_ids]
    keep = {card["id"] for card in sorted(interests, key=lambda c: parse_time(c["created_at"]), reverse=True)[:54]}
    return [card for card in result if card not in interests or card["id"] in keep]
