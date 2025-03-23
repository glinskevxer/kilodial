from __future__ import annotations

import pytest

from tests.cli.conftest import Invoke


@pytest.fixture
def stocked(started: Invoke) -> Invoke:
    started(
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
    )
    return started


def receive(invoke: Invoke, serial: str = "84-119302", *extra: str) -> None:
    invoke(
        "meter",
        "receive",
        serial,
        "--type",
        "Halvern/R4S",
        "--acquired",
        "2019-04-02",
        *extra,
    )


def test_receiving_a_meter(stocked: Invoke) -> None:
    receive(stocked)
    result = stocked("meter", "list")
    assert "84-119302" in result.output
    assert "received" in result.output


def test_receiving_against_a_type_nobody_stocks(stocked: Invoke) -> None:
    result = stocked(
        "meter",
        "receive",
        "84-119302",
        "--type",
        "Nowhere/X1",
        "--acquired",
        "2019-04-02",
        expect=2,
    )
    assert "not on the book" in result.output


def test_receiving_ahead_of_the_catalogue(stocked: Invoke) -> None:
    stocked(
        "meter",
        "receive",
        "84-119302",
        "--type",
        "Nowhere/X1",
        "--acquired",
        "2019-04-02",
        "--uncatalogued",
    )
    assert "Nowhere/X1" in stocked("meter", "list").output


def test_a_serial_that_is_not_a_serial(stocked: Invoke) -> None:
    result = stocked(
        "meter",
        "receive",
        "x",
        "--type",
        "Halvern/R4S",
        "--acquired",
        "2019-04-02",
        expect=2,
    )
    assert "not a meter serial" in result.output


def test_moving_a_meter_through_the_shop(stocked: Invoke) -> None:
    receive(stocked)
    stocked("meter", "move", "84-119302", "stock")
    result = stocked("meter", "move", "84-119302", "set")
    assert "is now set" in result.output


def test_an_illegal_move(stocked: Invoke) -> None:
    receive(stocked)
    result = stocked("meter", "move", "84-119302", "set", expect=2)
    assert "cannot go from received to set" in result.output


def test_a_state_nobody_has(stocked: Invoke) -> None:
    receive(stocked)
    result = stocked("meter", "move", "84-119302", "melted", expect=2)
    assert "is not one of" in result.output


def test_scrapping_wants_a_day(stocked: Invoke) -> None:
    receive(stocked)
    result = stocked("meter", "move", "84-119302", "scrap", expect=2)
    assert "needs the day" in result.output
    stocked("meter", "move", "84-119302", "scrap", "--on", "2025-06-01")
    assert "2025-06-01" in stocked("meter", "show", "84-119302").output


def test_sealing_and_unsealing(stocked: Invoke) -> None:
    receive(stocked)
    result = stocked("meter", "seal", "84-119302", "BX4471")
    assert "seal is now BX4471" in result.output
    result = stocked("meter", "seal", "84-119302")
    assert "seal is now -" in result.output


def test_listing_by_state_and_type(stocked: Invoke) -> None:
    receive(stocked, "84-119302")
    receive(stocked, "84-119303")
    stocked("meter", "move", "84-119303", "stock")
    assert "84-119303" in stocked("meter", "list", "--state", "stock").output
    assert "84-119302" not in stocked("meter", "list", "--state", "stock").output
    assert "84-119302" in stocked("meter", "list", "--type", "Halvern/R4S").output


def test_listing_what_is_in_the_shop(stocked: Invoke) -> None:
    receive(stocked, "84-119302")
    receive(stocked, "84-119303")
    stocked("meter", "move", "84-119303", "stock")
    stocked("meter", "move", "84-119303", "set")
    result = stocked("meter", "list", "--in-shop")
    assert "84-119302" in result.output
    assert "84-119303" not in result.output


def test_showing_a_meter(stocked: Invoke) -> None:
    receive(stocked, "84-119302", "--seal", "BX4471")
    result = stocked("meter", "show", "84-119302")
    assert "serial    84-119302" in result.output
    assert "Halvern/R4S form 2S CL200" in result.output
    assert "seal      BX4471" in result.output
    assert "runs      0" in result.output


def test_showing_a_meter_whose_type_is_missing(stocked: Invoke) -> None:
    stocked(
        "meter",
        "receive",
        "84-119302",
        "--type",
        "Nowhere/X1",
        "--acquired",
        "2019-04-02",
        "--uncatalogued",
    )
    assert "Nowhere/X1" in stocked("meter", "show", "84-119302").output


def test_showing_a_meter_that_is_not_there(stocked: Invoke) -> None:
    result = stocked("meter", "show", "84-000000", expect=2)
    assert "no meter on the book" in result.output


def test_counts_lists_every_state(stocked: Invoke) -> None:
    receive(stocked)
    result = stocked("meter", "counts")
    assert "received" in result.output
    assert "scrap" in result.output
