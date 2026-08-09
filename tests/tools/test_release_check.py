from __future__ import annotations

from pathlib import Path

import pytest

import kilodial
from kilodial.tools import release_check as gate


def project(tmp_path: Path, version: str) -> Path:
    path = tmp_path / "pyproject.toml"
    path.write_text(f'[project]\nname = "kilodial"\nversion = "{version}"\n')
    return path


def changelog(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "CHANGELOG.md"
    path.write_text(text)
    return path


def test_the_repository_is_releasable() -> None:
    assert gate.faults() == []


def test_the_gate_passes(capsys: pytest.CaptureFixture[str]) -> None:
    assert gate.main([]) == 0
    assert "is releasable" in capsys.readouterr().out


def test_the_three_versions_agree() -> None:
    assert gate.declared_version() == kilodial.__version__
    assert gate.changelog_versions()[0] == kilodial.__version__


def test_the_changelog_says_something_about_this_version() -> None:
    body = gate.changelog_body(kilodial.__version__)
    assert body
    assert gate.notes_in(kilodial.__version__)


def test_a_version_that_disagrees(tmp_path: Path) -> None:
    problems = gate.faults(project(tmp_path, "9.9.9"), gate.CHANGELOG)
    assert any("pyproject says 9.9.9" in p for p in problems)


def test_a_changelog_with_no_headings(tmp_path: Path) -> None:
    problems = gate.faults(gate.PYPROJECT, changelog(tmp_path, "nothing here\n"))
    assert any("no version headings" in p for p in problems)


def test_a_changelog_that_lags_the_version(tmp_path: Path) -> None:
    path = changelog(tmp_path, "# Changelog\n\n## 0.0.1\n\n- something\n")
    assert any("leads with 0.0.1" in p for p in gate.faults(gate.PYPROJECT, path))


def test_a_changelog_entry_with_nothing_in_it(tmp_path: Path) -> None:
    version = gate.declared_version()
    path = changelog(tmp_path, f"# Changelog\n\n## {version}\n\n## 0.0.1\n\n- old\n")
    assert any("says nothing about" in p for p in gate.faults(gate.PYPROJECT, path))


def test_a_version_listed_twice(tmp_path: Path) -> None:
    version = gate.declared_version()
    path = changelog(tmp_path, f"# Changelog\n\n## {version}\n\n- new\n\n## {version}\n\n- again\n")
    assert any("lists a version twice" in p for p in gate.faults(gate.PYPROJECT, path))


def test_a_missing_changelog(tmp_path: Path) -> None:
    assert gate.changelog_versions(tmp_path / "nowhere.md") == []
    assert gate.changelog_body("0.1.0", tmp_path / "nowhere.md") == ""


def test_the_source_carries_no_markers() -> None:
    assert gate.markers_in_source() == []


def test_the_markers_that_are_looked_for() -> None:
    assert "TODO" in gate.MARKERS
    assert "FIXME" in gate.MARKERS
    assert "pdb.set_trace(" in gate.DEBUG_CALLS


def test_the_gate_fails_loudly(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(gate, "faults", lambda *_: ["something"])
    assert gate.main([]) == 1
    assert "stand in the way of a release" in capsys.readouterr().out


def test_the_scanner_imports_rather_than_reading_what_is_loaded() -> None:
    import sys

    for name in ("kilodial.model.demand", "kilodial.report.register"):
        sys.modules.pop(name, None)
    assert gate.markers_in_source() == []


def test_the_scanner_excuses_itself_by_name() -> None:
    assert gate.EXCUSED == "kilodial.tools.release_check"
    assert "release_check" not in " ".join(gate.markers_in_source())


def test_a_marker_in_a_module_is_found(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from kilodial.model import demand

    original = Path(demand.__file__).read_text()
    planted = tmp_path / "demand.py"
    planted.write_text(original + "\n# TODO: finish this\n")
    monkeypatch.setattr(demand, "__file__", str(planted))
    assert any("carries a TODO" in p for p in gate.markers_in_source())


def test_the_entry_for_this_version_says_enough() -> None:
    notes = gate.notes_in(gate.declared_version())
    assert len(notes) >= gate.FEWEST_NOTES
    assert all(note.startswith("- ") for note in notes)


def test_a_thin_entry_is_caught(tmp_path: Path) -> None:
    version = gate.declared_version()
    path = changelog(tmp_path, f"# Changelog\n\n## {version}\n\n- one thing\n")
    problems = gate.faults(gate.PYPROJECT, path)
    assert any("which is not an entry" in p for p in problems)


def test_the_versions_are_read_as_numbers() -> None:
    assert gate.as_numbers("1.2.3") == (1, 2, 3)
    assert gate.as_numbers("10.0.0") > gate.as_numbers("9.9.9")


def test_a_changelog_out_of_order_is_caught(tmp_path: Path) -> None:
    version = gate.declared_version()
    path = changelog(
        tmp_path,
        f"# Changelog\n\n## {version}\n\n- a\n- b\n- c\n\n"
        "## 0.9.0\n\n- x\n- y\n- z\n\n## 0.10.0\n\n- p\n- q\n- r\n",
    )
    assert any("rather than" in p for p in gate.faults(gate.PYPROJECT, path))


def test_this_changelog_descends() -> None:
    found = gate.changelog_versions()
    assert found == sorted(found, key=gate.as_numbers, reverse=True)


def test_the_version_is_one_point_oh() -> None:
    assert gate.declared_version() == "1.0.0"
    assert kilodial.__version__ == "1.0.0"
