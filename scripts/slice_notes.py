"""Build a deterministic, incremental index of local course notes.

The module has no third-party import requirements for Markdown and text files.
PyMuPDF is imported only when a PDF actually needs to be read.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import unicodedata
from pathlib import Path
from typing import Any, Iterable


WORD_RE = re.compile(r"\b[\w]+(?:['’][\w]+)*\b", re.UNICODE)
COURSE_RE = re.compile(r"(?<![A-Z0-9])([A-Z]{2,6})[- ]?(\d{3,4})(?!\d)", re.IGNORECASE)
HEADING_RE = re.compile(r"^\s{0,3}(#{1,6})\s+(.+?)\s*#*\s*$")
SENTENCE_RE = re.compile(r"(?<=[.!?])\s+(?=(?:[\"'(*\[]*)[A-Z0-9])")
SUPPORTED_SUFFIXES = {".md", ".markdown", ".txt", ".pdf"}
CACHE_VERSION = 2
MIN_WORDS = 250
MAX_WORDS = 350


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _word_count(text: str) -> int:
    return len(WORD_RE.findall(text))


def _slug_course(value: str) -> str | None:
    match = COURSE_RE.search(value.upper())
    return f"{match.group(1).upper()}-{match.group(2)}" if match else None


def _folder_course(path: Path, root: Path) -> str | None:
    # Search from the closest containing folder outward.
    for parent in path.relative_to(root).parents:
        if str(parent) == ".":
            continue
        course = _slug_course(parent.name)
        if course:
            return course
    return _slug_course(root.name)


def _decode_text(path: Path) -> str:
    data = path.read_bytes()
    for encoding in ("utf-8-sig", "utf-8", "cp1252"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            pass
    return data.decode("utf-8", errors="replace")


def _pdf_text(path: Path) -> tuple[str, str | None]:
    try:
        import fitz  # type: ignore[import-not-found]
    except ImportError as exc:
        raise RuntimeError("PDF indexing requires PyMuPDF (install package 'pymupdf')") from exc

    with fitz.open(path) as document:
        metadata = document.metadata or {}
        title = (metadata.get("title") or "").strip() or None
        pages = [page.get_text("text") for page in document]
    return "\n\n".join(pages), title


def _split_sentences(paragraph: str) -> list[str]:
    paragraph = re.sub(r"\s+", " ", paragraph).strip()
    if not paragraph:
        return []
    # Preserve sentence punctuation. This intentionally remains lightweight and
    # deterministic; abbreviations may stay together as part of a sentence.
    return [part.strip() for part in SENTENCE_RE.split(paragraph) if part.strip()]


def _sentence_units(paragraph: str) -> list[str]:
    sentences = _split_sentences(paragraph)
    units: list[str] = []
    pending: list[str] = []
    pending_count = 0
    for sentence in sentences:
        count = _word_count(sentence)
        if count > MAX_WORDS:
            # A single enormous sentence is split at word boundaries rather
            # than allowed to produce an unusable oversized chunk.
            words = sentence.split()
            if pending:
                units.append(" ".join(pending))
                pending, pending_count = [], 0
            for start in range(0, len(words), MAX_WORDS):
                units.append(" ".join(words[start : start + MAX_WORDS]))
            continue
        if pending_count and pending_count + count > MAX_WORDS:
            units.append(" ".join(pending))
            pending, pending_count = [], 0
        pending.append(sentence)
        pending_count += count
    if pending:
        units.append(" ".join(pending))
    return units


def _sections(text: str, is_markdown: bool, fallback_title: str) -> list[tuple[str, str | None, list[str]]]:
    """Return section title, heading course code, and paragraph list."""
    sections: list[tuple[str, str | None, list[str]]] = []
    title = fallback_title
    course: str | None = None
    heading_courses: list[tuple[int, str | None]] = []
    paragraphs: list[str] = []

    def finish() -> None:
        nonlocal paragraphs
        if paragraphs:
            sections.append((title, course, paragraphs))
            paragraphs = []

    current: list[str] = []
    for raw_line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        line = raw_line.strip()
        heading = HEADING_RE.match(raw_line) if is_markdown else None
        if heading:
            if current:
                paragraphs.append(" ".join(current).strip())
                current = []
            finish()
            level = len(heading.group(1))
            title = re.sub(r"\s+#+\s*$", "", heading.group(2)).strip() or fallback_title
            heading_courses = [(old_level, value) for old_level, value in heading_courses if old_level < level]
            heading_course = _slug_course(title)
            heading_courses.append((level, heading_course))
            course = next((value for _, value in reversed(heading_courses) if value), None)
            continue
        if not line:
            if current:
                paragraphs.append(" ".join(current).strip())
                current = []
            continue
        # Strip common Markdown formatting without changing the readable text.
        if is_markdown:
            line = re.sub(r"^\s*[-*+]\s+", "", line)
            line = re.sub(r"^\s*\d+[.)]\s+", "", line)
            line = re.sub(r"`{1,3}", "", line)
            line = re.sub(r"!?\[([^\]]+)\]\([^)]*\)", r"\1", line)
            line = re.sub(r"[*_~]{1,3}", "", line)
        current.append(line)
    if current:
        paragraphs.append(" ".join(current).strip())
    finish()
    return sections


def _chunk_section(title: str, paragraphs: Iterable[str], source: str) -> list[dict[str, Any]]:
    # Split at sentence boundaries, then pack units into chunks no larger than
    # 350 words. Short final remainders are retained instead of discarded.
    units: list[str] = []
    for paragraph in paragraphs:
        units.extend(_sentence_units(paragraph))

    chunks: list[dict[str, Any]] = []
    current: list[str] = []
    count = 0

    def emit() -> None:
        nonlocal current, count
        text = " ".join(current).strip()
        if text:
            normalized = unicodedata.normalize("NFC", text)
            digest = _sha256((source + "\0" + normalized).encode("utf-8"))
            chunks.append({
                "id": f"note_{digest[:24]}",
                "course_tag": None,
                "source": source,
                "title": title,
                "text": normalized,
                "word_count": _word_count(normalized),
            })
        current, count = [], 0

    for unit in units:
        unit_count = _word_count(unit)
        if current and count + unit_count > MAX_WORDS:
            emit()
        current.append(unit)
        count += unit_count
    emit()
    return chunks


def _parse_source(path: Path, root: Path, relative: str) -> list[dict[str, Any]]:
    suffix = path.suffix.lower()
    pdf_title: str | None = None
    if suffix == ".pdf":
        raw, pdf_title = _pdf_text(path)
    else:
        raw = _decode_text(path)
    fallback_title = pdf_title or path.stem.replace("_", " ").replace("-", " ").strip()
    is_markdown = suffix in {".md", ".markdown"}
    sections = _sections(raw, is_markdown, fallback_title)
    folder_course = _folder_course(path, root)

    output: list[dict[str, Any]] = []
    for title, heading_course, paragraphs in sections:
        chunks = _chunk_section(title, paragraphs, relative)
        course_tag = folder_course or heading_course or "GENERAL"
        for chunk in chunks:
            chunk["course_tag"] = course_tag
        output.extend(chunks)
    return output


def _read_cache(cache_path: Path) -> dict[str, Any]:
    try:
        value = json.loads(cache_path.read_text(encoding="utf-8"))
        if value.get("version") == CACHE_VERSION and isinstance(value.get("sources"), dict):
            return value
    except (OSError, json.JSONDecodeError, AttributeError):
        pass
    return {"version": CACHE_VERSION, "sources": {}}


def _write_json_atomic(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def slice_notes(input_dir: str | Path, output_path: str | Path) -> dict[str, Any]:
    """Index supported note files recursively and return the written index.

    Unchanged source files reuse cached chunks from ``.cache/slice_notes`` and
    are not decoded or parsed again. Removed sources disappear from both the
    public index and the cache on the next run.
    """
    root = Path(input_dir).expanduser().resolve()
    output = Path(output_path).expanduser().resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"Input directory does not exist: {root}")

    repo_root = Path(__file__).resolve().parent.parent
    root_identity = root.as_posix().casefold().encode("utf-8")
    root_key = hashlib.sha256(root_identity).hexdigest()[:20]
    cache_path = repo_root / ".cache" / "slice_notes" / root_key / "cache.json"
    old_cache = _read_cache(cache_path)
    old_sources: dict[str, Any] = old_cache["sources"]
    current: dict[str, Any] = {}
    source_hashes: dict[str, str] = {}

    files = sorted(
        (path for path in root.rglob("*") if path.is_file() and path.suffix.lower() in SUPPORTED_SUFFIXES),
        key=lambda path: path.relative_to(root).as_posix().casefold(),
    )
    for path in files:
        relative = path.relative_to(root).as_posix()
        digest = _sha256(path.read_bytes())
        previous = old_sources.get(relative, {})
        if previous.get("sha256") == digest and isinstance(previous.get("chunks"), list):
            chunks = previous["chunks"]
        else:
            chunks = _parse_source(path, root, relative)
        source_hashes[relative] = digest
        current[relative] = {"sha256": digest, "chunks": chunks}

    chunks = [chunk for relative in sorted(current, key=str.casefold) for chunk in current[relative]["chunks"]]
    index = {"version": 1, "chunks": chunks, "sources": source_hashes}
    _write_json_atomic(output, index)
    _write_json_atomic(cache_path, {"version": CACHE_VERSION, "sources": current})
    return index


def main(argv: list[str] | None = None) -> int:
    repo_root = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(description="Deterministically slice local PDF, Markdown, and text notes")
    parser.add_argument("--input-dir", type=Path, default=repo_root / "notes_raw")
    parser.add_argument("--output", type=Path, default=repo_root / "docs" / "data" / "notes_index.json")
    args = parser.parse_args(argv)
    index = slice_notes(args.input_dir, args.output)
    print(f"Indexed {len(index['sources'])} source(s) into {len(index['chunks'])} chunk(s): {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
