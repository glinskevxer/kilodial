from __future__ import annotations

import pytest

from kilodial.tools import check_messages as gate


def test_every_message_is_in_the_house_style() -> None:
    assert gate.faults() == []


def test_the_gate_passes(capsys: pytest.CaptureFixture[str]) -> None:
    assert gate.main([]) == 0
    assert "all of them in the house style" in capsys.readouterr().out


def test_the_package_raises_a_lot_of_messages() -> None:
    assert gate.counts() > 200


def test_a_plain_message_is_read() -> None:
    found = gate.messages_in("kilodial.units.money")
    texts = [text for _, text, _ in found]
    assert "cents have to be a whole number" in texts
    assert all(not interpolated for _, text, interpolated in found if text.startswith("cents"))


def test_an_interpolated_message_is_read_without_its_values() -> None:
    found = gate.messages_in("kilodial.model.meter")
    texts = [text for _, text, interpolated in found if interpolated]
    assert any("is not a meter serial number" in text for text in texts)


def test_a_module_with_no_source() -> None:
    assert gate.messages_in("kilodial") == []


def test_a_capital_is_caught(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(gate, "messages_in", lambda _: [(1, "Not like this", False)])
    problems = gate.faults_for("kilodial.units.money")
    assert any("starts with a capital" in p for p in problems)


def test_an_acronym_is_not_a_capital(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        gate, "messages_in", lambda _: [(1, "CT-8841 is a voltage transformer", False)]
    )
    assert gate.faults_for("kilodial.units.money") == []


def test_a_full_stop_is_caught(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(gate, "messages_in", lambda _: [(1, "not like this.", False)])
    assert any("full stop" in p for p in gate.faults_for("kilodial.units.money"))


def test_a_blank_message_is_ignored(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(gate, "messages_in", lambda _: [(1, "   ", False)])
    assert gate.faults_for("kilodial.units.money") == []


def test_the_gate_fails_loudly(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(gate, "faults", lambda: ["something"])
    assert gate.main([]) == 1
    assert "do not read the way the rest do" in capsys.readouterr().out
