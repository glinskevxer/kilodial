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
        "1.8",
        "--tech",
        "solid_state",
        "--introduced",
        "2014-05-01",
    )
    started("meter", "receive", "84-119302", "--type", "Halvern/R4S", "--acquired", "2015-01-01")
    started("meter", "receive", "84-220001", "--type", "Vantage/SM3", "--acquired", "2019-01-01")
    return started


def record(invoke: Invoke, reference: str = "RP-1", *extra: str, expect: int = 0) -> str:
    return invoke(
        "repair",
        "record",
        reference,
        "84-119302",
        "bearing",
        "--on",
        "2025-03-14",
        "--by",
        "R Ellis",
        "--hours",
        "1",
        "--parts",
        "12.40",
        "--replacement",
        "184.00",
        *extra,
        expect=expect,
    ).output


def test_recording_a_repair(wired: Invoke) -> None:
    assert "worth doing" in record(wired)
    assert "RP-1" in wired("repair", "list").output


def test_an_expensive_repair_says_so(wired: Invoke) -> None:
    output = record(wired, "RP-1", "--hours", "2", "--parts", "40.00")
    assert "should have been scrapped" in output
    assert "RP-1" in wired("repair", "list", "--wasteful").output


def test_a_fault_nobody_records(wired: Invoke) -> None:
    result = wired(
        "repair",
        "record",
        "RP-1",
        "84-119302",
        "gremlins",
        "--on",
        "2025-03-14",
        "--by",
        "R Ellis",
        "--hours",
        "1",
        "--replacement",
        "184.00",
        expect=2,
    )
    assert "not a fault" in result.output


def test_a_meter_nobody_has(wired: Invoke) -> None:
    result = wired(
        "repair",
        "record",
        "RP-1",
        "84-000000",
        "bearing",
        "--on",
        "2025-03-14",
        "--by",
        "R Ellis",
        "--hours",
        "1",
        "--replacement",
        "184.00",
        expect=2,
    )
    assert "not on the book" in result.output


def test_a_repair_that_takes_no_time(wired: Invoke) -> None:
    assert "more than no time" in record(wired, "RP-1", "--hours", "0", expect=2)


def test_showing_a_repair(wired: Invoke) -> None:
    record(wired)
    result = wired("repair", "show", "RP-1")
    assert "mechanical" in result.output
    assert "$68.00" in result.output
    assert "43.70 percent" in result.output


def test_filtering(wired: Invoke) -> None:
    record(wired, "RP-1")
    wired(
        "repair",
        "record",
        "RP-2",
        "84-220001",
        "board",
        "--on",
        "2025-06-30",
        "--by",
        "R Ellis",
        "--hours",
        "1",
        "--replacement",
        "300.00",
    )
    assert "RP-2" in wired("repair", "list", "--fault", "board").output
    assert "RP-1" in wired("repair", "list", "--meter", "84-119302").output
    assert "RP-2" in wired("repair", "list", "--from", "2025-06-01", "--to", "2025-12-31").output
    result = wired("repair", "list", "--from", "2025-06-01", expect=2)
    assert "both --from and --to" in result.output


def test_the_fault_breakdown(wired: Invoke) -> None:
    record(wired, "RP-1")
    result = wired("repair", "faults")
    assert "bearing" in result.output
    assert "100.0" in result.output
    assert "1 repairs across" in result.output


def test_the_fault_breakdown_for_one_type(wired: Invoke) -> None:
    record(wired, "RP-1")

    wired(
        "repair",
        "record",
        "RP-2",
        "84-220001",
        "board",
        "--on",
        "2025-06-30",
        "--by",
        "R Ellis",
        "--hours",
        "1",
        "--replacement",
        "300.00",
    )
    printed = wired("repair", "faults", "--type", "Vantage/SM3").output
    lines = [line for line in printed.splitlines() if line.startswith("board")]
    assert lines[0].split()[-2] == "1"


def test_the_fault_breakdown_of_nothing(wired: Invoke) -> None:
    result = wired("repair", "faults")
    assert "0 repairs across" in result.output


def test_the_spend_command(wired: Invoke) -> None:
    record(wired, "RP-1")
    result = wired("repair", "spend", "--from", "2025-01-01", "--to", "2025-12-31")
    assert "$80.40" in result.output
    assert "not worth doing" in result.output


def test_nothing_found_is_counted_apart(wired: Invoke) -> None:
    wired(
        "repair",
        "record",
        "RP-3",
        "84-119302",
        "none found",
        "--on",
        "2025-03-14",
        "--by",
        "R Ellis",
        "--hours",
        "1",
        "--replacement",
        "184.00",
    )
    result = wired("repair", "spend", "--from", "2025-01-01", "--to", "2025-12-31")
    assert "nothing found" in result.output
    assert result.output.strip().endswith("1")
