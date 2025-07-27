from __future__ import annotations

import pytest

from kilodial.store.schema import MIGRATIONS
from kilodial.tools import check_migrations as gate


def test_the_migration_list_is_clean() -> None:
    assert gate.faults() == []


def test_the_gate_passes(capsys: pytest.CaptureFixture[str]) -> None:
    assert gate.main([]) == 0
    printed = capsys.readouterr().out
    assert "all present" in printed
    assert str(len(MIGRATIONS)) in printed


def test_every_expected_table_is_built() -> None:
    joined = " ".join(s for m in MIGRATIONS for s in m.statements)
    for table in gate.EXPECTED_TABLES:
        if table == "schema_migration":
            continue
        assert f"CREATE TABLE {table}" in joined


def test_a_missing_table_is_caught(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(gate, "EXPECTED_TABLES", frozenset(gate.EXPECTED_TABLES | {"nonesuch"}))
    problems = gate.faults()
    assert any("nonesuch is not built" in p for p in problems)


def test_an_unexpected_table_is_caught(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(gate, "EXPECTED_TABLES", frozenset(gate.EXPECTED_TABLES - {"meter"}))
    problems = gate.faults()
    assert any("meter is built but not expected" in p for p in problems)


def test_the_gate_fails_when_something_is_wrong(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(gate, "faults", lambda: ["something"])
    assert gate.main([]) == 1
    assert "1 problems" in capsys.readouterr().out


def test_a_packed_statement_is_caught(monkeypatch: pytest.MonkeyPatch) -> None:
    from kilodial.store.schema import Migration

    broken = (*MIGRATIONS, Migration(99, "packed", ("SELECT 1; SELECT 2",)))
    monkeypatch.setattr("kilodial.store.schema.MIGRATIONS", broken)
    from kilodial.store.schema import check_migrations

    problems = check_migrations()
    assert any("packs more than one statement" in p for p in problems)
