from __future__ import annotations

from pathlib import Path

import pytest

from kilodial.errors import BadInputError
from kilodial.ingest.sheet import Outcome, normalise, read_file, read_text

SIMPLE = "serial,tested on,registration\n84-119302,2025-03-04,100.12\n"


def test_column_names_are_normalised() -> None:
    assert normalise("  Meter_Serial ") == "meter serial"
    assert normalise("METER SERIAL") == "meter serial"


def test_reading_a_simple_sheet() -> None:
    sheet = read_text(SIMPLE)
    assert len(sheet) == 1
    assert sheet.columns == ("serial", "tested on", "registration")
    row = sheet.rows[0]
    assert row.line == 2
    assert row.need("Serial") == "84-119302"
    assert str(row) == "line 2"


def test_headers_match_however_they_are_spelled() -> None:
    sheet = read_text("Meter_Serial,Registration\n84-119302,100.12\n")
    assert sheet.has("meter serial")
    assert sheet.rows[0].need("METER SERIAL") == "84-119302"


def test_a_missing_column_is_named() -> None:
    with pytest.raises(BadInputError, match="missing bench, technician"):
        read_text(SIMPLE, required=["serial", "bench", "technician"])


def test_every_missing_column_is_named_at_once() -> None:
    with pytest.raises(BadInputError) as caught:
        read_text(SIMPLE, required=["a", "b", "c"])
    assert "a, b, c" in str(caught.value)


def test_a_required_column_that_is_there() -> None:
    assert len(read_text(SIMPLE, required=["serial", "registration"])) == 1


def test_an_empty_file() -> None:
    with pytest.raises(BadInputError, match="the file is empty"):
        read_text("")


def test_a_duplicated_column() -> None:
    with pytest.raises(BadInputError, match="the same column twice"):
        read_text("serial,serial\n1,2\n")


def test_a_short_row_names_its_line() -> None:
    with pytest.raises(BadInputError, match="line 3: 2 values against 3 columns"):
        read_text(SIMPLE + "84-119303,2025-03-05\n")


def test_blank_lines_are_skipped() -> None:
    assert len(read_text(SIMPLE + "\n\n")) == 1


def test_a_blank_cell_falls_back_to_the_default() -> None:
    sheet = read_text("serial,note\n84-119302,\n")
    row = sheet.rows[0]
    assert row.get("note") is None
    assert row.get("note", "-") == "-"
    assert row.get("nothing") is None


def test_a_needed_cell_that_is_blank() -> None:
    sheet = read_text("serial,note\n84-119302,\n")
    with pytest.raises(BadInputError, match="line 2: note is empty"):
        sheet.rows[0].need("note")


def test_reading_off_disk(tmp_path: Path) -> None:
    path = tmp_path / "bench.csv"
    path.write_text(SIMPLE)
    assert len(read_file(path)) == 1
    with pytest.raises(BadInputError, match="no file at"):
        read_file(tmp_path / "nowhere.csv")


def test_iterating_a_sheet() -> None:
    sheet = read_text(SIMPLE + "84-119303,2025-03-05,99.4\n")
    assert [row.need("serial") for row in sheet] == ["84-119302", "84-119303"]


def test_an_outcome_reports_what_it_left() -> None:
    clean = Outcome(4, ())
    assert clean.clean
    assert str(clean) == "4 rows taken, 0 left"
    messy = Outcome(3, ((5, "no such meter"),))
    assert not messy.clean
    assert "1 left" in messy.show()
