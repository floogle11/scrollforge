from copy import deepcopy
from datetime import datetime, timezone

from worker.retention import canonical_url, is_fresh, retain_cards
from worker.run_pipeline import merge_feed, run

NOW = "2026-10-24T12:00:00Z"


def card(identity="article", category="NEWS", created="2026-10-23T12:00:00Z", **overrides):
    value = {"id": identity, "category": category, "created_at": created,
             "course_tag": None, "title": "Broncos practice report", "body_markdown": "Report.",
             "solution_markdown": None, "source_url": "https://example.com/report",
             "parent_card_id": None, "comments": []}
    value.update(overrides)
    return value


def test_age_is_publication_based_and_category_specific():
    now = datetime(2026, 10, 24, 12, tzinfo=timezone.utc)
    assert is_fresh(card(created="2026-10-17T12:00:00Z"), now)
    assert not is_fresh(card(created="2026-10-17T11:59:59Z"), now)
    assert is_fresh(card(category="STORY", created="2026-10-01T12:00:00Z"), now)
    assert not is_fresh(card(category="STORY", created="2026-09-01T12:00:00Z"), now)
    assert is_fresh(card(category="CHALLENGE_PAST", created="2020-01-01T00:00:00Z"), now)


def test_old_news_removed_but_threads_and_pending_parents_remain():
    stale = card(created="2026-01-01T00:00:00Z")
    assert retain_cards([stale], now=NOW) == []
    assert retain_cards([stale], now=NOW, protected_ids={stale["id"]}) == [stale]
    threaded = deepcopy(stale)
    threaded["comments"] = [{"id": "reply"}]
    assert retain_cards([threaded], now=NOW) == [threaded]


def test_tracking_urls_and_edited_headlines_preserve_original_seen_identity():
    original = card(identity="already-seen", source_url="https://example.com/report?utm_source=rss#top")
    update = card(identity="new-source-id", source_url="https://EXAMPLE.com/report/", title="Revised headline")
    kept = retain_cards([original, update], now=NOW)
    assert len(kept) == 1
    assert kept[0]["id"] == "already-seen"
    assert canonical_url("https://example.com/report?id=4&utm_campaign=a") == "https://example.com/report?id=4"


def test_rss_refetch_cannot_renew_old_publication_date():
    old = card(created="2026-10-01T00:00:00Z")
    update = card(created="2026-10-24T00:00:00Z")
    feed = {"last_updated": NOW, "calendar_mode": "BASELINE", "active_exam_course": None, "cards": [old]}
    merged = merge_feed(feed, new_cards=[update], replies=[], issues=[],
                        calendar={"calendar_mode": "BASELINE"}, now=NOW)
    assert merged["cards"] == []


def test_normal_cloud_pipeline_never_invokes_codex(monkeypatch, tmp_path):
    import worker.run_pipeline as pipeline
    monkeypatch.setattr(pipeline, "get_calendar_state", lambda: {"calendar_mode": "BASELINE"})
    monkeypatch.setattr(pipeline, "ingest_all", lambda: {"cards": [], "sources": {}})
    calls = []
    def model(**_kwargs):
        calls.append(True)
        raise AssertionError("model invoked")
    monkeypatch.setattr(pipeline, "generate_batch", model)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    result = run(feed_path=tmp_path / "feed.json")
    assert result["cards"] == []
    assert calls == []
