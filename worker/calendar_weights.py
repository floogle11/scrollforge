"""Calendar proximity weighting for the next ten days.

Public API: ``get_calendar_state(url=None, *, now=None, timeout=10)`` returns a
JSON-serializable dict with ``weights``, ``calendar_mode``, ``active_exam_course``
and ``events``. Empty/missing/broken calendars intentionally use baseline weights.
"""
from __future__ import annotations

import os
import re
from datetime import date, datetime, time, timedelta, timezone
from typing import Any
from urllib.parse import urlparse

BASELINE_WEIGHTS = {"sports_news": 0.65, "reddit_stories": 0.20,
                    "current_coursework": 0.10, "past_coursework": 0.05}
WEIGHT_TABLE = {
    "BASELINE": BASELINE_WEIGHTS,
    "EXAM_WINDOW": {"sports_news": 0.20, "reddit_stories": 0.15,
                    "current_coursework": 0.55, "past_coursework": 0.10},
    "CRUNCH_WINDOW": {"sports_news": 0.25, "reddit_stories": 0.15,
                      "current_coursework": 0.55, "past_coursework": 0.05},
    "EXAM_DAY": {"sports_news": 0.50, "reddit_stories": 0.35,
                 "current_coursework": 0.15, "past_coursework": 0.0},
}
EXAM_RE = re.compile(r"\b(exam|midterm|final|quiz|project)\b", re.I)
COURSE_RE = re.compile(r"\b[A-Z]{2,5}\s*[- ]?\s*\d{3,4}[A-Z]?\b", re.I)


def _utc(dt: datetime) -> datetime:
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)


def _as_datetime(value: Any, *, end: bool = False) -> datetime | None:
    if isinstance(value, datetime):
        return _utc(value)
    if isinstance(value, date):
        return datetime.combine(value + (timedelta(days=1) if end else timedelta()), time.min, timezone.utc)
    return None


def _event_record(component: Any) -> dict[str, Any] | None:
    if str(component.get("STATUS", "")).upper() == "CANCELLED":
        return None
    summary = str(component.get("SUMMARY", ""))
    description = str(component.get("DESCRIPTION", ""))
    text = f"{summary} {description}"
    if not EXAM_RE.search(text):
        return None
    start_prop = component.get("DTSTART")
    if start_prop is None:
        return None
    start = _as_datetime(start_prop.dt)
    if start is None:
        return None
    course_match = COURSE_RE.search(text)
    course = re.sub(r"\s*[- ]\s*", "-", course_match.group(0)).upper() if course_match else None
    raw_start = start_prop.dt
    event_day = raw_start.date() if isinstance(raw_start, datetime) else raw_start
    event_tz = raw_start.tzinfo if isinstance(raw_start, datetime) and raw_start.tzinfo else timezone.utc
    return {"summary": summary[:200], "start": start, "event_day": event_day,
            "event_tz": event_tz, "course": course}


def parse_calendar(ics_text: str, *, now: datetime | None = None) -> list[dict[str, Any]]:
    """Parse and expand an ICS calendar, including recurring instances and overrides."""
    try:
        from icalendar import Calendar
        import recurring_ical_events
    except ImportError as exc:
        raise RuntimeError("calendar parsing requires icalendar and recurring-ical-events") from exc
    now = _utc(now or datetime.now(timezone.utc))
    # Query a little beyond ten UTC days to include the full tenth local day
    # in calendars west of UTC; event-day filtering below enforces the 10-day limit.
    end = now + timedelta(days=11)
    calendar = Calendar.from_ical(ics_text)
    # Recurrence expansion applies EXDATE, RECURRENCE-ID overrides, and cancellation
    # overrides. The all-day end bound is inclusive at the query boundary.
    # Include earlier events from today for the EXAM_DAY decompression profile.
    expanded = recurring_ical_events.of(calendar).between(now - timedelta(days=1), end)
    found: list[dict[str, Any]] = []
    seen: set[tuple[str, datetime]] = set()
    for component in expanded:
        rec = _event_record(component)
        if rec is None:
            continue
        local_today = now.astimezone(rec["event_tz"]).date()
        if not (local_today <= rec["event_day"] <= local_today + timedelta(days=10)):
            continue
        key = (rec["summary"], rec["start"])
        if key not in seen:
            found.append(rec)
            seen.add(key)
    return sorted(found, key=lambda item: item["start"])


def _fetch_ics(url: str, timeout: float) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("ICS_CALENDAR_URL must be an http(s) URL")
    import requests
    response = requests.get(url, timeout=timeout, headers={"User-Agent": "ScrollForge/1.0"})
    response.raise_for_status()
    return response.text


def get_calendar_state(url: str | None = None, *, now: datetime | None = None,
                       timeout: float = 10) -> dict[str, Any]:
    """Fetch calendar if configured, otherwise return baseline state without I/O."""
    url = url if url is not None else os.getenv("ICS_CALENDAR_URL", "")
    current = _utc(now or datetime.now(timezone.utc))
    if not url.strip():
        return {"calendar_mode": "BASELINE", "active_exam_course": None,
                "weights": dict(BASELINE_WEIGHTS), "events": [], "calendar_error": None}
    try:
        events = parse_calendar(_fetch_ics(url, timeout), now=current)
    except Exception as exc:  # Calendar outages must not stop the feed pipeline.
        return {"calendar_mode": "BASELINE", "active_exam_course": None,
                "weights": dict(BASELINE_WEIGHTS), "events": [],
                "calendar_error": f"{type(exc).__name__}: calendar unavailable or invalid"}
    if not events:
        mode, active = "BASELINE", None
    else:
        first = events[0]
        event_now_day = current.astimezone(first["event_tz"]).date()
        delta = (first["event_day"] - event_now_day).days
        active = events[0]["course"]
        mode = ("BASELINE" if delta > 6 else "EXAM_DAY" if delta == 0 else
                "CRUNCH_WINDOW" if delta <= 2 else "EXAM_WINDOW")
        if mode == "BASELINE":
            active = None
    public_events = [{"summary": event["summary"],
                      "start": event["start"].isoformat().replace("+00:00", "Z"),
                      "course": event["course"]} for event in events]
    return {"calendar_mode": mode, "active_exam_course": active,
            "weights": dict(WEIGHT_TABLE[mode]), "events": public_events, "calendar_error": None}


def target_card_counts(weights: dict[str, float] | None = None, total: int = 12) -> dict[str, int]:
    """Convert proportions to integer targets, using largest remainder rounding."""
    if total < 0:
        raise ValueError("total must be nonnegative")
    weights = weights or BASELINE_WEIGHTS
    keys = list(weights)
    quotas = [max(0.0, float(weights[k])) * total for k in keys]
    result = {key: int(quota) for key, quota in zip(keys, quotas)}
    remaining = total - sum(result.values())
    order = sorted(range(len(keys)), key=lambda i: (quotas[i] - int(quotas[i]), -i), reverse=True)
    for i in order[:max(0, remaining)]:
        result[keys[i]] += 1
    return result
