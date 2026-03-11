from __future__ import annotations

from pathlib import Path

import pytest

from kilodial.tools import check_tests as gate


def test_every_module_has_tests_of_its_own() -> None:
    assert gate.faults() == []


def test_the_gate_passes(capsys: pytest.CaptureFixture[str]) -> None:
    assert gate.main([]) == 0
    assert "tests written against them" in capsys.readouterr().out


def test_where_a_module_s_tests_should_live() -> None:
    assert gate.test_path_for("kilodial.units.money") == Path("tests/units/test_money.py")
    assert gate.test_path_for("kilodial.store.shop") == Path("tests/store/test_shop.py")
    assert gate.test_path_for("kilodial") == Path("tests/test_errors.py")


def test_a_module_whose_tests_live_elsewhere() -> None:
    assert gate.test_path_for("kilodial.model.form") == Path("tests/model/test_form.py")
    assert "kilodial.cli.context" in gate.ELSEWHERE


def test_counting_the_tests_in_a_file() -> None:
    assert gate.test_count(Path("tests/units/test_money.py")) > gate.FEWEST_TESTS
    assert gate.test_count(Path("tests/nowhere.py")) == 0


def test_every_module_carries_more_than_a_token_number() -> None:
    found = gate.counts()
    assert all(count >= gate.FEWEST_TESTS for count in found.values())
    assert len(found) > 50


def test_a_module_with_no_test_file_is_named(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(gate, "test_path_for", lambda _: Path("tests/nowhere.py"))
    problems = gate.faults()
    assert problems
    assert "has no tests of its own" in problems[0]


def test_a_stub_test_file_is_caught(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    stub = tmp_path / "test_stub.py"
    stub.write_text("def test_one() -> None:\n    assert True\n")
    monkeypatch.setattr(gate, "test_path_for", lambda _: stub)
    problems = gate.faults()
    assert any("which is not a test file" in p for p in problems)


def test_the_gate_fails_loudly(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(gate, "faults", lambda: ["something"])
    assert gate.main([]) == 1
    assert "no tests of their own" in capsys.readouterr().out
