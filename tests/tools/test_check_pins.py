from __future__ import annotations

from pathlib import Path

import pytest

from kilodial.tools import check_pins as gate


def test_everything_is_pinned() -> None:
    assert gate.faults() == []


def test_the_gate_passes(capsys: pytest.CaptureFixture[str]) -> None:
    assert gate.main([]) == 0
    assert "pinned exactly" in capsys.readouterr().out


def test_the_direct_dependencies_are_read() -> None:
    found = gate.direct()
    assert found["click"] == ("==", "8.1.8")
    assert found["pytest"][0] == "=="
    assert "ruff" in found


def test_the_closure_carries_more_than_the_direct_pins() -> None:
    assert set(gate.direct()) <= set(gate.pinned())
    assert len(gate.pinned()) > len(gate.direct())


def test_names_compare_with_dashes_and_underscores_the_same() -> None:
    assert gate._normal("typing_extensions") == "typing-extensions"
    assert "mypy-extensions" in gate.pinned()


def test_the_build_requirements_are_pinned_too() -> None:
    assert all("==" in requirement for requirement in gate.build_requires())


def test_a_missing_constraints_file(tmp_path: Path) -> None:
    problems = gate.faults(gate.PYPROJECT, tmp_path / "nowhere.txt")
    assert "there is no constraints file" in problems[0]


def test_a_range_is_caught(tmp_path: Path) -> None:
    path = tmp_path / "pyproject.toml"
    path.write_text('[project]\nname = "x"\nversion = "1"\ndependencies = ["click>=8.0"]\n')
    problems = gate.faults(path, gate.CONSTRAINTS)
    assert any("is specified as >=" in p for p in problems)


def test_a_pin_missing_from_the_closure(tmp_path: Path) -> None:
    path = tmp_path / "pyproject.toml"
    path.write_text('[project]\nname = "x"\nversion = "1"\ndependencies = ["nowhere==1.0"]\n')
    problems = gate.faults(path, gate.CONSTRAINTS)
    assert any("is not in" in p for p in problems)


def test_a_pin_that_disagrees_with_the_closure(tmp_path: Path) -> None:
    path = tmp_path / "pyproject.toml"
    path.write_text('[project]\nname = "x"\nversion = "1"\ndependencies = ["click==9.9.9"]\n')
    problems = gate.faults(path, gate.CONSTRAINTS)
    assert any("9.9.9 in" in p for p in problems)


def test_comments_in_the_constraints_are_ignored(tmp_path: Path) -> None:
    path = tmp_path / "constraints.txt"
    path.write_text("# a comment\nclick==8.1.8  # trailing\n\n")
    assert gate.pinned(path) == {"click": "8.1.8"}


def test_the_gate_fails_loudly(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(gate, "faults", lambda: ["something"])
    assert gate.main([]) == 1
    assert "not pinned the way they should be" in capsys.readouterr().out
