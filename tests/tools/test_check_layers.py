from __future__ import annotations

from pathlib import Path

import pytest

from kilodial.tools import check_layers as gate
from kilodial.tools.check_wiring import graph


def test_every_import_points_down_or_sideways() -> None:
    assert gate.faults() == []


def test_the_gate_passes(capsys: pytest.CaptureFixture[str]) -> None:
    assert gate.main([]) == 0
    assert "every import points down or sideways" in capsys.readouterr().out


def test_the_layers_are_deepest_prefix_wins() -> None:
    assert gate.rank_of("kilodial.units.money") == 0
    assert gate.rank_of("kilodial.model.device") == 1
    assert gate.rank_of("kilodial.store.shop") == 3
    assert gate.rank_of("kilodial.cli.main") == 5
    assert gate.rank_of("kilodial.report.document") == 2
    assert gate.rank_of("kilodial.report.commission") == 4


def test_a_module_outside_every_layer() -> None:
    assert gate.rank_of("something.else") == -1


def test_an_imported_name_is_trimmed_to_its_module() -> None:
    assert gate.module_only("kilodial.store.runs.RunRepository") == "kilodial.store.runs"
    assert gate.module_only("kilodial.units.money") == "kilodial.units.money"


def test_the_exception_list_is_empty() -> None:
    assert gate.EXCEPTIONS == {}


def test_an_upward_import_is_caught(monkeypatch: pytest.MonkeyPatch) -> None:
    edges = graph()
    edges["kilodial.model.device"] = {"kilodial.store.shop"}
    monkeypatch.setattr(gate, "graph", lambda: edges)
    problems = gate.faults()
    assert "kilodial.model.device (layer 1) imports kilodial.store.shop (layer 3)" in problems


def test_an_exception_is_allowed(monkeypatch: pytest.MonkeyPatch) -> None:
    edges = graph()
    edges["kilodial.model.device"] = {"kilodial.store.shop"}
    monkeypatch.setattr(gate, "graph", lambda: edges)
    monkeypatch.setattr(gate, "EXCEPTIONS", {"kilodial.model.device": {"kilodial.store.shop"}})
    assert gate.faults() == []


def test_the_map_is_written_out(tmp_path: Path) -> None:
    path = tmp_path / "deep" / "layers.md"
    gate.write(path)
    text = path.read_text()
    assert "# kilodial layers" in text
    assert "## Layer 0" in text
    assert "`kilodial.units`" in text


def test_writing_from_the_command_line(capsys: pytest.CaptureFixture[str]) -> None:
    assert gate.main(["--write"]) == 0
    assert "wrote" in capsys.readouterr().out


def test_the_gate_fails_loudly(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(gate, "faults", lambda: ["something"])
    assert gate.main([]) == 1
    assert "point the wrong way" in capsys.readouterr().out
