from __future__ import annotations

import json

import pytest

from kilodial.errors import BadInputError
from kilodial.report.document import Document, Grid, Section


def a_grid() -> Grid:
    return Grid.of(["group", "meters"], [["G1", "412"], ["G2", "88"]])


def test_a_grid_refuses_a_row_that_does_not_fit() -> None:
    with pytest.raises(BadInputError, match="does not fit"):
        Grid.of(["a", "b"], [["only one"]])


def test_an_empty_grid() -> None:
    empty = Grid.of(["group"], [])
    assert empty.is_empty
    assert empty.lines() == ["group", "-----"]
    assert empty.dicts() == []


def test_a_grid_renders_and_converts() -> None:
    grid = a_grid()
    assert grid.lines()[0] == "group  meters"
    assert grid.dicts() == [
        {"group": "G1", "meters": "412"},
        {"group": "G2", "meters": "88"},
    ]


def test_a_section_chains() -> None:
    section = Section("Shop").fact("meters", 412).fact("runs", 88).note("nothing odd")
    assert section.facts == [("meters", "412"), ("runs", "88")]
    lines = section.lines()
    assert lines[0] == "Shop"
    assert lines[1] == "===="
    assert "nothing odd" in lines


def test_a_section_with_only_a_grid() -> None:
    lines = Section("Groups", grid=a_grid()).lines()
    assert lines[2].startswith("group")


def test_a_section_with_both_puts_a_blank_line_between() -> None:
    section = Section("Groups", grid=a_grid())
    section.fact("groups", 2)
    lines = section.lines()
    assert "" in lines


def test_a_document_renders() -> None:
    doc = Document("Meter shop report")
    doc.section("Fleet").fact("meters", 412)
    doc.section("Groups", a_grid())
    text = doc.render()
    assert text.startswith("Meter shop report\n=================")
    assert "Fleet" in text
    assert "G1" in text
    assert str(doc) == text


def test_a_document_as_json() -> None:
    doc = Document("Meter shop report")
    doc.section("Fleet").fact("meters", 412).note("as at 2025-06-30")
    doc.section("Groups", a_grid())
    payload = json.loads(doc.as_json())
    assert payload["title"] == "Meter shop report"
    assert payload["sections"][0]["facts"] == {"meters": "412"}
    assert payload["sections"][0]["notes"] == ["as at 2025-06-30"]
    assert payload["sections"][1]["rows"][0]["group"] == "G1"


def test_a_document_as_csv() -> None:
    doc = Document("Meter shop report")
    doc.section("Fleet").fact("meters", 412)
    doc.section("Groups", a_grid())
    assert doc.as_csv() == "group,meters\nG1,412\nG2,88\n"


def test_a_document_with_no_table_cannot_be_csv() -> None:
    doc = Document("Nothing")
    doc.section("Fleet").fact("meters", 412)
    with pytest.raises(BadInputError, match="no table in it"):
        doc.as_csv()


def test_an_empty_grid_is_not_the_csv_table() -> None:
    doc = Document("Report")
    doc.section("Empty", Grid.of(["a"], []))
    doc.section("Full", a_grid())
    assert doc.as_csv().startswith("group,meters")
