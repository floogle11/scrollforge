import json
import os
import subprocess
import sys
from pathlib import Path

import jsonschema

ROOT = Path(__file__).resolve().parents[1]
FEED_PATH = ROOT / "docs" / "data" / "feed.json"
INITIAL_FEED_PATH = ROOT / "tests" / "fixtures" / "initial_feed.json"


def read_feed():
    return json.loads(FEED_PATH.read_text(encoding="utf-8"))


def test_seed_feed_matches_contract_and_requested_sample_mix():
    feed = json.loads(INITIAL_FEED_PATH.read_text(encoding="utf-8"))
    schema = json.loads((ROOT / "contracts" / "feed_schema.json").read_text(encoding="utf-8"))
    jsonschema.validate(feed, schema, format_checker=jsonschema.FormatChecker())
    assert len(feed["cards"]) == 15
    categories = [card["category"] for card in feed["cards"]]
    assert {category: categories.count(category) for category in set(categories)} == {
        "SPORTS": 3, "NEWS": 2, "STORY": 3, "CHALLENGE_CURRENT": 4,
        "CHALLENGE_PAST": 2, "DEEP_CUT": 1,
    }
    for card in feed["cards"]:
        if card["category"] in {"SPORTS", "NEWS", "STORY"}:
            assert "sample" in (card["title"] + " " + card["body_markdown"]).lower()
            assert "archive" in (card["title"] + " " + card["body_markdown"]).lower() or card["category"] == "STORY"
        if card["category"] == "CHALLENGE_CURRENT":
            assert len(card["body_markdown"].split()) <= 75
    thread = next(card for card in feed["cards"] if card["comments"])
    assert [comment["author"] for comment in thread["comments"]] == ["USER", "CODEX"]
    assert thread["comments"][1]["unread"] is True
    assert all(comment["issue_number"] is None for comment in thread["comments"])


def test_runtime_feed_remains_contract_valid_after_worker_updates():
    feed = read_feed()
    schema = json.loads((ROOT / "contracts" / "feed_schema.json").read_text(encoding="utf-8"))
    jsonschema.validate(feed, schema, format_checker=jsonschema.FormatChecker())
    ids = [card["id"] for card in feed["cards"]]
    assert len(ids) == len(set(ids))


def test_dry_run_cli_is_offline_and_does_not_mutate_committed_feed(tmp_path):
    before = FEED_PATH.read_bytes()
    env = os.environ.copy()
    env.update({"OPENAI_API_KEY": "must-not-be-used", "ICS_CALENDAR_URL": "https://127.0.0.1:1/not-used",
                "GITHUB_REPOSITORY": "example/unused", "GITHUB_TOKEN": "unused"})
    env["PYTHONIOENCODING"] = "utf-8"
    result = subprocess.run(
        [sys.executable, "-m", "worker.run_pipeline", "--dry-run", "--output", str(tmp_path / "preview.json")],
        cwd=ROOT, env=env, text=True, encoding="utf-8", capture_output=True, timeout=15, check=True,
    )
    expected = {card["id"]: card for card in read_feed()["cards"]}
    assert {card["id"]: card for card in json.loads(result.stdout)["cards"]} == expected
    assert {card["id"]: card for card in json.loads((tmp_path / "preview.json").read_text(encoding="utf-8"))["cards"]} == expected
    assert FEED_PATH.read_bytes() == before


def test_dry_run_guards_committed_feed_path(monkeypatch, tmp_path):
    from worker import run_pipeline

    path = tmp_path / "feed.json"
    feed = read_feed()
    path.write_text(json.dumps(feed), encoding="utf-8")
    try:
        run_pipeline.run(feed_path=path, dry_run=True, output_path=path)
    except ValueError as exc:
        assert "committed feed path" in str(exc)
    else:
        raise AssertionError("dry-run must reject writing to its input feed")
