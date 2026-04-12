from __future__ import annotations

import json
from pathlib import Path

import pytest

from kilodial.store.shop import open_shop
from kilodial.tools.smoke import stand_up
from tests.cli.conftest import Invoke


@pytest.fixture
def stocked(invoke: Invoke, book: Path) -> Invoke:
    invoke("init")
    with open_shop(book) as shop:
        stand_up(shop)
    return invoke


def test_exporting_to_standard_output(stocked: Invoke) -> None:
    payload = json.loads(stocked("book", "export").output)
    assert payload["format"] == 1
    assert payload["tables"]["meter"]["rows"][0][0] == "84-119302"


def test_exporting_to_a_file(stocked: Invoke, tmp_path: Path) -> None:
    out = tmp_path / "deep" / "book.json"
    result = stocked("book", "export", "--out", str(out))
    assert out.exists()
    assert "rows at migration" in result.output
    assert json.loads(out.read_text())["tables"]["meter"]


def test_a_round_trip_through_the_command_line(stocked: Invoke, tmp_path: Path, book: Path) -> None:
    out = tmp_path / "book.json"
    stocked("book", "export", "--out", str(out))
    other = tmp_path / "other.sqlite3"
    from click.testing import CliRunner

    from kilodial.cli.main import cli

    runner = CliRunner()
    assert runner.invoke(cli, ["--book", str(other), "init"]).exit_code == 0
    restored = runner.invoke(cli, ["--book", str(other), "book", "restore", str(out), "--yes"])
    assert restored.exit_code == 0
    assert "restored" in restored.output
    assert "meter 1" in restored.output
    summary = runner.invoke(cli, ["--book", str(other), "book", "summary"])
    assert "1" in summary.output


def test_restoring_into_a_book_that_is_not_empty(stocked: Invoke, tmp_path: Path) -> None:
    out = tmp_path / "book.json"
    stocked("book", "export", "--out", str(out))
    result = stocked("book", "restore", str(out), "--yes", expect=2)
    assert "is not empty" in result.output


def test_restoring_something_that_is_not_json(started: Invoke, tmp_path: Path) -> None:
    path = tmp_path / "notjson.json"
    path.write_text("not json at all")
    result = started("book", "restore", str(path), "--yes", expect=2)
    assert "is not json" in result.output


def test_restoring_a_dump_that_is_not_a_book(started: Invoke, tmp_path: Path) -> None:
    path = tmp_path / "other.json"
    path.write_text(json.dumps({"format": 1, "application": 1, "version": 1, "tables": {}}))
    result = started("book", "restore", str(path), "--yes", expect=2)
    assert "not from a kilodial book" in result.output


def test_restoring_a_file_that_is_not_there(started: Invoke, tmp_path: Path) -> None:
    result = started("book", "restore", str(tmp_path / "nowhere.json"), "--yes", expect=2)
    assert "does not exist" in result.output
