"""Small, course-aware sampler for the pre-sliced local note index."""
from __future__ import annotations

import json
import random
import re
from pathlib import Path
from typing import Any


def load_index(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict) or value.get("version") != 1 or not isinstance(value.get("chunks"), list):
        raise ValueError("notes index must have {version: 1, chunks: [...], sources: {...}} shape")
    return value


def _token_estimate(chunk: dict[str, Any]) -> int:
    text = str(chunk.get("text", ""))
    # Conservative plain-English approximation; avoids requiring a tokenizer.
    return max(1, (len(text) + 3) // 4)


def _excerpt(text: str, budget: int) -> str:
    """Take a deterministic sentence-boundary excerpt within an approximate token cap."""
    char_cap = max(0, budget * 4)
    if len(text) <= char_cap:
        return text
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    out: list[str] = []
    used = 0
    for sentence in sentences:
        addition = len(sentence) + (1 if out else 0)
        if used + addition > char_cap:
            break
        out.append(sentence)
        used += addition
    if out:
        return " ".join(out)
    # Very long first sentence: fall back to a clean word boundary.
    prefix = text[:char_cap]
    if " " in prefix:
        prefix = prefix.rsplit(" ", 1)[0]
    return (prefix or text[:char_cap]).rstrip()


def sample_chunks(index: dict[str, Any] | str | Path, *, target_course: str | None = None,
                  token_budget: int = 1600, min_chunks: int = 5, max_chunks: int = 6,
                  rng: random.Random | None = None) -> list[dict[str, Any]]:
    """Return 5–6 index chunks (when available/budget permits), favoring target course.

    The returned chunk objects retain the index fields and are wrapped by the caller
    in the request's ``{version: 1, chunks: [...], sources: {}}`` payload.
    """
    if isinstance(index, (str, Path)):
        index = load_index(index)
    if not isinstance(index, dict) or index.get("version") != 1 or not isinstance(index.get("chunks"), list):
        raise ValueError("notes index must have {version: 1, chunks: [...], sources: {...}} shape")
    if token_budget <= 0:
        return []
    if not (0 <= min_chunks <= max_chunks):
        raise ValueError("chunk bounds must satisfy 0 <= min_chunks <= max_chunks")
    rng = rng or random.SystemRandom()
    candidates = [chunk for chunk in index["chunks"] if isinstance(chunk, dict)
                  and all(key in chunk for key in ("id", "course_tag", "source", "title", "text", "word_count"))]
    target = str(target_course or "").strip().casefold()
    if target:
        targeted = [c for c in candidates if str(c.get("course_tag", "")).casefold() == target]
        others = [c for c in candidates if c not in targeted]
        rng.shuffle(targeted)
        rng.shuffle(others)
        candidates = targeted + others
    else:
        rng.shuffle(candidates)
    unique: list[dict[str, Any]] = []
    used_ids: set[str] = set()
    for chunk in candidates:
        if str(chunk["id"]) not in used_ids and str(chunk.get("text", "")).strip():
            unique.append(chunk)
            used_ids.add(str(chunk["id"]))
    # Reserve enough budget for a useful excerpt from every selected chunk.
    count = min(max_chunks, len(unique), token_budget // 64)
    if count >= min_chunks:
        count = max(count, min_chunks)
    if count == 0:
        return []
    chosen, remainder = unique[:count], token_budget
    per_chunk_budget = max(1, token_budget // count)
    sampled: list[dict[str, Any]] = []
    for idx, chunk in enumerate(chosen):
        remaining_chunks = len(chosen) - idx - 1
        allowance = min(per_chunk_budget, max(1, remainder - remaining_chunks * 64))
        excerpt = _excerpt(str(chunk["text"]), allowance)
        while _token_estimate({"text": excerpt}) > allowance and excerpt:
            excerpt = _excerpt(excerpt, max(1, allowance - 1))
        if not excerpt:
            continue
        sampled_chunk = {"id": str(chunk["id"])[:100],
                         "course_tag": str(chunk["course_tag"] or "")[:40] or None,
                         "source": str(chunk["source"] or "")[:200],
                         "title": str(chunk["title"] or "")[:160],
                         "text": excerpt,
                         "word_count": len(excerpt.split())}
        sampled.append(sampled_chunk)
        remainder -= _token_estimate({"text": excerpt})
    return sampled


def build_notes_payload(index: dict[str, Any] | str | Path, *, target_course: str | None = None,
                        token_budget: int = 1600, rng: random.Random | None = None) -> dict[str, Any]:
    loaded = load_index(index) if isinstance(index, (str, Path)) else index
    return {"version": 1,
            "chunks": sample_chunks(loaded, target_course=target_course,
                                    token_budget=token_budget, rng=rng),
            "sources": {}}
