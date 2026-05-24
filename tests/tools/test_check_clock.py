from __future__ import annotations

import pytest

from kilodial.tools import check_clock as gate


def test_nothing_reads_the_clock_unasked() -> None:
    assert gate.faults() == []


def test_the_gate_passes(capsys: pytest.CaptureFixture[str]) -> None:
    assert gate.main([]) == 0
    printed = capsys.readouterr().out
    assert "none of them reads the clock unasked" in printed
    assert "allowed:" in printed


def test_the_two_allowed_places_are_named() -> None:
    assert set(gate.ALLOWED) == {"kilodial.store.book", "kilodial.store.events"}
    assert all(why for why in gate.ALLOWED.values())
    assert len(gate.allowed_lines()) == 2


def test_the_allowed_calls_are_timezone_aware() -> None:
    for name in gate.ALLOWED:
        for line, _ in gate.clock_calls(name):
            assert gate.is_aware(name, line)


def test_the_clock_names_that_are_looked_for() -> None:
    assert "today" in gate.CLOCK
    assert "now" in gate.CLOCK
    assert "utcnow" in gate.CLOCK


def test_the_calls_in_an_allowed_module_are_found() -> None:
    found = gate.clock_calls("kilodial.store.events")
    assert found
    assert any(shown.endswith(".now") for _, shown in found)


def test_a_module_with_no_clock_calls() -> None:
    assert gate.clock_calls("kilodial.units.money") == []


def test_a_module_with_no_source() -> None:
    assert gate.clock_calls("kilodial") == []


def test_a_clock_call_outside_the_allowed_modules_is_caught(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(gate, "ALLOWED", {})
    problems = gate.faults()
    assert problems
    assert "dates come in as arguments" in problems[0]


def test_a_naive_call_in_an_allowed_module_is_caught(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(gate, "is_aware", lambda *_: False)
    problems = gate.faults()
    assert any("without a timezone" in p for p in problems)


def test_the_gate_fails_loudly(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(gate, "faults", lambda: ["something"])
    assert gate.main([]) == 1
    assert "read the clock" in capsys.readouterr().out
