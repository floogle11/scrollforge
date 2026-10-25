import json
import subprocess
from datetime import datetime, timedelta, timezone

import pytest

from worker import local_loop, run_pipeline


def _root(tmp_path):
    feed_path = tmp_path / "docs" / "data" / "feed.json"
    feed_path.parent.mkdir(parents=True)
    feed_path.write_text("{}", encoding="utf-8")
    return tmp_path


def _parent():
    return {"id": "card-1", "category": "DEEP_CUT", "course_tag": "ME-101", "title": "Card",
            "body_markdown": "Body", "solution_markdown": "", "created_at": "2026-10-20T00:00:00Z",
            "comments": []}


def _base(monkeypatch, root, issues=None):
    monkeypatch.setattr(local_loop, "_pull_latest", lambda _root: None)
    monkeypatch.setattr(local_loop, "_repository", lambda _root: "owner/repo")
    monkeypatch.setattr(local_loop, "_github_token", lambda: "token")
    monkeypatch.setattr(local_loop, "fetch_pending_issues", lambda *a, **k: issues or [])
    monkeypatch.setattr(local_loop, "resolve_only", lambda **_kwargs: {"resolved": []})
    monkeypatch.setattr(local_loop, "get_calendar_state", lambda: {"calendar_mode": "BASELINE",
        "active_exam_course": None, "weights": {"current_coursework": 0.3, "past_coursework": 0.2,
        "sports_news": 0.3, "reddit_stories": 0.2}, "events": []})
    monkeypatch.setattr(run_pipeline, "_load_feed", lambda _path: {"cards": [_parent()],
        "calendar_mode": "BASELINE", "active_exam_course": None})


def test_dry_run_does_not_fetch_or_mutate(monkeypatch, tmp_path):
    root = _root(tmp_path)
    state_path = root / ".cache/local-agent/state.json"
    monkeypatch.setattr(local_loop, "ROOT", root)
    monkeypatch.setattr(local_loop.subprocess, "run", lambda *_a, **_k: pytest.fail("subprocess called"))
    result = local_loop.run_cycle(root=root, dry_run=True, publish=True)
    assert result == {"dry_run": True, "cards": 0, "external_calls": 0}
    assert not state_path.exists()


def test_idle_scheduler_tick_makes_no_model_call(monkeypatch, tmp_path):
    root = _root(tmp_path)
    now = datetime(2026, 10, 24, 12, tzinfo=timezone.utc)
    state_path = root / ".cache/local-agent/state.json"
    state_path.parent.mkdir(parents=True)
    state_path.write_text(json.dumps({"generation_attempts": [(now - timedelta(hours=2)).isoformat()]}), encoding="utf-8")
    _base(monkeypatch, root)
    monkeypatch.setattr(local_loop, "generate_batch", lambda **_kwargs: pytest.fail("model called while idle"))
    result = local_loop.run_cycle(root=root, now=now)
    assert result["idle"] is True
    assert result["pending_questions"] == 0


def test_idle_tick_retries_resolving_durable_replies(monkeypatch, tmp_path):
    root = _root(tmp_path)
    now = datetime(2026, 10, 24, 12, tzinfo=timezone.utc)
    state_path = root / ".cache/local-agent/state.json"
    state_path.parent.mkdir(parents=True)
    state_path.write_text(json.dumps({"generation_attempts": [(now - timedelta(hours=2)).isoformat()]}), encoding="utf-8")
    card = _parent()
    card["comments"] = [{"id": "issue-15-user", "author": "USER", "body_markdown": "Why?",
                         "created_at": "2026-10-24T10:00:00Z", "unread": False, "issue_number": 15},
                        {"id": "issue-15-reply", "author": "CODEX", "body_markdown": "Answer.",
                         "created_at": "2026-10-24T11:00:00Z", "unread": True, "issue_number": 15}]
    _base(monkeypatch, root)
    monkeypatch.setattr(run_pipeline, "_load_feed", lambda _path: {"cards": [card],
        "calendar_mode": "BASELINE", "active_exam_course": None})
    resolved = []
    monkeypatch.setattr(local_loop, "resolve_only", lambda **_kw: resolved.append(True) or {"resolved": [15]})
    result = local_loop.run_cycle(root=root, now=now)
    assert result["idle"] is True
    assert result["resolved"] == [15]
    assert resolved == [True]


def test_comment_only_cycle_never_requests_engineering_cards(monkeypatch, tmp_path):
    root = _root(tmp_path)
    now = datetime(2026, 10, 24, 12, tzinfo=timezone.utc)
    issue = {"issue_number": 15, "card_id": "card-1", "course_tag": "ME-101",
             "user_comment": "Why?", "created_at": "2026-10-24T11:00:00Z"}
    _base(monkeypatch, root, [issue])
    observed = {}

    def generate(**kwargs):
        observed.update(kwargs)
        return {"comment_replies": [], "new_cards": [], "_issues": [issue]}

    monkeypatch.setattr(local_loop, "generate_batch", generate)
    monkeypatch.setattr(local_loop, "merge_feed", lambda *a, **kw: {"cards": [_parent()]})
    result = local_loop.run_cycle(root=root, now=now)
    assert result["pending_questions"] == 1
    assert observed["generate_new_cards"] is False
    assert observed["counts_override"] == {"current_coursework": 0, "past_coursework": 0}


def test_scheduled_generation_is_limited_to_twenty_cards(monkeypatch, tmp_path):
    root = _root(tmp_path)
    now = datetime(2026, 10, 24, 12, tzinfo=timezone.utc)
    _base(monkeypatch, root)
    observed = {}
    card = {**_parent(), "id": "generated-card"}

    def generate(**kwargs):
        observed.update(kwargs)
        return {"comment_replies": [], "new_cards": [card], "_issues": []}

    monkeypatch.setattr(local_loop, "generate_batch", generate)
    monkeypatch.setattr(local_loop, "merge_feed", lambda *a, **kw: {"cards": [card]})
    result = local_loop.run_cycle(root=root, now=now)
    assert result["generated_cards"] == 1
    assert observed["generate_new_cards"] is True
    assert sum(observed["counts_override"].values()) == 20
    state = json.loads((root / ".cache/local-agent/state.json").read_text(encoding="utf-8"))
    assert len(state["generation_attempts"]) == 1
    assert "last_generation" not in state  # No feed push occurred.


def test_generated_batch_merges_after_second_fast_forward(monkeypatch, tmp_path):
    root = _root(tmp_path)
    now = datetime(2026, 10, 24, 12, tzinfo=timezone.utc)
    _base(monkeypatch, root)
    pull_count = []
    monkeypatch.setattr(local_loop, "_pull_latest", lambda _root: pull_count.append(True))
    feed_versions = [
        {"cards": [_parent()], "calendar_mode": "BASELINE", "active_exam_course": None},
        {"cards": [{**_parent(), "id": "latest-remote-card"}],
         "calendar_mode": "BASELINE", "active_exam_course": None},
    ]
    monkeypatch.setattr(run_pipeline, "_load_feed", lambda _path: feed_versions.pop(0))
    card = {**_parent(), "id": "generated-card"}
    monkeypatch.setattr(local_loop, "generate_batch", lambda **_kw: {
        "comment_replies": [], "new_cards": [card], "_issues": []})
    merged = {}

    def merge(existing, **_kwargs):
        merged["existing"] = existing
        return {"cards": [card]}

    monkeypatch.setattr(local_loop, "merge_feed", merge)
    monkeypatch.setattr(local_loop, "atomic_write", lambda *_a, **_kw: None)
    monkeypatch.setattr(local_loop, "_push_feed", lambda _root: None)
    result = local_loop.run_cycle(root=root, now=now, publish=True)
    assert result["published"] is True
    assert len(pull_count) == 2
    assert merged["existing"]["cards"][0]["id"] == "latest-remote-card"


def test_failed_push_never_resolves_issues_or_records_last_generation(monkeypatch, tmp_path):
    root = _root(tmp_path)
    now = datetime(2026, 10, 24, 12, tzinfo=timezone.utc)
    _base(monkeypatch, root)
    card = {**_parent(), "id": "generated-card"}
    monkeypatch.setattr(local_loop, "generate_batch", lambda **_kw: {
        "comment_replies": [], "new_cards": [card], "_issues": []})
    monkeypatch.setattr(local_loop, "merge_feed", lambda *a, **kw: {"cards": [card]})
    monkeypatch.setattr(local_loop, "atomic_write", lambda *_a, **_kw: None)
    monkeypatch.setattr(local_loop, "_push_feed", lambda _root: (_ for _ in ()).throw(RuntimeError("push failed")))
    monkeypatch.setattr(local_loop, "resolve_only", lambda **_kw: pytest.fail("resolved before push"))
    with pytest.raises(RuntimeError, match="push failed"):
        local_loop.run_cycle(root=root, now=now, publish=True)
    state = json.loads((root / ".cache/local-agent/state.json").read_text(encoding="utf-8"))
    assert "last_generation" not in state
    outbox = root / ".cache/local-agent/outbox.json"
    assert outbox.exists()

    # The next tick publishes the cached batch without spending another model turn.
    monkeypatch.setattr(local_loop, "generate_batch", lambda **_kw: pytest.fail("model reran on retry"))
    monkeypatch.setattr(local_loop, "_push_feed", lambda _root: None)
    monkeypatch.setattr(local_loop, "resolve_only", lambda **_kw: {"resolved": []})
    result = local_loop.run_cycle(root=root, now=now + timedelta(minutes=5), publish=True)
    assert result["published"] is True
    assert not outbox.exists()
    state = json.loads((root / ".cache/local-agent/state.json").read_text(encoding="utf-8"))
    assert state["last_generation"] == now.isoformat(timespec="seconds").replace("+00:00", "Z")


def _git(git, cwd, *args):
    result = subprocess.run([git, *args], cwd=cwd, text=True, capture_output=True,
                            encoding="utf-8", errors="replace")
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


def _git_race_repos(tmp_path):
    git = local_loop._resolve_cli("GIT_BIN", "git")
    remote = tmp_path / "origin.git"
    seed = tmp_path / "seed"
    _git(git, tmp_path, "init", "--bare", str(remote))
    _git(git, tmp_path, "clone", str(remote), str(seed))
    _git(git, seed, "config", "user.name", "ScrollForge Test")
    _git(git, seed, "config", "user.email", "scrollforge-test@example.invalid")
    (seed / "docs/data").mkdir(parents=True)
    (seed / "docs/data/feed.json").write_text("{\"version\": 1}\n", encoding="utf-8")
    (seed / "docs/data/feed-meta.json").write_text("{\"version\": 1}\n", encoding="utf-8")
    (seed / "README.md").write_text("base\n", encoding="utf-8")
    (seed / ".gitignore").write_text(".cache/\n", encoding="utf-8")
    _git(git, seed, "add", "--", "docs/data/feed.json", "docs/data/feed-meta.json", "README.md", ".gitignore")
    _git(git, seed, "commit", "-m", "Initial content")
    _git(git, seed, "branch", "-M", "main")
    _git(git, seed, "push", "-u", "origin", "main")
    _git(git, remote, "symbolic-ref", "HEAD", "refs/heads/main")
    remote_clone = tmp_path / "other-agent"
    local_clone = tmp_path / ".cache" / "local-agent" / "checkout"
    local_clone.parent.mkdir(parents=True)
    _git(git, tmp_path, "clone", str(remote), str(remote_clone))
    _git(git, tmp_path, "clone", str(remote), str(local_clone))
    for clone in (remote_clone, local_clone):
        _git(git, clone, "config", "user.name", "ScrollForge Test")
        _git(git, clone, "config", "user.email", "scrollforge-test@example.invalid")
    return git, remote_clone, local_clone


def test_git_fast_forward_race_recovers_cached_feed_commit(tmp_path, monkeypatch):
    git, other, local = _git_race_repos(tmp_path)
    monkeypatch.setenv("GIT_BIN", git)
    (local / ".cache/local-agent").mkdir(parents=True)
    (local / ".cache/local-agent/outbox.json").write_text('{"output": {"new_cards": []}}', encoding="utf-8")
    (local / "docs/data/feed.json").write_text("{\"local_agent_batch\": true}\n", encoding="utf-8")
    (local / "docs/data/feed-meta.json").write_text("{\"local_agent_batch\": true}\n", encoding="utf-8")
    _git(git, local, "add", "--", "docs/data/feed.json", "docs/data/feed-meta.json")
    _git(git, local, "commit", "-m", "Update ScrollForge feed")

    (other / "README.md").write_text("remote RSS update\n", encoding="utf-8")
    _git(git, other, "commit", "-am", "Refresh RSS feed")
    _git(git, other, "push")
    latest = _git(git, other, "rev-parse", "HEAD")
    local_loop._pull_latest(local)
    assert _git(git, local, "rev-parse", "HEAD") == latest
    assert (local / "README.md").read_text(encoding="utf-8") == "remote RSS update\n"
    assert (local / "docs/data/feed.json").read_text(encoding="utf-8") == "{\"version\": 1}\n"
    assert (local / "docs/data/feed-meta.json").read_text(encoding="utf-8") == "{\"version\": 1}\n"
    assert (local / ".cache/local-agent/outbox.json").is_file()


def test_precommit_feed_crash_restores_only_cached_feed_path(tmp_path, monkeypatch):
    git, _other, local = _git_race_repos(tmp_path)
    monkeypatch.setenv("GIT_BIN", git)
    (local / ".cache/local-agent").mkdir(parents=True)
    (local / ".cache/local-agent/outbox.json").write_text('{"output": {"new_cards": []}}', encoding="utf-8")
    (local / "docs/data/feed.json").write_text("{\"partial_write\": true}\n", encoding="utf-8")
    (local / "docs/data/feed-meta.json").write_text("{\"partial_write\": true}\n", encoding="utf-8")
    local_loop._pull_latest(local)
    assert (local / "docs/data/feed.json").read_text(encoding="utf-8") == "{\"version\": 1}\n"
    assert (local / ".cache/local-agent/outbox.json").is_file()
