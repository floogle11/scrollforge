import json
from pathlib import Path

import fitz

from scripts.slice_notes import slice_notes


def _long_text(label: str) -> str:
    sentence = (f"{label} conservation gives a useful engineering relation for careful review. "
                "State the assumptions, identify the control volume, and retain consistent units. ")
    return "# Topic\n\n" + sentence * 45


def test_slicer_incremental_content_change_delete_and_cross_course_pdf(tmp_path):
    source = tmp_path / "input"
    output = tmp_path / "output" / "notes_index.json"
    (source / "ME-3310_Fluids").mkdir(parents=True)
    (source / "ENGR-2300_Thermo").mkdir(parents=True)
    fluids = source / "ME-3310_Fluids" / "fluids.md"
    thermo = source / "ENGR-2300_Thermo" / "thermo.txt"
    pdf_path = source / "ENGR-2300_Thermo" / "handout.pdf"
    fluids.write_text(_long_text("Fluids"), encoding="utf-8")
    thermo.write_text(_long_text("Thermodynamics"), encoding="utf-8")
    with fitz.open() as document:
        page = document.new_page()
        page.insert_text((72, 72), _long_text("PDF thermodynamics"))
        document.save(pdf_path)

    first = slice_notes(source, output)
    snapshot = output.read_bytes()
    second = slice_notes(source, output)
    assert output.read_bytes() == snapshot
    assert [chunk["id"] for chunk in first["chunks"]] == [chunk["id"] for chunk in second["chunks"]]
    by_course = {}
    for chunk in second["chunks"]:
        by_course.setdefault(chunk["course_tag"], []).append(chunk)
    assert "ME-3310" in by_course and "ENGR-2300" in by_course
    assert any(chunk["source"].endswith("handout.pdf") for chunk in by_course["ENGR-2300"])

    old_fluids_ids = {chunk["id"] for chunk in by_course["ME-3310"]}
    fluids.write_text(_long_text("Changed fluids"), encoding="utf-8")
    changed = slice_notes(source, output)
    new_fluids_ids = {chunk["id"] for chunk in changed["chunks"] if chunk["course_tag"] == "ME-3310"}
    assert new_fluids_ids.isdisjoint(old_fluids_ids)

    fluids.unlink()
    deleted = slice_notes(source, output)
    assert all(chunk["course_tag"] != "ME-3310" for chunk in deleted["chunks"])
    public_index = json.loads(output.read_text(encoding="utf-8"))
    assert set(public_index["sources"]) == {"ENGR-2300_Thermo/thermo.txt", "ENGR-2300_Thermo/handout.pdf"}
