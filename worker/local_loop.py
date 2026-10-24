"""Scheduled local Codex generation and durable GitHub publication.

The Windows task launcher runs this module from a dedicated clone. This module
never writes into the user's working checkout and resolves issues only after
the feed commit has been pushed.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

try:
    from .calendar_weights import get_calendar_state, target_card_counts
    from .generate_batch import fetch_pending_issues, generate_batch
    from .run_pipeline import merge_feed, resolve_only, atomic_write
except ImportError:  # pragma: no cover
    from calendar_weights import get_calendar_state, target_card_counts
    from generate_batch import fetch_pending_issues, generate_batch
    from run_pipeline import merge_feed, resolve_only, atomic_write

ROOT = Path(__file__).resolve().parents[1]
STATE_PATH = ROOT / ".cache" / "local-agent" / "state.json"
OUTBOX_PATH = ROOT / ".cache" / "local-agent" / "outbox.json"
INTERVAL_SECONDS = 300
MAX_ISSUES = 20
MAX_CARDS = 6
MIN_GENERATION_GAP = timedelta(hours=12)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _stamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _parse_stamp(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


def _load_state(path: Path = STATE_PATH) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _save_state(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def _resolve_cli(name: str, fallback: str) -> str:
    configured = os.getenv(name)
    if configured:
        return configured
    import shutil
    found = shutil.which(fallback)
    if found:
        return found
    if os.name == "nt":
        known = Path(os.getenv("ProgramFiles", "C:/Program Files")) / "Git" / "cmd" / f"{fallback}.exe"
        if known.is_file():
            return str(known)
        if fallback == "gh":
            known = Path("C:/Program Files/GitHub CLI/gh.exe")
            if known.is_file():
                return str(known)
    return fallback


def _run(args: list[str], *, cwd: Path = ROOT, timeout: int = 60,
         input_text: str | None = None) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    for secret_name in ("OPENAI_API_KEY", "CODEX_API_KEY", "GITHUB_TOKEN", "GH_TOKEN"):
        env.pop(secret_name, None)
    result = subprocess.run(args, cwd=cwd, input=input_text, text=True, capture_output=True,
                            timeout=timeout, env=env, check=False, encoding="utf-8", errors="replace")
    if result.returncode:
        # Never include command output: it can contain repository or credential data.
        raise RuntimeError(f"{Path(args[0]).name} failed (exit {result.returncode})")
    return result


def _repository(root: Path) -> str:
    configured = os.getenv("GITHUB_REPOSITORY", "").strip()
    if configured:
        return configured
    git = _resolve_cli("GIT_BIN", "git")
    remote = _run([git, "config", "--get", "remote.origin.url"], cwd=root).stdout.strip()
    match = re.search(r"(?:github\.com[:/])([^/\s]+/[^/\s]+?)(?:\.git)?$", remote, re.I)
    if not match:
        raise RuntimeError("could not determine GitHub repository from origin")
    return match.group(1)


def _github_token() -> str:
    gh = _resolve_cli("GH_BIN", "gh")
    token = _run([gh, "auth", "token"], timeout=20).stdout.strip()
    if not token:
        raise RuntimeError("gh auth token returned no token")
    return token


def _new_questions(issues: list[dict[str, Any]], cards: list[dict[str, Any]]) -> list[dict[str, Any]]:
    replied = {comment.get("issue_number") for card in cards for comment in card.get("comments", [])
               if comment.get("author") == "CODEX"
               and comment.get("id") == f"issue-{comment.get('issue_number')}-reply"}
    card_ids = {card.get("id") for card in cards}
    return [issue for issue in issues if issue.get("issue_number") not in replied
            and issue.get("card_id") in card_ids][:MAX_ISSUES]


def _generation_due(state: dict[str, Any], now: datetime) -> bool:
    attempts = [_parse_stamp(value) for value in state.get("generation_attempts", [])]
    recent = [value for value in attempts if value and now - value < timedelta(hours=24)]
    last = max(recent, default=None)
    return len(recent) < 2 and (last is None or now - last >= MIN_GENERATION_GAP)


def _pull_latest(root: Path) -> None:
    owned_clone = root.name == "checkout" and root.parent.name == "local-agent" and root.parent.parent.name == ".cache"
    git = _resolve_cli("GIT_BIN", "git")
    _run([git, "fetch", "--prune"], cwd=root, timeout=120)
    upstream = _run([git, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}"], cwd=root).stdout.strip()
    counts = _run([git, "rev-list", "--left-right", "--count", f"{upstream}...HEAD"], cwd=root).stdout.split()
    if len(counts) != 2:
        raise RuntimeError("could not compare the isolated checkout with its upstream")
    behind, ahead = map(int, counts)
    status = _run([git, "status", "--porcelain"], cwd=root).stdout.splitlines()
    if status:
        changed = [line[3:] for line in status if len(line) >= 4]
        has_outbox = (root / ".cache/local-agent/outbox.json").is_file()
        if changed != ["docs/data/feed.json"] or not has_outbox or not owned_clone:
            raise RuntimeError("isolated checkout has uncommitted work; refusing to overwrite it")
        # A crash between writing feed.json and committing it is recoverable:
        # the batch was atomically cached first, and only this owned clone's feed
        # path may be restored. Any unrelated working changes still stop here.
        _run([git, "restore", "--source=HEAD", "--staged", "--worktree", "--", "docs/data/feed.json"],
             cwd=root, timeout=60)
        status = _run([git, "status", "--porcelain"], cwd=root).stdout.splitlines()
        if status:
            raise RuntimeError("isolated checkout still has uncommitted work after feed recovery")
    if behind and ahead:
        merge_base = _run([git, "merge-base", upstream, "HEAD"], cwd=root).stdout.strip()
        paths = _run([git, "diff", "--name-only", f"{merge_base}..HEAD"], cwd=root).stdout.splitlines()
        messages = _run([git, "log", "--format=%s", f"{upstream}..HEAD"], cwd=root).stdout.splitlines()
        if (not owned_clone or paths != ["docs/data/feed.json"] or not messages
                or any(message != "Update ScrollForge feed" for message in messages)
                or not (root / ".cache/local-agent/outbox.json").is_file()):
            raise RuntimeError("diverged local history is not a recoverable cached feed publication")
        # The dedicated clone contains only our feed commits. The outbox stores
        # the generated batch before publication, so replay it over the newly
        # fetched feed rather than losing generated work or another user's data.
        _run([git, "reset", "--hard", upstream], cwd=root, timeout=60)
    elif behind:
        _run([git, "merge", "--ff-only", upstream], cwd=root, timeout=120)


def _push_feed(root: Path) -> None:
    git = _resolve_cli("GIT_BIN", "git")
    status = _run([git, "status", "--porcelain"], cwd=root).stdout.splitlines()
    if any(not line.endswith("docs/data/feed.json") for line in status):
        raise RuntimeError("isolated checkout contains unexpected changes")
    _run([git, "add", "--", "docs/data/feed.json"], cwd=root)
    staged = _run([git, "diff", "--cached", "--name-only"], cwd=root).stdout.splitlines()
    if staged != ["docs/data/feed.json"]:
        raise RuntimeError("refusing to publish files outside docs/data/feed.json")
    _run([git, "commit", "-m", "Update ScrollForge feed"], cwd=root, timeout=60)
    _run([git, "push"], cwd=root, timeout=120)


def _load_outbox(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) and isinstance(value.get("output"), dict) else None
    except (OSError, json.JSONDecodeError):
        return None


def _save_outbox(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def _merge_issues(*groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_number: dict[int, dict[str, Any]] = {}
    for group in groups:
        for issue in group:
            if isinstance(issue.get("issue_number"), int):
                by_number[issue["issue_number"]] = issue
    return list(by_number.values())


def run_cycle(*, root: Path = ROOT, dry_run: bool = False, publish: bool = False,
              now: datetime | None = None) -> dict[str, Any]:
    """Run one scheduler tick; injectable root/time keep scheduling testable."""
    root = Path(root).resolve()
    feed_path = root / "docs" / "data" / "feed.json"
    state_path = root / ".cache" / "local-agent" / "state.json"
    if dry_run:
        feed = json.loads(feed_path.read_text(encoding="utf-8"))
        return {"dry_run": True, "cards": len(feed.get("cards", [])), "external_calls": 0}

    current = (now or _utc_now()).astimezone(timezone.utc)
    # All automated runs are expected to be launched from the dedicated clone.
    # Fast-forward first so subsequent work merges against the newest feed.
    _pull_latest(root)
    repository = _repository(root)
    token = _github_token()
    # Local clone imports resolve the matching project modules after sys.path prep.
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    from worker.run_pipeline import _load_feed

    existing = _load_feed(feed_path)
    issues = fetch_pending_issues(repository, token, max_issues=MAX_ISSUES)
    questions = _new_questions(issues, existing["cards"])
    state = _load_state(state_path)
    outbox_path = root / ".cache" / "local-agent" / "outbox.json"
    outbox = _load_outbox(outbox_path)
    if outbox:
        output = outbox["output"]
        scheduled_generation = bool(outbox.get("scheduled_generation"))
        generated_at = _parse_stamp(outbox.get("created_at")) or current
        issues = _merge_issues(issues, outbox.get("issues", []))
    else:
        scheduled_generation = not questions and _generation_due(state, current)
        if not questions and not scheduled_generation:
            # Retries previously embedded replies after a transient GitHub post/close failure.
            resolved = resolve_only(feed_path=feed_path, repository=repository, token=token)
            return {"idle": True, "pending_questions": 0, "generated_cards": 0,
                    "resolved": resolved.get("resolved", [])}

        calendar = get_calendar_state()
        if questions:
            counts = {"current_coursework": 0, "past_coursework": 0}
        else:
            targets = target_card_counts(calendar.get("weights"))
            current_count, past_count = targets["current_coursework"], targets["past_coursework"]
            total = min(MAX_CARDS, current_count + past_count)
            if current_count + past_count > total:
                current_count = round(total * current_count / (current_count + past_count))
                past_count = total - current_count
            counts = {"current_coursework": current_count, "past_coursework": past_count}

        if scheduled_generation:
            attempts = [_parse_stamp(value) for value in state.get("generation_attempts", [])]
            state["generation_attempts"] = [_stamp(value) for value in attempts if value
                                            and current - value < timedelta(hours=24)]
            state["generation_attempts"].append(_stamp(current))
            _save_state(state_path, state)

        output = generate_batch(notes_index=root / "docs" / "data" / "notes_index.json",
                                calendar=calendar, target_course=calendar.get("active_exam_course"),
                                issues=questions, repository=repository, github_token=token,
                                existing_cards=existing["cards"], generate_new_cards=bool(scheduled_generation),
                                counts_override=counts)
        generated_at = current
        if not output["new_cards"] and not output["comment_replies"]:
            # An idle model result does not replace an existing unresolved outbox.
            resolved = resolve_only(feed_path=feed_path, repository=repository, token=token)
            return {"idle": True, "pending_questions": len(questions), "generated_cards": 0,
                    "resolved": resolved.get("resolved", [])}
        if not publish:
            feed = merge_feed(existing, new_cards=output["new_cards"], replies=output["comment_replies"],
                              issues=issues, calendar=calendar)
            return {"published": False, "pending_questions": len(questions),
                    "generated_cards": len(output["new_cards"]), "feed": feed}
        _save_outbox(outbox_path, {"created_at": _stamp(generated_at),
                                   "scheduled_generation": bool(scheduled_generation),
                                   "issues": issues, "output": output})

        # RSS automation may have advanced the remote feed while the model ran.
        # Refresh now, then merge the cached result with that newest version.
        _pull_latest(root)
        existing = _load_feed(feed_path)

    calendar = get_calendar_state()
    generated = output.get("new_cards", [])
    feed = merge_feed(existing, new_cards=generated, replies=output.get("comment_replies", []),
                      issues=issues, calendar=calendar)
    atomic_write(feed_path, feed)
    _push_feed(root)
    if scheduled_generation and generated:
        state["last_generation"] = _stamp(generated_at)
        _save_state(state_path, state)
    # The feed is durable now. A later idle tick retries issue resolution from it.
    outbox_path.unlink(missing_ok=True)
    resolved = resolve_only(feed_path=feed_path, repository=repository, token=token)
    return {"published": True, "pending_questions": len(questions),
            "generated_cards": len(generated), "resolved": resolved.get("resolved", [])}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--once", action="store_true", help="run one five-minute scheduler tick")
    parser.add_argument("--dry-run", action="store_true", help="inspect local feed only; no network, model, or writes")
    parser.add_argument("--publish", action="store_true", help="commit/push the validated feed and resolve represented issues")
    args = parser.parse_args(argv)
    try:
        if args.once or args.dry_run:
            print(json.dumps(run_cycle(dry_run=args.dry_run, publish=args.publish), ensure_ascii=False))
            return 0
        while True:
            try:
                print(json.dumps(run_cycle(publish=args.publish), ensure_ascii=False))
            except Exception as exc:
                print(f"local loop tick failed: {type(exc).__name__}", file=sys.stderr)
            time.sleep(INTERVAL_SECONDS)
    except Exception as exc:
        print(f"local loop failed: {type(exc).__name__}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
