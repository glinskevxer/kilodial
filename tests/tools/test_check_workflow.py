from __future__ import annotations

from pathlib import Path

import pytest

from kilodial.tools import check_workflow as gate


def test_ci_runs_every_gate() -> None:
    assert gate.faults() == []


def test_the_gate_passes(capsys: pytest.CaptureFixture[str]) -> None:
    assert gate.main([]) == 0
    assert "runs all" in capsys.readouterr().out


def test_the_gates_are_found() -> None:
    names = gate.gate_names()
    assert "check_migrations" in names
    assert "check_exports" in names
    assert "smoke" in names
    assert names == sorted(names)


def test_the_supported_versions_come_off_the_project() -> None:
    assert gate.supported_versions() == ["3.12", "3.13"]


def test_a_missing_workflow(tmp_path: Path) -> None:
    problems = gate.faults(tmp_path / "nowhere.yml")
    assert "there is no workflow" in problems[0]


def test_a_workflow_that_skips_a_gate(tmp_path: Path) -> None:
    path = tmp_path / "ci.yml"
    text = gate.WORKFLOW.read_text().replace(
        "      - run: python -m kilodial.tools.check_exports\n", ""
    )
    path.write_text(text)
    problems = gate.faults(path)
    assert any("check_exports" in p for p in problems)


def test_a_workflow_that_skips_a_python_version(tmp_path: Path) -> None:
    path = tmp_path / "ci.yml"
    path.write_text(gate.WORKFLOW.read_text().replace('"3.13"', '"3.12"'))
    assert any("python 3.13" in p for p in gate.faults(path))


def test_a_workflow_that_skips_a_tool(tmp_path: Path) -> None:
    path = tmp_path / "ci.yml"
    path.write_text(gate.WORKFLOW.read_text().replace("python -m mypy", "true"))
    assert any("never runs mypy" in p for p in gate.faults(path))


def test_a_workflow_that_never_builds(tmp_path: Path) -> None:
    path = tmp_path / "ci.yml"
    path.write_text(gate.WORKFLOW.read_text().replace("python -m build", "true"))
    assert any("never builds a wheel" in p for p in gate.faults(path))


def test_the_gate_fails_loudly(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(gate, "faults", lambda: ["something"])
    assert gate.main([]) == 1
    assert "1 things CI does not run" in capsys.readouterr().out


def test_the_walk_job_drives_the_console_script() -> None:
    text = gate.WORKFLOW.read_text()
    for command in ("device add", "run record", "adjust show", "report register"):
        assert f'kilodial --book "$book" {command}' in text
