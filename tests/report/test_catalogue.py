from __future__ import annotations

import pytest

from kilodial.cli.main import cli
from kilodial.report import catalogue


def test_every_report_has_an_entry() -> None:
    commands = set(cli.commands["report"].commands)  # type: ignore[attr-defined]
    listed = set(catalogue.names())
    housekeeping = {"formats", "list"}
    assert listed == commands - housekeeping


def test_the_names_are_in_catalogue_order() -> None:
    assert catalogue.names()[0] == "shop"
    assert "commission" in catalogue.names()
    assert len(catalogue.names()) == len(set(catalogue.names()))


def test_every_question_reads_like_a_question() -> None:
    for entry in catalogue.CATALOGUE:
        assert entry.question.endswith("?")
        assert entry.question[0].isupper()


def test_the_command_line_for_an_entry() -> None:
    assert catalogue.find("shop").command == "kilodial report shop"
    assert str(catalogue.find("shop")).startswith("kilodial report shop - ")


def test_finding_a_report_that_is_not_there() -> None:
    with pytest.raises(KeyError, match="not a report"):
        catalogue.find("weather")


def test_the_split_by_what_they_take() -> None:
    over, at = catalogue.by_period()
    assert {e.name for e in over} == {"commission", "faults", "bench"}
    assert {e.name for e in at} == {"shop", "register", "certificates"}
    assert len(over) + len(at) == len(catalogue.CATALOGUE)


def test_the_period_flag_matches_the_commands_options() -> None:
    group = cli.commands["report"]
    for entry in catalogue.CATALOGUE:
        command = group.commands[entry.name]  # type: ignore[attr-defined]
        names = {opt for param in command.params for opt in param.opts}
        if entry.period:
            assert "--from" in names
            assert "--to" in names
        else:
            assert "--on" in names


def test_a_row_is_three_cells() -> None:
    assert len(catalogue.find("shop").row()) == 3
    assert catalogue.find("commission").row()[1] == "period"
