from __future__ import annotations

from pathlib import Path

import pytest

from kilodial import __version__
from kilodial.tools import build_index as gate


def test_the_index_on_disk_is_what_the_list_builds() -> None:
    assert gate.differences() == []


def test_the_check_passes(capsys: pytest.CaptureFixture[str]) -> None:
    assert gate.main(["--check"]) == 0
    assert "lists all" in capsys.readouterr().out


def test_every_document_it_names_is_there() -> None:
    assert gate.missing() == []
    for document in gate.DOCUMENTS:
        assert Path(document.path).exists()


def test_nothing_under_docs_is_left_out() -> None:
    assert gate.unlisted() == []


def test_each_document_says_how_to_rebuild_itself() -> None:
    for document in gate.DOCUMENTS:
        assert document.command.startswith("python -m kilodial.tools.")
        assert document.holds.endswith(".")
        assert document.title


def test_the_index_names_the_version() -> None:
    assert __version__ in gate.build()
    assert "Do not edit by hand" in gate.build()


def test_the_index_links_by_file_name() -> None:
    text = gate.build()
    assert "(commands.md)" in text
    assert "(schema.sql)" in text
    assert "docs/commands.md" not in text.split("## Documents")[1]


def test_writing_and_reading_back(tmp_path: Path) -> None:
    path = tmp_path / "deep" / "README.md"
    gate.write(path)
    assert path.exists()
    assert path.read_text() == gate.build()


def test_a_missing_index(tmp_path: Path) -> None:
    problems = gate.differences(tmp_path / "nowhere.md")
    assert any("there is no index" in p for p in problems)


def test_a_stale_index(tmp_path: Path) -> None:
    path = tmp_path / "README.md"
    path.write_text("nothing like it\n")
    assert any("is not what the list builds" in p for p in gate.differences(path))


def test_a_document_the_index_names_that_is_gone(monkeypatch: pytest.MonkeyPatch) -> None:
    missing = gate.Document("docs/nowhere.md", "Nowhere", "Nothing.", "build_index")
    monkeypatch.setattr(gate, "DOCUMENTS", (*gate.DOCUMENTS, missing))
    assert any("which is not there" in p for p in gate.differences())


def test_a_document_nobody_listed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(gate, "DOCUMENTS", gate.DOCUMENTS[:2])
    assert any("is not in the index" in p for p in gate.differences())


def test_the_check_fails_on_a_stale_index(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "README.md"
    path.write_text("nothing like it\n")
    assert gate.main(["--check", "--path", str(path)]) == 1
    assert "bring it up to date" in capsys.readouterr().out


def test_writing_from_the_command_line(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = tmp_path / "README.md"
    assert gate.main(["--path", str(path)]) == 0
    assert "listing 4 documents" in capsys.readouterr().out
