"""Offline end-to-end smoke: local note index, sampler, and dry-run pipeline."""
import json
import random
from pathlib import Path

from worker.run_pipeline import run
from worker.sampler import build_notes_payload
from scripts.slice_notes import slice_notes


def test_local_notes_to_sampled_batch_and_dry_run(tmp_path):
    raw = tmp_path / "notes"
    raw.mkdir()
    course = raw / "ME-3310_Fluids"
    course.mkdir()
    (course / "fluids.md").write_text(
        "# ME-3310 Fluids\n\n" + "For steady flow, conservation sets the balance. Check dimensions before substitution. " * 90,
        encoding="utf-8",
    )
    (course / "extra.txt").write_text(
        "For pipe systems, head loss depends on flow regime. State assumptions and units. " * 90,
        encoding="utf-8",
    )
    index_path = tmp_path / "notes_index.json"
    index = slice_notes(raw, index_path)
    assert len(index["chunks"]) >= 5
    payload = build_notes_payload(index_path, target_course="ME-3310", token_budget=1000,
                                  rng=random.Random(17))
    same_payload = build_notes_payload(index_path, target_course="ME-3310", token_budget=1000,
                                       rng=random.Random(17))
    assert payload == same_payload
    assert 5 <= len(payload["chunks"]) <= 6
    assert all(chunk["course_tag"] == "ME-3310" for chunk in payload["chunks"])
    assert all(chunk["text"] for chunk in payload["chunks"])

    committed = Path(__file__).resolve().parents[1] / "docs/data/feed.json"
    before = committed.read_bytes()
    preview_path = tmp_path / "preview.json"
    result = run(feed_path=committed, dry_run=True, output_path=preview_path)
    assert json.loads(preview_path.read_text(encoding="utf-8")) == result
    assert committed.read_bytes() == before
