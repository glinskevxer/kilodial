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
    started("point", "set", "SP-1042", "84-119302", "--multiplier", "1", "--on", "2024-12-01")
    return started


LAST_DAY = {1: 31, 2: 28, 3: 31, 4: 30, 5: 31, 6: 30}


def bill(invoke: Invoke, months: int = 6, amount: str = "100.00") -> None:
    for index in range(1, months + 1):
        invoke(
            "bill",
            "add",
            "SP-1042",
            "--from",
            f"2025-{index:02d}-01",
            "--to",
            f"2025-{index:02d}-{LAST_DAY[index]}",
            "--amount",
            amount,
        )


def bench(invoke: Invoke, reference: str, on: str, pct: str) -> None:
    invoke(
        "run",
        "record",
        reference,
        "--meter",
        "84-119302",
        "--bench",
        "B2",
        "--on",
        on,
        "--by",
        "R Ellis",
        "--fl",
        pct,
        "--ll",
        pct,
    )


def test_recording_and_listing_a_bill(wired: Invoke) -> None:
    wired(
        "bill",
        "add",
        "SP-1042",
        "--from",
        "2025-01-01",
        "--to",
        "2025-01-31",
        "--amount",
        "104.22",
        "--kwh",
        "912.4",
    )
    result = wired("bill", "list", "SP-1042")
    assert "$104.22" in result.output
    assert "912.4" in result.output
    assert "31" in result.output


def test_overlapping_billing_periods(wired: Invoke) -> None:
    wired(
        "bill", "add", "SP-1042", "--from", "2025-01-01", "--to", "2025-01-31", "--amount", "100.00"
    )
    result = wired(
        "bill",
        "add",
        "SP-1042",
        "--from",
        "2025-01-15",
        "--to",
        "2025-02-14",
        "--amount",
        "100.00",
        expect=2,
    )
    assert "already on the book" in result.output


def test_billing_a_point_nobody_has(wired: Invoke) -> None:
    result = wired(
        "bill",
        "add",
        "SP-9999",
        "--from",
        "2025-01-01",
        "--to",
        "2025-01-31",
        "--amount",
        "100.00",
        expect=2,
    )
    assert "not on the book" in result.output


def test_listing_a_window(wired: Invoke) -> None:
    bill(wired, 3)
    assert (
        "2025-02-01"
        in wired("bill", "list", "SP-1042", "--from", "2025-02-01", "--to", "2025-02-28").output
    )
    result = wired("bill", "list", "SP-1042", "--from", "2025-02-01", expect=2)
    assert "both --from and --to" in result.output


def test_removing_a_billing_period(wired: Invoke) -> None:
    bill(wired, 1)
    wired("bill", "remove", "SP-1042", "2025-01-01", "--yes")
    assert "$100.00" not in wired("bill", "list", "SP-1042").output


def test_a_meter_inside_tolerance_is_not_adjusted(wired: Invoke) -> None:
    bill(wired)
    bench(wired, "TR-1", "2025-06-30", "101.00")
    result = wired("adjust", "show", "SP-1042", "--on", "2025-07-15")
    assert "inside the +/-2.0 percent tolerance" in result.output


def test_a_fast_meter_produces_a_refund_sheet(wired: Invoke) -> None:
    bill(wired)
    bench(wired, "TR-1", "2025-06-30", "103.00")
    result = wired("adjust", "show", "SP-1042", "--on", "2025-07-15")
    assert "refund" in result.output
    assert "$600.00" in result.output
    assert result.output.count("2025-") > 6


def test_a_slow_meter_produces_a_back_bill_sheet(wired: Invoke) -> None:
    bill(wired)
    bench(wired, "TR-1", "2025-06-30", "96.00")
    result = wired("adjust", "show", "SP-1042", "--on", "2025-07-15")
    assert "back bill" in result.output


def test_the_period_command_names_what_bounds_it(wired: Invoke) -> None:
    bill(wired)
    bench(wired, "TR-1", "2025-06-30", "103.00")
    result = wired("adjust", "period", "SP-1042", "--on", "2025-07-15")
    assert "the day the meter was set" in result.output
    assert "2024-12-01" in result.output


def test_the_period_command_on_a_meter_that_is_fine(wired: Invoke) -> None:
    bill(wired)
    bench(wired, "TR-1", "2025-06-30", "100.10")
    result = wired("adjust", "period", "SP-1042", "--on", "2025-07-15")
    assert "inside the" in result.output


def test_no_billed_history(wired: Invoke) -> None:
    bench(wired, "TR-1", "2025-06-30", "103.00")
    result = wired("adjust", "show", "SP-1042", "--on", "2025-07-15")
    assert "no billed history" in result.output


def test_a_meter_that_was_never_tested(wired: Invoke) -> None:
    bill(wired)
    result = wired("adjust", "show", "SP-1042", "--on", "2025-07-15", expect=2)
    assert "no usable as found run" in result.output


def test_the_tariff_command(wired: Invoke) -> None:
    result = wired("adjust", "tariff")
    assert "refund lookback" in result.output
    assert "60 months" in result.output
    assert "12 months" in result.output
