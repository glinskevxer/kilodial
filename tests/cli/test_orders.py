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
    started("meter", "receive", "84-119302", "--type", "Halvern/R4S", "--acquired", "2015-01-01")
    started(
        "standard",
        "add",
        "RS-5511",
        "--maker",
        "Radian",
        "--model",
        "RD-23",
        "--certificate",
        "NVLAP-88214",
        "--certified",
        "2015-01-01",
        "--due",
        "2035-01-01",
        "--uncertainty",
        "0.02",
    )
    started(
        "bench",
        "add",
        "B2",
        "north wall",
        "--positions",
        "8",
        "--standard",
        "RS-5511",
        "--max-amps",
        "100",
        "--max-volts",
        "480",
        "--installed",
        "2010-01-01",
    )
    return started


def test_raising_an_order(wired: Invoke) -> None:
    result = wired("work", "raise", "WO-1", "test", "84-119302", "--on", "2025-03-04")
    assert "due 2025-04-03" in result.output
    assert "WO-1" in wired("work", "list").output


def test_a_kind_nobody_raises(wired: Invoke) -> None:
    result = wired("work", "raise", "WO-1", "dance", "84-119302", "--on", "2025-03-04", expect=2)
    assert "not a work order kind" in result.output


def test_an_order_on_a_meter_nobody_has(wired: Invoke) -> None:
    result = wired("work", "raise", "WO-1", "test", "84-000000", "--on", "2025-03-04", expect=2)
    assert "not on the book" in result.output


def test_assigning_and_closing(wired: Invoke) -> None:
    wired("work", "raise", "WO-1", "test", "84-119302", "--on", "2025-03-04")
    wired(
        "run",
        "record",
        "TR-1",
        "--meter",
        "84-119302",
        "--bench",
        "B2",
        "--on",
        "2025-03-14",
        "--by",
        "R Ellis",
        "--fl",
        "100.10",
        "--ll",
        "99.80",
    )
    assert "assigned to R Ellis" in wired("work", "assign", "WO-1", "R Ellis").output
    result = wired("work", "done", "WO-1", "--on", "2025-03-14", "--run", "TR-1")
    assert "done after 10 days" in result.output
    assert "WO-1" not in wired("work", "list").output
    assert "WO-1" in wired("work", "list", "--all").output


def test_a_test_order_needs_its_run(wired: Invoke) -> None:
    wired("work", "raise", "WO-1", "test", "84-119302", "--on", "2025-03-04")
    result = wired("work", "done", "WO-1", "--on", "2025-03-14", expect=2)
    assert "closes with the run" in result.output


def test_closing_with_a_run_nobody_has(wired: Invoke) -> None:
    wired("work", "raise", "WO-1", "test", "84-119302", "--on", "2025-03-04")
    result = wired("work", "done", "WO-1", "--on", "2025-03-14", "--run", "TR-9", expect=2)
    assert "no bench run" in result.output


def test_a_repair_order_needs_a_disposition(wired: Invoke) -> None:
    wired("work", "raise", "WO-2", "repair", "84-119302", "--on", "2025-03-04")
    result = wired("work", "done", "WO-2", "--on", "2025-03-14", expect=2)
    assert "what became of the meter" in result.output
    wired("work", "done", "WO-2", "--on", "2025-03-14", "--disposition", "scrapped")
    assert "scrapped" in wired("work", "show", "WO-2").output


def test_cancelling(wired: Invoke) -> None:
    wired("work", "raise", "WO-1", "test", "84-119302", "--on", "2025-03-04")
    wired("work", "cancel", "WO-1", "--on", "2025-03-05", "--why", "duplicate")
    assert "duplicate" in wired("work", "show", "WO-1").output


def test_filtering(wired: Invoke) -> None:
    wired(
        "work", "raise", "WO-1", "test", "84-119302", "--on", "2025-03-04", "--priority", "urgent"
    )
    wired("work", "raise", "WO-2", "repair", "84-119302", "--on", "2025-03-04")
    wired("work", "assign", "WO-2", "R Ellis")
    assert "WO-2" in wired("work", "list", "--kind", "repair").output
    assert "WO-2" in wired("work", "list", "--to", "R Ellis").output
    assert "WO-1" in wired("work", "list", "--meter", "84-119302").output
    assert "WO-1" in wired("work", "list", "--late", "2025-03-10").output
    assert "WO-2" not in wired("work", "list", "--late", "2025-03-10").output


def test_the_planner_writes_nothing_without_the_flag(wired: Invoke) -> None:
    result = wired("work", "plan", "--on", "2025-01-01")
    assert "nothing written" in result.output
    assert "84-119302" in result.output
    assert wired("work", "list").output.count("WO-") == 0


def test_the_planner_raises_with_the_flag(wired: Invoke) -> None:
    result = wired("work", "plan", "--on", "2025-01-01", "--raise")
    assert "1 orders" in result.output
    assert "WO-2025-0001" in wired("work", "list").output


def test_the_planner_skips_a_meter_already_covered(wired: Invoke) -> None:
    wired("work", "plan", "--on", "2025-01-01", "--raise")
    result = wired("work", "plan", "--on", "2025-02-01")
    assert "already has a live test order" in result.output


def test_the_planner_limit(wired: Invoke) -> None:
    wired("meter", "receive", "84-119303", "--type", "Halvern/R4S", "--acquired", "2015-01-01")
    result = wired("work", "plan", "--on", "2025-01-01", "--limit", "1")
    assert "over the limit" in result.output


def test_counts_and_kinds(wired: Invoke) -> None:
    wired("work", "raise", "WO-1", "test", "84-119302", "--on", "2025-03-04")
    assert "open" in wired("work", "counts").output
    kinds = wired("work", "kinds").output
    assert "a run" in kinds
    assert "a disposition" in kinds


def test_showing_an_order_that_is_not_there(wired: Invoke) -> None:
    result = wired("work", "show", "WO-9", expect=2)
    assert "no work order" in result.output
