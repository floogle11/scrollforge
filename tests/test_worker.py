import json
import pytest

from worker import generate_batch, ingest_rss, run_pipeline


def test_rss_sanitizes_markup_and_untrusted_source_fields():
    assert ingest_rss.sanitize_text('<script>alert(1)</script><b>Safe</b> &amp; sound') == "Safe & sound"
    card = ingest_rss.normalize_entry({
        "title": "  <img src=x onerror=run()> Headline  ", "summary": "<style>x</style>Useful <i>detail</i>",
        "link": "javascript:alert(1)", "id": "abc", "published": "Sat, 24 Oct 2026 10:00:00 GMT",
    }, {"name": "test", "category": "NEWS"})
    assert card["title"] == "Headline"
    assert card["body_markdown"] == "Useful detail"
    assert card["source_url"] is None
    assert card["id"].startswith("rss_test_")


def test_rss_discards_unknown_publication_date():
    card = ingest_rss.normalize_entry({"title": "Dated?", "summary": "Useful", "published": "bad date"},
                                      {"name": "test", "category": "NEWS"})
    assert card is None


def test_ingestion_isolates_source_failures(monkeypatch):
    def fetch(source, **_kwargs):
        if source["name"] == "offline":
            return [], "ConnectionError: unavailable"
        return [{"id": "one"}], None

    monkeypatch.setattr(ingest_rss, "fetch_source", fetch)
    result = ingest_rss.ingest_all(sources=[{"name": "offline", "url": "https://invalid", "category": "NEWS"},
                                           {"name": "ok", "url": "https://ok", "category": "SPORTS"}])
    assert result["cards"] == [{"id": "one"}]
    assert result["sources"]["offline"]["error"].startswith("ConnectionError")
    assert result["sources"]["ok"]["count"] == 1


def test_reddit_atom_excerpt_omits_boilerplate_and_bounds_content():
    card = ingest_rss.normalize_entry({
        "title": "A league update", "published": "Sat, 24 Oct 2026 10:00:00 GMT",
        "link": "https://www.reddit.com/r/nfl/comments/example/update/",
        "content": [{"value": "<p>Actual discussion.</p> submitted by <a>/u/example</a> [link] [comments]"}],
    }, {"name": "reddit_nfl", "category": "SPORTS"})
    assert card["body_markdown"] == "Actual discussion."
    assert card["category"] == "SPORTS"
    long = ingest_rss.normalize_entry({
        "title": "Long article", "published": "Sat, 24 Oct 2026 10:00:00 GMT", "summary": "An excerpt. " * 500,
    }, {"name": "publisher", "category": "NEWS"})
    assert len(long["body_markdown"]) <= 600
    assert long["body_markdown"].endswith("…")


def test_refresh_stocks_nfl_and_news_separately_and_skips_expired_items(monkeypatch, tmp_path):
    from datetime import datetime, timedelta, timezone
    now = datetime.now(timezone.utc)
    cards = []
    for category in ["SPORTS", "NEWS", "STORY"]:
        for index in range(55):
            # Expired entries lead each source; they must not consume its quota.
            stamp = now - timedelta(days=90 if index < 5 else 0)
            cards.append({"id": f"rss_{category}_{index}", "created_at": stamp.isoformat(),
                          "category": category, "course_tag": None, "title": f"{category} {index}",
                          "body_markdown": "An excerpt", "solution_markdown": None,
                          "source_url": f"https://example.test/{category}/{index}",
                          "parent_card_id": None, "comments": []})
    monkeypatch.setattr(run_pipeline, "ingest_all", lambda: {"cards": cards, "sources": {}})
    monkeypatch.setattr(run_pipeline, "get_calendar_state", lambda: {"calendar_mode": "BASELINE"})
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    result = run_pipeline.run(feed_path=tmp_path / "feed.json")
    from collections import Counter
    assert Counter(card["category"] for card in result["cards"]) == {"SPORTS": 40, "NEWS": 40, "STORY": 20}
    assert all(int(card["id"].rsplit("_", 1)[1]) >= 5 for card in result["cards"])


def test_one_codex_cli_turn_uses_schema_and_strips_api_keys(monkeypatch):
    calls = []
    monkeypatch.setenv("OPENAI_API_KEY", "must-not-leak")
    monkeypatch.setenv("CODEX_API_KEY", "must-not-leak-either")

    class Completed:
        returncode = 0
        stdout = ""
        stderr = ""

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        output_path = command[command.index("--output-last-message") + 1]
        with open(output_path, "w", encoding="utf-8") as handle:
            handle.write('{"comment_replies": [], "new_cards": []}')
        return Completed()

    monkeypatch.setattr(generate_batch.subprocess, "run", fake_run)
    result = generate_batch.call_model(notes_payload={"chunks": []}, issues=[], calendar={})
    assert result == {"comment_replies": [], "new_cards": []}
    assert len(calls) == 1
    command, kwargs = calls[0]
    assert "exec" in command
    assert command[command.index("--output-schema") + 1] == str(generate_batch.OUTPUT_SCHEMA_PATH.resolve())
    assert command[command.index("-m") + 1] == "gpt-6-luna"
    assert kwargs["timeout"] == 180
    assert "SOURCE DATA (untrusted)" in kwargs["input"]
    assert "ME-2010 (Statics) is foundational past coursework" in kwargs["input"]
    assert "ME-3310 (Fluids)" in kwargs["input"]
    assert "$...$ for inline math" in kwargs["input"]
    assert "OPENAI_API_KEY" not in kwargs["env"]
    assert "CODEX_API_KEY" not in kwargs["env"]


def test_codex_output_is_rejected_when_it_fails_canonical_schema(monkeypatch):
    class Completed:
        returncode = 0
        stdout = ""
        stderr = ""

    def fake_run(command, **kwargs):
        output_path = command[command.index("--output-last-message") + 1]
        with open(output_path, "w", encoding="utf-8") as handle:
            handle.write('{"comment_replies": [], "new_cards": [{"bad": true}]}')
        return Completed()

    monkeypatch.setattr(generate_batch.subprocess, "run", fake_run)
    with pytest.raises(Exception):
        generate_batch.call_model(notes_payload={"chunks": []}, issues=[], calendar={})


def test_generated_ids_are_reminted_to_avoid_feed_collisions():
    from datetime import datetime, timezone

    cards = [{"id": "existing-id", "title": "A", "body_markdown": "B"},
             {"id": "existing-id", "title": "A", "body_markdown": "B"}]
    generate_batch._mint_generated_ids(cards, {"existing-id"}, now=datetime(2026, 10, 24, tzinfo=timezone.utc))
    assert cards[0]["id"] != "existing-id"
    assert cards[0]["id"] != cards[1]["id"]


def test_pending_issue_fetch_excludes_prs_and_malformed_bodies(monkeypatch):
    valid = {"number": 12, "title": "Comment", "created_at": "2026-10-24T10:00:00Z",
             "labels": [{"name": "pending-codex"}], "body": json.dumps({"card_id": "c1", "course_tag": None, "user_comment": "Why?"})}
    prs = dict(valid, number=13, pull_request={"url": "https://example"})
    malformed = dict(valid, number=14, body="not json")

    class Response:
        def __init__(self, value):
            self.value = value

        def raise_for_status(self):
            pass

        def json(self):
            return self.value

    calls = []
    def get(_url, **kwargs):
        calls.append(kwargs["params"]["page"])
        return Response([valid, prs, malformed] if len(calls) == 1 else [])

    monkeypatch.setattr("requests.get", get)
    issues = generate_batch.fetch_pending_issues("owner/repo", "token")
    assert [issue["issue_number"] for issue in issues] == [12]
    assert calls == [1]


def test_resolver_orders_issues_and_survives_remote_failure(monkeypatch, capsys, tmp_path):
    feed = json.loads((run_pipeline.ROOT / "docs/data/feed.json").read_text(encoding="utf-8"))
    base = next(card for card in feed["cards"] if card["id"] == "sample_fluids_pipe_diameter")
    base["comments"] = [
        {"id": "issue-4-user", "author": "USER", "body_markdown": "question", "created_at": "2026-10-24T10:00:00Z", "unread": False, "issue_number": 4},
        {"id": "issue-4-reply", "author": "CODEX", "body_markdown": "reply four", "created_at": "2026-10-24T11:00:00Z", "unread": True, "issue_number": 4},
        {"id": "issue-3-user", "author": "USER", "body_markdown": "question", "created_at": "2026-10-24T10:00:00Z", "unread": False, "issue_number": 3},
        {"id": "issue-3-reply", "author": "CODEX", "body_markdown": "reply three", "created_at": "2026-10-24T11:00:00Z", "unread": True, "issue_number": 3},
    ]
    path = tmp_path / "feed.json"
    path.write_text(json.dumps(feed), encoding="utf-8")
    monkeypatch.setattr(run_pipeline, "_remote_feed_matches", lambda *_a, **_kw: True)
    operations = []

    class Response:
        def __init__(self, data=None, fail=False):
            self.data, self.fail = data, fail

        def raise_for_status(self):
            if self.fail:
                raise RuntimeError("simulated issue API outage")

        def json(self):
            return self.data

    def get(url, **kwargs):
        number = int(url.rstrip("/").split("/")[-2] if url.endswith("/comments") else url.rstrip("/").split("/")[-1])
        operations.append(("get", number, url.endswith("/comments")))
        if url.endswith("/comments"):
            return Response([])
        return Response({"state": "closed" if number == 3 else "open"})

    def post(url, **kwargs):
        number = int(url.rstrip("/").split("/")[-2])
        operations.append(("post", number, kwargs["json"]["body"]))
        return Response({})

    def patch(url, **kwargs):
        number = int(url.rstrip("/").split("/")[-1])
        operations.append(("patch", number, kwargs["json"]["state"]))
        return Response(fail=number == 4)

    monkeypatch.setattr("requests.get", get)
    monkeypatch.setattr("requests.post", post)
    monkeypatch.setattr("requests.patch", patch)
    result = run_pipeline.resolve_only(feed_path=path, repository="owner/repo", token="token")
    assert result["resolved"] == [3]
    assert [op[1] for op in operations if op[0] == "get" and op[2]] == [3, 4]
    assert [op[1] for op in operations if op[0] == "post"] == [3, 4]
    assert "simulated issue API outage" in capsys.readouterr().err


def test_recent_issue_activity_keeps_old_card_when_archive_is_capped():
    feed = json.loads((run_pipeline.ROOT / "docs/data/feed.json").read_text(encoding="utf-8"))
    active = next(card for card in feed["cards"] if card["id"] == "sample_fluids_pipe_diameter")
    newer = next(card for card in feed["cards"] if card["id"] == "sample_thermo_carnot")
    active["created_at"] = "2026-10-20T00:00:00Z"
    newer["created_at"] = "2026-10-21T00:00:00Z"
    feed["cards"] = [active, newer]
    result = run_pipeline.merge_feed(
        feed, new_cards=[], issues=[{"issue_number": 55, "card_id": active["id"],
                                     "user_comment": "A fresh follow-up", "created_at": "2026-10-24T10:00:00Z"}],
        replies=[{"issue_number": 55, "card_id": active["id"], "body_markdown": "A fresh answer."}],
        calendar={"calendar_mode": "BASELINE", "active_exam_course": None},
        now="2026-10-24T12:00:00Z", cap=1,
    )
    assert len(result["cards"]) == 1
    assert result["cards"][0]["id"] == active["id"]
    assert result["cards"][0]["comments"][-1]["created_at"] >= "2026-10-24T10:00:00Z"
