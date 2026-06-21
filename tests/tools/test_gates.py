from __future__ import annotations

import pytest

from kilodial.tools import check_migrations, gates


def test_every_gate_passes() -> None:
    failed = [r.name for r in gates.run_all() if not r.passed]
    assert failed == []


def test_the_runner_reports_at_the_end(capsys: pytest.CaptureFixture[str]) -> None:
    assert gates.main([]) == 0
    printed = capsys.readouterr().out
    assert f"all {len(gates.GATES)} gates pass" in printed
    assert "ok   migrations" in printed


def test_quiet_leaves_the_passing_output_out(capsys: pytest.CaptureFixture[str]) -> None:
    assert gates.main(["--quiet"]) == 0
    printed = capsys.readouterr().out
    assert "ok   smoke" in printed
    assert "stood up" not in printed


def test_the_cheapest_gate_runs_first() -> None:
    assert gates.GATES[0][0] == "migrations"


def test_every_gate_has_a_name_and_a_module() -> None:
    for name, module, argv in gates.GATES:
        assert name
        assert hasattr(module, "main")
        assert isinstance(argv, list)


def test_running_one_gate_captures_its_output() -> None:
    result = gates.run_one("migrations", check_migrations, [])
    assert result.passed
    assert "all present" in result.output
    assert str(result) == "ok   migrations"


def test_a_failing_gate_is_reported_and_the_rest_still_run(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(check_migrations, "faults", lambda: ["something"])
    assert gates.main([]) == 1
    printed = capsys.readouterr().out
    assert "FAIL migrations" in printed
    assert "ok   smoke" in printed
    assert f"1 of {len(gates.GATES)} gates failed" in printed


def test_a_failing_gate_prints_even_when_quiet(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(check_migrations, "faults", lambda: ["something"])
    assert gates.main(["--quiet"]) == 1
    assert "something" in capsys.readouterr().out


def test_the_runner_is_not_a_ci_step() -> None:
    from kilodial.tools.check_workflow import RUN_ELSEWHERE, faults

    assert "gates" in RUN_ELSEWHERE
    assert faults() == []
