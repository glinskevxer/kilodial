from __future__ import annotations

from pathlib import Path

import pytest

from kilodial.store.shop import open_shop
from kilodial.tools.smoke import stand_up
from tests.cli.conftest import Invoke


@pytest.fixture
def stocked(invoke: Invoke, book: Path) -> Invoke:
    invoke("init")
    with open_shop(book) as shop:
        stand_up(shop)
    return invoke


def take(invoke: Invoke, value: int, on: str, *extra: str, expect: int = 0) -> str:
    return invoke(
        "read",
        "take",
        "SP-1042",
        "84-119302",
        str(value),
        "--on",
        on,
        "--dials",
        "5",
        *extra,
        expect=expect,
    ).output


def test_taking_a_reading(stocked: Invoke) -> None:
    assert "41200" in take(stocked, 41_200, "2025-01-01")
    assert "41200" in stocked("read", "list", "SP-1042").output


def test_a_reading_the_register_could_not_show(stocked: Invoke) -> None:
    assert "rolls at 100000" in take(stocked, 100_000, "2025-01-01", expect=2)


def test_a_meter_nobody_has(stocked: Invoke) -> None:
    result = stocked(
        "read",
        "take",
        "SP-1042",
        "84-000000",
        "100",
        "--on",
        "2025-01-01",
        "--dials",
        "5",
        expect=2,
    )
    assert "no meter on the book" in result.output


def test_a_point_nobody_has(stocked: Invoke) -> None:
    result = stocked(
        "read",
        "take",
        "SP-9999",
        "84-119302",
        "100",
        "--on",
        "2025-01-01",
        "--dials",
        "5",
        expect=2,
    )
    assert "no service point" in result.output


def test_reading_twice_on_one_day(stocked: Invoke) -> None:
    take(stocked, 41_200, "2025-01-01")
    assert "already on the book" in take(stocked, 41_210, "2025-01-01", expect=2)


def test_a_kind_nobody_reads(stocked: Invoke) -> None:
    assert "kind of register reading" in take(
        stocked, 100, "2025-01-01", "--kind", "guessed", expect=2
    )


def test_listing_a_window(stocked: Invoke) -> None:
    take(stocked, 41_200, "2025-01-01")
    take(stocked, 41_480, "2025-02-01")
    assert (
        "41200"
        not in stocked(
            "read", "list", "SP-1042", "--from", "2025-01-15", "--to", "2025-03-01"
        ).output
    )
    result = stocked("read", "list", "SP-1042", "--from", "2025-01-15", expect=2)
    assert "both --from and --to" in result.output


def test_consumption_between_two_readings(stocked: Invoke) -> None:
    take(stocked, 41_200, "2025-01-01")
    take(stocked, 41_480, "2025-02-01")
    result = stocked("read", "consumption", "SP-1042", "--from", "2025-01-01", "--to", "2025-02-01")
    assert "dials            280" in result.output
    assert "billed units     280.000" in result.output
    assert "register rolled  no" in result.output


def test_the_multiplier_comes_off_the_set(stocked: Invoke) -> None:
    take(stocked, 41_200, "2025-01-01")
    take(stocked, 41_480, "2025-02-01")
    result = stocked(
        "read",
        "consumption",
        "SP-1042",
        "--from",
        "2025-01-01",
        "--to",
        "2025-02-01",
        "--multiplier",
        "40",
    )
    assert "11200.000" in result.output


def test_a_rollover_is_named(stocked: Invoke) -> None:
    take(stocked, 99_860, "2025-01-01")
    take(stocked, 140, "2025-02-01")
    result = stocked("read", "consumption", "SP-1042", "--from", "2025-01-01", "--to", "2025-02-01")
    assert "register rolled  yes" in result.output
    assert "dials            280" in result.output


def test_an_implausible_rollover_exits_non_zero(stocked: Invoke) -> None:
    take(stocked, 90_000, "2025-01-01")
    take(stocked, 100, "2025-01-02")
    result = stocked(
        "read",
        "consumption",
        "SP-1042",
        "--from",
        "2025-01-01",
        "--to",
        "2025-01-02",
        expect=1,
    )
    assert "may not have rolled" in result.output


def test_consumption_with_one_reading(stocked: Invoke) -> None:
    take(stocked, 41_200, "2025-01-01")
    result = stocked(
        "read",
        "consumption",
        "SP-1042",
        "--from",
        "2025-01-01",
        "--to",
        "2025-02-01",
        expect=2,
    )
    assert "not enough to work consumption out of" in result.output


def test_a_reading_leaves_a_line_in_the_log(stocked: Invoke) -> None:
    take(stocked, 41_200, "2025-01-01")
    assert "read" in stocked("book", "history").output


def test_the_kinds_command(stocked: Invoke) -> None:
    result = stocked("read", "kinds")
    assert "customer" in result.output
    assert "rolls at 100000" in result.output
