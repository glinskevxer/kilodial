from __future__ import annotations

from tests.cli.conftest import Invoke


def add(invoke: Invoke, *extra: str) -> None:
    invoke(
        "device",
        "add",
        "Halvern",
        "R4S",
        "--form",
        "2S",
        "--class",
        "200",
        "--volts",
        "240",
        "--kh",
        "7.2",
        "--ratio",
        "100",
        "--introduced",
        "2004-05-01",
        *extra,
    )


def test_adding_a_type(started: Invoke) -> None:
    add(started)
    result = started("device", "list")
    assert "Halvern/R4S" in result.output
    assert "induction" in result.output


def test_adding_the_same_type_twice(started: Invoke) -> None:
    add(started)
    result = started(
        "device",
        "add",
        "Halvern",
        "R4S",
        "--form",
        "2S",
        "--class",
        "200",
        "--volts",
        "240",
        "--kh",
        "7.2",
        "--ratio",
        "100",
        "--introduced",
        "2004-05-01",
        expect=2,
    )
    assert "already on the book" in result.output


def test_an_induction_type_without_a_ratio(started: Invoke) -> None:
    result = started(
        "device",
        "add",
        "Halvern",
        "R4S",
        "--form",
        "2S",
        "--class",
        "200",
        "--volts",
        "240",
        "--kh",
        "7.2",
        "--introduced",
        "2004-05-01",
        expect=2,
    )
    assert "register ratio" in result.output


def test_a_solid_state_type(started: Invoke) -> None:
    started(
        "device",
        "add",
        "Vantage",
        "SM3",
        "--form",
        "16S",
        "--class",
        "320",
        "--volts",
        "277",
        "--kh",
        "1.0",
        "--tech",
        "solid_state",
        "--introduced",
        "2018-01-01",
    )
    result = started("device", "list", "--tech", "solid_state")
    assert "Vantage/SM3" in result.output
    assert "Halvern" not in result.output


def test_a_technology_nobody_stocks(started: Invoke) -> None:
    result = started(
        "device",
        "add",
        "Halvern",
        "R4S",
        "--form",
        "2S",
        "--class",
        "200",
        "--volts",
        "240",
        "--kh",
        "7.2",
        "--tech",
        "clockwork",
        "--introduced",
        "2004-05-01",
        expect=2,
    )
    assert "is not one of" in result.output


def test_listing_by_class(started: Invoke) -> None:
    add(started)
    started(
        "device",
        "add",
        "Halvern",
        "R9S",
        "--form",
        "9S",
        "--class",
        "20",
        "--volts",
        "240",
        "--kh",
        "0.6",
        "--ratio",
        "100",
        "--introduced",
        "2009-01-01",
    )
    result = started("device", "list", "--class", "20")
    assert "Halvern/R9S" in result.output
    assert "Halvern/R4S" not in result.output


def test_listing_what_was_current_on_a_day(started: Invoke) -> None:
    add(started, "--retired", "2012-12-31")
    assert "Halvern/R4S" in started("device", "list", "--on", "2010-01-01").output
    assert "Halvern/R4S" not in started("device", "list", "--on", "2015-01-01").output


def test_showing_a_type(started: Invoke) -> None:
    add(started, "--demand")
    result = started("device", "show", "Halvern/R4S")
    assert "form                2S (1P3W, 1 element)" in result.output
    assert "class               CL200 at 30 A" in result.output
    assert "demand              yes" in result.output
    assert "meters on the book  0" in result.output


def test_showing_a_type_that_is_not_there(started: Invoke) -> None:
    result = started("device", "show", "Nowhere/X1", expect=2)
    assert "no device type on the book" in result.output


def test_retiring_a_type(started: Invoke) -> None:
    add(started)
    started("device", "retire", "Halvern/R4S", "--on", "2016-12-31")
    assert "2016-12-31" in started("device", "list").output


def test_an_empty_catalogue_still_prints_headings(started: Invoke) -> None:
    result = started("device", "list")
    assert result.output.splitlines()[0].startswith("type")
