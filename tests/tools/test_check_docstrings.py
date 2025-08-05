from __future__ import annotations

import pytest

from kilodial.tools import check_docstrings as gate
from kilodial.tools.check_exports import module_names


def test_nothing_is_unexplained() -> None:
    assert gate.faults() == []


def test_the_gate_passes(capsys: pytest.CaptureFixture[str]) -> None:
    assert gate.main([]) == 0
    assert "nothing unexplained" in capsys.readouterr().out


def test_the_counts_are_real() -> None:
    modules, written = gate.counts()
    assert modules > 50
    assert written > modules


def test_every_module_carries_a_docstring() -> None:
    for name in module_names():
        assert not any("module docstring" in p for p in gate.faults_for(name))


def test_a_module_with_no_source() -> None:
    assert gate.faults_for("kilodial") == []


def test_methods_are_exempt_and_module_functions_are_not() -> None:
    import ast

    tree = ast.parse(
        "'''Doc.'''\n"
        "class Thing:\n"
        "    '''A thing.'''\n"
        "    def method(self):\n"
        "        return 1\n"
        "def loose():\n"
        "    return 1\n"
    )
    names = [n.name for n in tree.body if isinstance(n, ast.FunctionDef)]
    assert names == ["loose"]


def test_a_click_command_is_exempt() -> None:
    import ast

    tree = ast.parse("@group.command('x')\ndef thing():\n    return 1\n")
    node = tree.body[0]
    assert isinstance(node, ast.FunctionDef)
    assert gate._is_command(node)


def test_the_gate_fails_when_something_is_wrong(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(gate, "faults", lambda: ["something"])
    assert gate.main([]) == 1
    assert "1 things want explaining" in capsys.readouterr().out
