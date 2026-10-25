"""ScrollForge pipeline entry point.

Normal mode collects RSS/calendar input and atomically writes a validated
feed. ``--dry-run`` reads only local files and never calls the network. Run
``--resolve-only`` after publishing the feed commit to GitHub Pages.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:  # Support both `python -m worker.run_pipeline` and script invocation.
    from .calendar_weights import get_calendar_state
    from .generate_batch import generate_batch, _github_headers
    from .ingest_rss import ingest_all
    from .retention import retain_cards
except ImportError:  # pragma: no cover - exercised by command-line workflow
    from calendar_weights import get_calendar_state
    from generate_batch import generate_batch, _github_headers
    from ingest_rss import ingest_all
    from retention import retain_cards

ROOT = Path(__file__).resolve().parents[1]
FEED_PATH = ROOT / "docs" / "data" / "feed.json"
FEED_SCHEMA_PATH = ROOT / "contracts" / "feed_schema.json"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def validate_feed(feed: Any) -> dict[str, Any]:
    import jsonschema
    schema = json.loads(FEED_SCHEMA_PATH.read_text(encoding="utf-8"))
    jsonschema.validate(feed, schema, format_checker=jsonschema.FormatChecker())
    return feed


def _load_feed(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"last_updated": utc_now(), "calendar_mode": "BASELINE",
                "active_exam_course": None, "cards": []}
    with path.open("r", encoding="utf-8") as handle:
        existing = json.load(handle)
    return validate_feed(existing)


def _merge_comments(old: list[dict[str, Any]], new: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id = {comment["id"]: comment for comment in old}
    for comment in new:
        if comment["id"] not in by_id:
            by_id[comment["id"]] = comment
    return sorted(by_id.values(), key=lambda comment: (comment["created_at"], comment["id"]))


def _activity_timestamp(card: dict[str, Any]) -> float:
    """UTC timestamp of the card's newest creation or comment activity."""
    stamps = [card["created_at"], *(comment["created_at"] for comment in card.get("comments", []))]
    parsed = [datetime.fromisoformat(str(value).replace("Z", "+00:00")) for value in stamps]
    normalized = [value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value for value in parsed]
    return max(value.timestamp() for value in normalized)


def select_rss_mix(cards: list[dict[str, Any]], quota: int) -> list[dict[str, Any]]:
    """Round-robin RSS source buckets so one prolific feed cannot monopolize a batch."""
    buckets: dict[str, list[dict[str, Any]]] = {}
    for card in cards:
        card_id = str(card.get("id", ""))
        source = card_id[len("rss_"):].rsplit("_", 1)[0] if card_id.startswith("rss_") else card_id
        buckets.setdefault(source, []).append(card)
    picked: list[dict[str, Any]] = []
    while len(picked) < max(0, quota):
        progressed = False
        for bucket in buckets.values():
            if bucket and len(picked) < quota:
                picked.append(bucket.pop(0))
                progressed = True
        if not progressed:
            break
    return picked


def merge_feed(existing: dict[str, Any], *, new_cards: list[dict[str, Any]],
               replies: list[dict[str, Any]], issues: list[dict[str, Any]],
               calendar: dict[str, Any], now: str | None = None, cap: int = 300) -> dict[str, Any]:
    """Dedupe cards, preserve historical comments, and embed only matched replies."""
    by_id: dict[str, dict[str, Any]] = {}
    for card in list(existing.get("cards", [])) + list(new_cards):
        old = by_id.get(card["id"])
        if old is None:
            by_id[card["id"]] = dict(card)
        else:
            merged = dict(old)
            merged.update({key: value for key, value in card.items() if key != "comments"})
            merged["created_at"] = min(old["created_at"], card["created_at"],
                                       key=lambda value: datetime.fromisoformat(value.replace("Z", "+00:00")))
            merged["comments"] = _merge_comments(old.get("comments", []), card.get("comments", []))
            by_id[card["id"]] = merged
    issues_by_number = {issue.get("issue_number"): issue for issue in issues}
    for reply in replies:
        issue = issues_by_number.get(reply.get("issue_number"))
        card = by_id.get(reply.get("card_id"))
        if not issue or not card or issue.get("card_id") != reply.get("card_id"):
            continue
        number = issue["issue_number"]
        user_created = issue.get("created_at") or now or utc_now()
        if not user_created.endswith("Z") and "+" not in user_created:
            user_created = user_created + "Z"
        comments = [
            {"id": f"issue-{number}-user", "author": "USER",
             "body_markdown": str(issue["user_comment"]), "created_at": user_created,
             "unread": False, "issue_number": number},
            {"id": f"issue-{number}-reply", "author": "CODEX",
             "body_markdown": reply["body_markdown"], "created_at": now or utc_now(),
             "unread": True, "issue_number": number},
        ]
        card["comments"] = _merge_comments(card.get("comments", []), comments)
    protected = {issue.get("card_id") for issue in issues}
    protected.update(card.get("parent_card_id") for card in by_id.values() if card.get("parent_card_id"))
    retained = retain_cards(list(by_id.values()), now=now, protected_ids=protected)
    cards = sorted(retained, key=lambda card: (card["id"] in protected, _activity_timestamp(card), card["created_at"], card["id"]),
                   reverse=True)[:cap]
    feed = {"last_updated": now or utc_now(),
            "calendar_mode": calendar.get("calendar_mode", "BASELINE"),
            "active_exam_course": calendar.get("active_exam_course"), "cards": cards}
    return validate_feed(feed)


def atomic_write(path: Path, value: dict[str, Any]) -> None:
    """Write a schema-validated JSON value via same-directory atomic replace."""
    validate_feed(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    except Exception:
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise


def run(*, feed_path: str | Path = FEED_PATH, dry_run: bool = False,
        output_path: str | Path | None = None, offline: bool | None = None,
        generator: str = "none") -> dict[str, Any]:
    """Run pipeline. Dry-run is strictly offline and does not mutate feed_path."""
    if generator not in {"none", "codex"}:
        raise ValueError("generator must be 'none' or 'codex'")
    feed_path = Path(feed_path)
    existing = _load_feed(feed_path)
    if dry_run:
        if output_path and Path(output_path).resolve() == feed_path.resolve():
            raise ValueError("--dry-run --output must not point at the committed feed path")
        calendar = {"calendar_mode": existing["calendar_mode"],
                    "active_exam_course": existing["active_exam_course"]}
        result = merge_feed(existing, new_cards=[], replies=[], issues=[], calendar=calendar)
        if output_path:
            atomic_write(Path(output_path), result)
        return result
    calendar = get_calendar_state()
    rss = ingest_all()
    for source_name, status in rss["sources"].items():
        if status.get("error"):
            print(f"RSS source {source_name} unavailable: {status['error']}", file=sys.stderr)
    # New RSS IDs and generated IDs are merged without mutating/replacing comments.
    try:
        result = (generate_batch(calendar=calendar, target_course=calendar.get("active_exam_course"),
                                 existing_cards=existing["cards"]) if generator == "codex" else
                  {"comment_replies": [], "new_cards": [], "_issues": []})
    except Exception as exc:
        # Do not lose successfully ingested RSS just because an LLM request or
        # response validation failed. No automatic retry is made.
        print(f"structured generation unavailable: {type(exc).__name__}", file=sys.stderr)
        result = {"comment_replies": [], "new_cards": [], "_issues": []}
    issues = result.pop("_issues", [])
    if generator == "none" and os.getenv("GITHUB_TOKEN") and os.getenv("GITHUB_REPOSITORY"):
        # Protect queued question parents while the desktop runner is asleep.
        try:
            try:
                from .generate_batch import fetch_pending_issues
            except ImportError:
                from generate_batch import fetch_pending_issues
            issues = fetch_pending_issues()
        except Exception:
            print("Pending-question check unavailable; retaining existing cards this run", file=sys.stderr)
            issues = [{"card_id": card["id"]} for card in existing["cards"]]
    # Stock the feed independently of study-generation targets. Previously only
    # 3–4 headlines survived each refresh, often all from sports sources.
    fresh_rss = retain_cards(rss["cards"])
    sports_cards = select_rss_mix([card for card in fresh_rss if card["category"] == "SPORTS"], 40)
    news_cards = select_rss_mix([card for card in fresh_rss if card["category"] == "NEWS"], 40)
    story_cards = select_rss_mix([card for card in fresh_rss if card["category"] == "STORY"], 20)
    feed = merge_feed(existing, new_cards=sports_cards + news_cards + story_cards + result["new_cards"],
                      replies=result["comment_replies"], issues=issues, calendar=calendar)
    atomic_write(Path(output_path) if output_path else feed_path, feed)
    return feed


def _remote_feed_matches(feed_path: Path, repository: str, token: str, timeout: float = 10) -> bool:
    """Require this feed byte-for-byte on the remote default branch before resolving."""
    import requests
    url = f"https://api.github.com/repos/{repository}/contents/docs/data/feed.json"
    response = requests.get(url, headers=_github_headers(token), timeout=timeout)
    response.raise_for_status()
    remote = response.json()
    if remote.get("encoding") != "base64" or not remote.get("content"):
        return False
    content = base64.b64decode(remote["content"].replace("\n", ""))
    return content == feed_path.read_bytes()


def resolve_only(*, feed_path: str | Path = FEED_PATH, repository: str | None = None,
                 token: str | None = None, timeout: float = 10) -> dict[str, Any]:
    """Idempotently post represented replies and close their GitHub Issues.

    Checks the remote default-branch feed bytes first. A failed comment or close
    remains retryable: a marker in existing issue comments prevents duplicate posts.
    """
    feed_path = Path(feed_path)
    feed = _load_feed(feed_path)
    repository = repository or os.getenv("GITHUB_REPOSITORY", "")
    token = token or os.getenv("GITHUB_TOKEN", "")
    if not repository or not token:
        return {"resolved": [], "skipped": "GITHUB_REPOSITORY and GITHUB_TOKEN are required"}
    if not _remote_feed_matches(feed_path, repository, token, timeout):
        return {"resolved": [], "skipped": "local feed is not yet present on the remote default branch"}
    import requests
    headers = _github_headers(token)
    root = f"https://api.github.com/repos/{repository}/issues"
    candidates: dict[int, tuple[dict[str, Any], dict[str, Any]]] = {}
    for card in feed["cards"]:
        comments = {comment["id"]: comment for comment in card["comments"]}
        for comment in card["comments"]:
            number = comment.get("issue_number")
            if (comment["author"] == "CODEX" and comment["id"] == f"issue-{number}-reply"
                    and isinstance(number, int) and number > 0
                    and f"issue-{number}-user" in comments):
                candidates[number] = (card, comment)
    completed = []
    for number, (card, reply) in sorted(candidates.items()):
        issue_url = f"{root}/{number}"
        try:
            comments_url = f"{issue_url}/comments"
            remote_comments: list[dict[str, Any]] = []
            page = 1
            while True:
                response = requests.get(comments_url, headers=headers,
                                        params={"per_page": 100, "page": page}, timeout=timeout)
                response.raise_for_status()
                batch = response.json()
                remote_comments.extend(batch)
                if len(batch) < 100:
                    break
                page += 1
            marker = f"<!-- scrollforge:issue-{number} -->"
            if not any(marker in str(comment.get("body", "")) for comment in remote_comments):
                body = f"{reply['body_markdown']}\n\n{marker}"
                response = requests.post(comments_url, headers=headers, json={"body": body}, timeout=timeout)
                response.raise_for_status()
            response = requests.get(issue_url, headers=headers, timeout=timeout)
            response.raise_for_status()
            issue = response.json()
            if issue.get("state") != "closed":
                response = requests.patch(issue_url, headers=headers,
                                          json={"state": "closed", "state_reason": "completed"}, timeout=timeout)
                response.raise_for_status()
            completed.append(number)
        except Exception as exc:
            print(f"issue #{number} resolution failed: {type(exc).__name__}: {str(exc)[:160]}", file=sys.stderr)
    return {"resolved": completed, "skipped": None}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="offline preview; no feeds, calendar, LLM, or GitHub calls")
    parser.add_argument("--resolve-only", action="store_true", help="post/close replies already embedded in the remote feed")
    parser.add_argument("--output", type=Path, help="write generated/preview feed to a separate path")
    parser.add_argument("--generator", choices=["none", "codex"], default="none",
                        help="RSS only by default; codex uses the local ChatGPT CLI login")
    parser.add_argument("--feed", type=Path, default=FEED_PATH, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.resolve_only and args.dry_run:
        parser.error("--resolve-only and --dry-run cannot be combined")
    if args.resolve_only:
        if args.output:
            parser.error("--output cannot be used with --resolve-only")
        result = resolve_only(feed_path=args.feed)
    else:
        result = run(feed_path=args.feed, dry_run=args.dry_run, output_path=args.output, generator=args.generator)
    # ASCII escapes keep CLI output valid JSON on Windows legacy consoles too.
    print(json.dumps(result, ensure_ascii=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
