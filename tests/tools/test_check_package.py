from __future__ import annotations

from pathlib import Path

import pytest

from kilodial.tools import check_package as gate


def test_the_wheel_would_contain_what_it_should() -> None:
    assert gate.faults() == []


def test_the_gate_passes(capsys: pytest.CaptureFixture[str]) -> None:
    assert gate.main([]) == 0
    printed = capsys.readouterr().out
    assert "py.typed present" in printed
    assert "console script resolves" in printed


def test_the_type_marker_is_there() -> None:
    assert gate.marker_path().exists()
    assert gate.marker_path().name == "py.typed"


def test_the_wheel_is_built_from_the_source_tree_alone() -> None:
    assert gate.packaged_roots() == ["src/kilodial"]


def test_the_console_script_resolves() -> None:
    declared = gate.scripts()
    assert declared == {"kilodial": "kilodial.cli.main:run"}
    assert gate.resolves("kilodial.cli.main:run")


def test_a_target_that_is_not_there() -> None:
    assert not gate.resolves("kilodial.cli.main:nowhere")
    assert not gate.resolves("kilodial.nowhere:run")


def test_the_package_contents_are_the_subpackages() -> None:
    found = gate.contents()
    assert "py.typed" in found
    assert "errors.py" in found
    assert "store" in found
    assert "tests" not in found


def test_a_wheel_built_from_the_wrong_root_is_caught(tmp_path: Path) -> None:
    path = tmp_path / "pyproject.toml"
    path.write_text(
        '[build-system]\nrequires = ["hatchling==1.27.0"]\n'
        '[project]\nname = "x"\nversion = "1"\n'
        '[project.scripts]\nkilodial = "kilodial.cli.main:run"\n'
        '[tool.hatch.build.targets.wheel]\npackages = ["src", "tests"]\n'
    )
    problems = gate.faults(path)
    assert any("not from src/kilodial alone" in p for p in problems)
    assert any("would ship tests" in p for p in problems)


def test_a_wheel_with_no_console_script(tmp_path: Path) -> None:
    path = tmp_path / "pyproject.toml"
    path.write_text(
        '[build-system]\nrequires = ["hatchling==1.27.0"]\n'
        '[project]\nname = "x"\nversion = "1"\n'
        '[tool.hatch.build.targets.wheel]\npackages = ["src/kilodial"]\n'
    )
    assert any("no console script" in p for p in gate.faults(path))


def test_a_script_pointing_at_nothing(tmp_path: Path) -> None:
    path = tmp_path / "pyproject.toml"
    path.write_text(
        '[build-system]\nrequires = ["hatchling==1.27.0"]\n'
        '[project]\nname = "x"\nversion = "1"\n'
        '[project.scripts]\nkilodial = "kilodial.cli.main:nowhere"\n'
        '[tool.hatch.build.targets.wheel]\npackages = ["src/kilodial"]\n'
    )
    assert any("which is not there" in p for p in gate.faults(path))


def test_an_unpinned_backend(tmp_path: Path) -> None:
    path = tmp_path / "pyproject.toml"
    path.write_text(
        '[build-system]\nrequires = ["hatchling"]\n'
        '[project]\nname = "x"\nversion = "1"\n'
        '[project.scripts]\nkilodial = "kilodial.cli.main:run"\n'
        '[tool.hatch.build.targets.wheel]\npackages = ["src/kilodial"]\n'
    )
    assert any("is not pinned" in p for p in gate.faults(path))


def test_the_gate_fails_loudly(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(gate, "faults", lambda: ["something"])
    assert gate.main([]) == 1
    assert "what the wheel would contain" in capsys.readouterr().out
