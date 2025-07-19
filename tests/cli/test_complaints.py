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
    started(
        "point",
        "add",
        "SP-1042",
        "--account",
        "44-9021",
        "--address",
        "18 Fenwick Row",
        "--service",
        "1P3W",
        "--volts",
        "240",
        "--rate",
        "R1",
        "--energised",
        "2011-06-14",
    )
    started("point", "set", "SP-1042", "84-119302", "--multiplier", "1", "--on", "2019-05-02")
    return started


def referee(invoke: Invoke, reference: str, on: str, pct: str) -> None:
    invoke(
        "run",
        "record",
        reference,
        "--meter",
        "84-119302",
        "--bench",
        "B2",
        "--kind",
        "referee",
        "--on",
        on,
        "--by",
        "R Ellis",
        "--fl",
        pct,
        "--ll",
        pct,
    )


def test_opening_a_request(wired: Invoke) -> None:
    result = wired(
        "complaint",
        "open",
        "CR-1",
        "SP-1042",
        "--on",
        "2025-03-04",
        "--by",
        "M Okafor",
        "--reason",
        "high bill",
    )
    assert "test due by 2025-04-03" in result.output
    assert "CR-1" in wired("complaint", "list").output


def test_a_reason_nobody_files(wired: Invoke) -> None:
    result = wired(
        "complaint",
        "open",
        "CR-1",
        "SP-1042",
        "--on",
        "2025-03-04",
        "--by",
        "M Okafor",
        "--reason",
        "angry",
        expect=2,
    )
    assert "not a complaint reason" in result.output


def test_a_point_nobody_has(wired: Invoke) -> None:
    result = wired(
        "complaint",
        "open",
        "CR-1",
        "SP-9999",
        "--on",
        "2025-03-04",
        "--by",
        "M Okafor",
        expect=2,
    )
    assert "not on the book" in result.output


def test_answering_a_first_request_on_a_good_meter(wired: Invoke) -> None:
    wired("complaint", "open", "CR-1", "SP-1042", "--on", "2025-03-04", "--by", "M Okafor")
    referee(wired, "TR-9", "2025-03-14", "100.10")
    result = wired("complaint", "answer", "CR-1", "--run", "TR-9", "--on", "2025-03-14")
    assert "waived, first test in the free window" in result.output
    assert "$0.00" in result.output


def test_answering_a_repeat_request(wired: Invoke) -> None:
    wired("complaint", "open", "CR-0", "SP-1042", "--on", "2024-01-01", "--by", "M Okafor")
    wired("complaint", "open", "CR-1", "SP-1042", "--on", "2025-03-04", "--by", "M Okafor")
    referee(wired, "TR-9", "2025-03-14", "100.10")
    result = wired("complaint", "answer", "CR-1", "--run", "TR-9", "--on", "2025-03-14")
    assert "$28.00" in result.output
    assert "charged" in result.output


def test_a_bad_meter_waives_the_fee(wired: Invoke) -> None:
    wired("complaint", "open", "CR-0", "SP-1042", "--on", "2024-01-01", "--by", "M Okafor")
    wired("complaint", "open", "CR-1", "SP-1042", "--on", "2025-03-04", "--by", "M Okafor")
    referee(wired, "TR-9", "2025-03-14", "103.00")
    result = wired("complaint", "answer", "CR-1", "--run", "TR-9", "--on", "2025-03-14")
    assert "waived, meter outside tolerance" in result.output


def test_an_ordinary_run_cannot_answer(wired: Invoke) -> None:
    wired("complaint", "open", "CR-1", "SP-1042", "--on", "2025-03-04", "--by", "M Okafor")
    wired(
        "run",
        "record",
        "TR-9",
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
        "100.10",
    )
    result = wired("complaint", "answer", "CR-1", "--run", "TR-9", "--on", "2025-03-14", expect=2)
    assert "answered by a referee run" in result.output


def test_the_fee_can_be_overridden(wired: Invoke) -> None:
    wired("complaint", "open", "CR-0", "SP-1042", "--on", "2024-01-01", "--by", "M Okafor")
    wired("complaint", "open", "CR-1", "SP-1042", "--on", "2025-03-04", "--by", "M Okafor")
    referee(wired, "TR-9", "2025-03-14", "100.10")
    result = wired(
        "complaint", "answer", "CR-1", "--run", "TR-9", "--on", "2025-03-14", "--fee", "40"
    )
    assert "$40.00" in result.output


def test_a_closed_request_leaves_the_open_list(wired: Invoke) -> None:
    wired("complaint", "open", "CR-1", "SP-1042", "--on", "2025-03-04", "--by", "M Okafor")
    referee(wired, "TR-9", "2025-03-14", "100.10")
    wired("complaint", "answer", "CR-1", "--run", "TR-9", "--on", "2025-03-14")
    assert "CR-1" not in wired("complaint", "list").output
    assert "CR-1" in wired("complaint", "list", "--all").output


def test_listing_by_point_and_overdue(wired: Invoke) -> None:
    wired("complaint", "open", "CR-1", "SP-1042", "--on", "2025-03-04", "--by", "M Okafor")
    assert "CR-1" in wired("complaint", "list", "--point", "sp-1042").output
    assert "CR-1" in wired("complaint", "list", "--overdue", "2025-06-01").output
    assert "CR-1" not in wired("complaint", "list", "--overdue", "2025-03-10").output


def test_showing_a_request(wired: Invoke) -> None:
    wired(
        "complaint",
        "open",
        "CR-1",
        "SP-1042",
        "--on",
        "2025-03-04",
        "--by",
        "M Okafor",
        "--note",
        "bill doubled",
    )
    result = wired("complaint", "show", "CR-1")
    assert "bill doubled" in result.output
    assert "2025-04-03" in result.output


def test_the_clock_command(wired: Invoke) -> None:
    wired("complaint", "open", "CR-1", "SP-1042", "--on", "2025-03-04", "--by", "M Okafor")
    assert "in time" in wired("complaint", "clock", "--on", "2025-03-10").output
    assert "late" in wired("complaint", "clock", "--on", "2025-05-10").output


def test_the_reasons_command(wired: Invoke) -> None:
    result = wired("complaint", "reasons")
    assert "suspected tamper" in result.output
