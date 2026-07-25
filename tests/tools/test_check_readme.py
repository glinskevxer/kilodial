from __future__ import annotations

from pathlib import Path

import pytest

from kilodial import __version__
from kilodial.tools import check_readme as gate


def test_the_readme_still_describes_the_package() -> None:
    assert gate.faults() == []


def test_the_gate_passes(capsys: pytest.CaptureFixture[str]) -> None:
    assert gate.main([]) == 0
    assert "all of them real" in capsys.readouterr().out


def test_every_link_points_at_something_here() -> None:
    found = gate.links()
    assert "docs/commands.md" in found
    assert all(Path(target).exists() for target in found)


def test_the_worked_example_is_real() -> None:
    found = gate.commands()
    assert len(found) > 10
    assert any(line.startswith("device add") for line in found)
    assert all(gate.resolves(line) for line in found)


def test_a_continuation_is_joined() -> None:
    assert any("--introduced" in line for line in gate.commands())
    assert not any(line.endswith("\\") for line in gate.commands())


def test_resolving_a_command() -> None:
    assert gate.resolves("init")
    assert gate.resolves("run show TR-1")
    assert gate.resolves("report shop --on 2026-01-01")
    assert not gate.resolves("nowhere")
    assert not gate.resolves("run nowhere")
    assert not gate.resolves("run")


def test_the_readme_names_no_other_version() -> None:
    for version in gate.versions():
        assert version == __version__


def test_a_missing_readme(tmp_path: Path) -> None:
    assert "there is no readme" in gate.faults(tmp_path / "nowhere.md")[0]


def test_a_dead_link_is_caught(tmp_path: Path) -> None:
    path = tmp_path / "README.md"
    path.write_text("see [the docs](docs/nowhere.md)\n")
    assert any("which is not there" in p for p in gate.faults(path))


def test_a_command_that_no_longer_exists_is_caught(tmp_path: Path) -> None:
    path = tmp_path / "README.md"
    path.write_text("run it\n\n    kilodial nowhere --on 2026-01-01\n")
    assert any("is not a command" in p for p in gate.faults(path))


def test_a_stale_version_is_caught(tmp_path: Path) -> None:
    path = tmp_path / "README.md"
    path.write_text("install kilodial 0.0.1\n")
    assert any("names version 0.0.1" in p for p in gate.faults(path))


def test_an_absolute_link_is_left_alone(tmp_path: Path) -> None:
    path = tmp_path / "README.md"
    path.write_text("see [the site](https://example.invalid/x)\n")
    assert gate.faults(path) == []


def test_the_gate_fails_loudly(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(gate, "faults", lambda: ["something"])
    assert gate.main([]) == 1
    assert "no longer describe this package" in capsys.readouterr().out
