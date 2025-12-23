from __future__ import annotations

import pytest

from tests.cli.conftest import Invoke


@pytest.fixture
def wired(started: Invoke) -> Invoke:
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


def test_a_catalogued_type_leaves_a_line(wired: Invoke) -> None:
    result = wired("book", "history")
    assert "catalogued" in result.output
    assert "device Halvern/R4S" in result.output


def test_the_actor_can_be_named(wired: Invoke) -> None:
    wired(
        "--actor",
        "R Ellis",
        "meter",
        "receive",
        "84-119302",
        "--type",
        "Halvern/R4S",
        "--acquired",
        "2015-01-01",
    )
    assert "R Ellis" in wired("book", "history").output
    assert "R Ellis" in wired("book", "history", "--by", "R Ellis").output
    assert "84-119302" not in wired("book", "history", "--by", "Nobody").output


def test_the_default_actor_is_the_shop(wired: Invoke) -> None:
    assert "shop" in wired("book", "history").output


def test_a_move_leaves_a_line(wired: Invoke) -> None:
    wired("meter", "receive", "84-119302", "--type", "Halvern/R4S", "--acquired", "2015-01-01")
    wired("meter", "move", "84-119302", "stock")
    result = wired("book", "history", "--subject", "meter 84-119302")
    assert "received" in result.output
    assert "to stock" in result.output


def test_a_command_that_fails_leaves_nothing(wired: Invoke) -> None:
    before = wired("book", "history").output.count("\n")
    wired(
        "meter",
        "receive",
        "84-119302",
        "--type",
        "Nowhere/X1",
        "--acquired",
        "2015-01-01",
        expect=2,
    )
    assert wired("book", "history").output.count("\n") == before


def test_filtering_by_action(wired: Invoke) -> None:
    wired("meter", "receive", "84-119302", "--type", "Halvern/R4S", "--acquired", "2015-01-01")
    assert "84-119302" in wired("book", "history", "--action", "received").output
    assert "84-119302" not in wired("book", "history", "--action", "moved").output


def test_only_the_last_few_lines(wired: Invoke) -> None:
    for n in range(3):
        wired(
            "meter",
            "receive",
            f"84-11930{n}",
            "--type",
            "Halvern/R4S",
            "--acquired",
            "2015-01-01",
        )
    result = wired("book", "history", "--last", "2")
    assert "84-119301" in result.output
    assert "84-119300" not in result.output


def test_a_read_only_command_leaves_nothing(wired: Invoke) -> None:
    before = wired("book", "history").output
    wired("device", "list")
    wired("book", "summary")
    assert wired("book", "history").output == before


def test_a_deleted_line_is_reported(wired: Invoke, book: object) -> None:
    from kilodial.store.shop import open_shop

    wired("meter", "receive", "84-119302", "--type", "Halvern/R4S", "--acquired", "2015-01-01")
    with open_shop(book) as shop:  # type: ignore[arg-type]
        shop.book.connection.execute("DELETE FROM event WHERE sequence = 1")
    result = wired("book", "history", expect=1)
    assert "the log is missing 1 lines" in result.output


def test_the_summary_counts_the_log(wired: Invoke) -> None:
    assert "events" in wired("book", "summary").output
