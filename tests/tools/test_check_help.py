from __future__ import annotations

import click
import pytest

from kilodial.cli.main import cli
from kilodial.tools import check_help as gate


def test_every_command_and_option_is_explained() -> None:
    assert gate.faults() == []


def test_the_gate_passes(capsys: pytest.CaptureFixture[str]) -> None:
    assert gate.main([]) == 0
    assert "every one of them explained" in capsys.readouterr().out


def test_the_counts_are_real() -> None:
    commands, options = gate.counts()
    assert commands > 80
    assert options > 150


def test_a_summary_is_the_first_line() -> None:
    command = cli.commands["run"].commands["record"]  # type: ignore[attr-defined]
    assert gate.summary_of(command) == "Write a bench run down."


def test_a_command_with_no_help() -> None:
    bare = click.Command("bare")
    assert gate.faults_for(["bare"], bare) == ["bare has no help at all"]


def test_a_summary_that_reads_like_a_note() -> None:
    lower = click.Command("thing", help="does a thing.")
    problems = gate.faults_for(["thing"], lower)
    assert any("start with a capital" in p for p in problems)


def test_a_summary_that_does_not_end_a_sentence() -> None:
    fragment = click.Command("thing", help="Does a thing")
    assert any("end a sentence" in p for p in gate.faults_for(["thing"], fragment))


def test_a_question_ends_a_sentence() -> None:
    asked = click.Command("thing", help="Does it do a thing?")
    assert gate.faults_for(["thing"], asked) == []
    assert "?" in gate.ENDINGS


def test_a_summary_that_runs_on() -> None:
    long = click.Command("thing", help="A" * (gate.LONGEST_SUMMARY + 1) + ".")
    assert any("runs to" in p for p in gate.faults_for(["thing"], long))


def test_an_option_with_no_help() -> None:
    command = click.Command("thing", help="Does a thing.", params=[click.Option(["--nowhere"])])
    problems = gate.faults_for(["thing"], command)
    assert problems == ["thing: --nowhere has no help"]


def test_the_obvious_options_are_exempt() -> None:
    command = click.Command(
        "thing", help="Does a thing.", params=[click.Option(["--yes"], is_flag=True)]
    )
    assert gate.faults_for(["thing"], command) == []
    assert "--help" in gate.OBVIOUS


def test_arguments_are_not_options() -> None:
    command = click.Command("thing", help="Does a thing.", params=[click.Argument(["thing"])])
    assert gate.faults_for(["thing"], command) == []


def test_the_gate_fails_loudly(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(gate, "faults", lambda: ["something"])
    assert gate.main([]) == 1
    assert "do not say what they are for" in capsys.readouterr().out
