from __future__ import annotations

import pytest

from kilodial.tools import query_plan as gate


def test_every_hot_query_uses_its_index() -> None:
    assert gate.faults() == []


def test_the_gate_passes(capsys: pytest.CaptureFixture[str]) -> None:
    assert gate.main([]) == 0
    assert "hot queries use an index" in capsys.readouterr().out


def test_the_plans_are_readable() -> None:
    found = gate.plans()
    assert set(found) == {q.name for q in gate.QUERIES}
    assert any("USING INDEX" in step for step in found["runs for one meter"])


def test_the_counting_query_is_meant_to_scan() -> None:
    assert any("SCAN" in step for step in gate.plans()["every meter"])
    assert not next(q for q in gate.QUERIES if q.name == "every meter").wants_index


def test_a_query_that_lost_its_index_is_caught(monkeypatch: pytest.MonkeyPatch) -> None:
    broken = gate.Query(
        "no index for this",
        "SELECT serial FROM meter WHERE owner = ?",
        ("utility",),
        True,
    )
    monkeypatch.setattr(gate, "QUERIES", (broken,))
    problems = gate.faults()
    assert any("no index for this scans" in p for p in problems)


def test_a_scan_that_stopped_scanning_is_caught(monkeypatch: pytest.MonkeyPatch) -> None:
    surprising = gate.Query(
        "this should scan",
        "SELECT serial FROM meter WHERE device_key = ?",
        ("Halvern/R4S",),
        False,
    )
    monkeypatch.setattr(gate, "QUERIES", (surprising,))
    assert any("expected to scan" in p for p in gate.faults())


def test_the_gate_fails_loudly(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(gate, "faults", lambda: ["something"])
    assert gate.main([]) == 1
    assert "not using the indexes" in capsys.readouterr().out


def test_every_query_names_a_real_table() -> None:
    for query in gate.QUERIES:
        assert " FROM " in query.sql
        assert query.name
