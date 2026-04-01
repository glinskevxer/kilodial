from __future__ import annotations

import pytest

from kilodial.tools import check_exports as gate


def test_the_package_declares_its_exports() -> None:
    assert gate.faults() == []


def test_the_gate_passes(capsys: pytest.CaptureFixture[str]) -> None:
    assert gate.main([]) == 0
    assert "every export declared and sorted" in capsys.readouterr().out


def test_every_module_is_walked() -> None:
    names = gate.module_names()
    assert "kilodial" in names
    assert "kilodial.units.registration" in names
    assert "kilodial.cli.main" in names
    assert names == sorted(names)


def test_the_export_order_is_constants_then_classes_then_functions() -> None:
    names = ["build", "MAX_KH", "DeviceType", "MIN_KH", "form"]
    assert sorted(names, key=gate.export_order) == [
        "MAX_KH",
        "MIN_KH",
        "DeviceType",
        "build",
        "form",
    ]


def test_public_names_are_read_off_the_source() -> None:
    from kilodial.model import device

    found = gate.public_names(device)
    assert "DeviceType" in found
    assert "MAX_KH" in found
    assert "Decimal" not in found
    assert "_kh" not in found


def test_a_module_with_no_source() -> None:
    import types

    assert gate.public_names(types.ModuleType("nowhere")) == set()


def test_a_missing_name_in_all_is_caught(monkeypatch: pytest.MonkeyPatch) -> None:
    from kilodial.model import device

    monkeypatch.setattr(device, "__all__", ["DeviceType", "MAX_KH", "MIN_KH", "nonesuch"])
    problems = gate.faults_for("kilodial.model.device")
    assert any("names nonesuch" in p for p in problems)


def test_an_unsorted_all_is_caught(monkeypatch: pytest.MonkeyPatch) -> None:
    from kilodial.model import device

    monkeypatch.setattr(device, "__all__", ["MIN_KH", "MAX_KH", "DeviceType"])
    assert any("not sorted" in p for p in gate.faults_for("kilodial.model.device"))


def test_a_namespace_module_may_have_no_all() -> None:
    assert gate.faults_for("kilodial.model") == []
    assert "kilodial.model" in gate.NO_EXPORTS


def test_click_leaf_commands_are_not_exports() -> None:
    assert gate.faults_for("kilodial.cli.devices") == []


def test_the_gate_fails_when_something_is_wrong(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(gate, "faults", lambda: ["something"])
    assert gate.main([]) == 1
    assert "1 export problems" in capsys.readouterr().out


def test_the_module_list_is_cached() -> None:
    first = gate.module_names()
    assert gate.module_names() is first


def test_the_module_list_is_stable_across_calls() -> None:
    assert gate.module_names() == sorted(set(gate.module_names()))
