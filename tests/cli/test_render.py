from __future__ import annotations

import pytest

from kilodial.cli.render import or_dash, pairs, table, yes_no


def test_a_table_pads_to_the_widest_cell() -> None:
    lines = table(["code", "name"], [["B2", "north wall"], ["B10", "bay"]])
    assert lines[0] == "code  name"
    assert lines[1] == "----  ----------"
    assert lines[2] == "B2    north wall"
    assert lines[3] == "B10   bay"


def test_numeric_columns_go_right() -> None:
    lines = table(["item", "count"], [["meters", "7"], ["runs", "1204"]])
    assert lines[2] == "meters      7"
    assert lines[3] == "runs     1204"


def test_a_column_that_is_only_mostly_numeric_stays_left() -> None:
    lines = table(["value"], [["7"], ["none"]])
    assert lines[2] == "7"
    assert lines[3] == "none"


def test_percentages_and_money_count_as_numbers() -> None:
    lines = table(["reading"], [["99.87%"], ["100.2%"]])
    assert lines[2] == " 99.87%"
    lines = table(["amount"], [["$1,204.05"], ["-$7.00"]])
    assert lines[2] == "$1,204.05"
    assert lines[3] == "   -$7.00"


def test_an_empty_table_is_just_the_heading() -> None:
    assert table(["code"], []) == ["code", "----"]


def test_a_row_that_does_not_fit() -> None:
    with pytest.raises(Exception, match="does not fit"):
        table(["a", "b"], [["only one"]])


def test_pairs_line_the_values_up() -> None:
    assert pairs([("serial", "84-119302"), ("state", "stock")]) == [
        "serial  84-119302",
        "state   stock",
    ]
    assert pairs([]) == []


def test_yes_no_and_or_dash() -> None:
    assert yes_no(True) == "yes"
    assert yes_no(0) == "no"
    assert or_dash(None) == "-"
    assert or_dash("2025-01-01") == "2025-01-01"
