from __future__ import annotations

from pathlib import Path

import click
import pytest

from kilodial.cli.main import cli
from kilodial.tools import build_docs as gate


def test_the_reference_on_disk_matches_the_tree() -> None:
    assert gate.differences() == []


def test_the_check_passes(capsys: pytest.CaptureFixture[str]) -> None:
    assert gate.main(["--check"]) == 0
    assert "matches the command tree" in capsys.readouterr().out


def test_the_walk_reaches_every_leaf() -> None:
    found = gate.walk(cli, [])
    paths = [" ".join(path) for path, _ in found]
    assert "init" in paths
    assert "run record" in paths
    assert "report register" in paths
    assert len(found) > 60


def test_the_walk_comes_back_sorted() -> None:
    paths = [" ".join(path) for path, _ in gate.walk(cli, [])]
    assert paths == sorted(paths)


def test_arguments_are_upper_cased() -> None:
    command = cli.commands["run"].commands["show"]  # type: ignore[attr-defined]
    assert gate.arguments_of(command) == ["REFERENCE"]


def test_options_carry_their_help_and_whether_they_are_required() -> None:
    command = cli.commands["run"].commands["record"]  # type: ignore[attr-defined]
    options = dict(gate.options_of(command))
    assert options["--on"] == "the day it was run (required)"
    assert "help" not in " ".join(options)


def test_the_reference_names_the_groups() -> None:
    text = gate.build()
    assert "Groups: adjust, bench" in text
    assert "Do not edit by hand" in text
    assert "## `run record`" in text


def test_every_command_has_a_summary_line() -> None:
    text = gate.build()
    for path, command in gate.walk(cli, []):
        assert f"## `{' '.join(path)}`" in text
        assert (command.help or "").strip(), f"{path} has no help"


def test_writing_and_reading_back(tmp_path: Path) -> None:
    path = tmp_path / "deep" / "commands.md"
    gate.write(path)
    assert path.exists()
    assert gate.differences(path) == []


def test_a_missing_reference(tmp_path: Path) -> None:
    assert "no command reference" in gate.differences(tmp_path / "nowhere.md")[0]


def test_a_stale_reference(tmp_path: Path) -> None:
    path = tmp_path / "commands.md"
    gate.write(path)
    path.write_text(path.read_text().replace("run record", "run recrod", 1))
    assert any("should be" in p for p in gate.differences(path))


def test_the_check_fails_on_a_stale_reference(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "commands.md"
    path.write_text("nothing like it\n")
    assert gate.main(["--check", "--path", str(path)]) == 1
    assert "bring it up to date" in capsys.readouterr().out


def test_writing_from_the_command_line(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = tmp_path / "commands.md"
    assert gate.main(["--path", str(path)]) == 0
    assert "covering" in capsys.readouterr().out


def test_a_leaf_command_walks_to_itself() -> None:
    leaf = click.Command("solo")
    assert gate.walk(leaf, ["solo"]) == [(["solo"], leaf)]
