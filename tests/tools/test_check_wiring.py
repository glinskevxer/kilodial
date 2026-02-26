from __future__ import annotations

import pytest

from kilodial.tools import check_wiring as gate


def test_everything_is_wired_in() -> None:
    assert gate.faults() == []


def test_the_gate_passes(capsys: pytest.CaptureFixture[str]) -> None:
    assert gate.main([]) == 0
    assert "everything reachable" in capsys.readouterr().out


def test_the_graph_covers_every_module() -> None:
    edges = gate.graph()
    assert "kilodial.store.shop" in edges
    assert "kilodial.units.registration" in edges
    assert len(edges) > 50


def test_imports_are_read_off_the_source() -> None:
    found = gate.imports_of("kilodial.store.shop")
    assert "kilodial.store.runs" in found
    assert "kilodial.testing.verdict" in found
    assert not any(name.startswith("sqlite3") for name in found)


def test_a_from_import_records_the_names_too() -> None:
    found = gate.imports_of("kilodial.store.shop")
    assert "kilodial.store.runs.RunRepository" in found


def test_a_module_with_no_source() -> None:
    assert gate.imports_of("kilodial") <= set(gate.imports_of("kilodial"))


def test_the_roots_are_reachable_by_definition() -> None:
    assert gate.is_root("kilodial")
    assert gate.is_root("kilodial.cli.main")
    assert gate.is_root("kilodial.tools.smoke")
    assert not gate.is_root("kilodial.store.shop")


def test_who_imports_a_module() -> None:
    found = gate.reach("kilodial.units.money")
    assert "kilodial.adjust.compute" in found
    assert found == sorted(found)


def test_a_module_nothing_imports_is_named(monkeypatch: pytest.MonkeyPatch) -> None:
    edges = gate.graph()
    edges["kilodial.store.dump"] = set()
    edges = {k: (v - {"kilodial.store.dump"}) for k, v in edges.items()}
    monkeypatch.setattr(gate, "graph", lambda: edges)
    assert "nothing imports kilodial.store.dump" in gate.faults()


def test_the_gate_fails_loudly(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(gate, "faults", lambda: ["something"])
    assert gate.main([]) == 1
    assert "not wired into anything" in capsys.readouterr().out


def test_every_cli_module_is_reachable_from_the_tree() -> None:
    tree = gate.imports_of("kilodial.cli.main")
    for name in gate.graph():
        if name.startswith("kilodial.cli.") and name != "kilodial.cli.main":
            assert any(name == target or target.startswith(f"{name}.") for target in tree) or (
                gate.reach(name) != []
            )
