from __future__ import annotations

import pytest

from tests.cli.conftest import Invoke


@pytest.fixture
def shop(started: Invoke) -> Invoke:
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
        "meter",
        "receive",
        "84-119302",
        "--type",
        "Halvern/R4S",
        "--acquired",
        "2019-04-02",
    )
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
        "2024-11-04",
        "--due",
        "2025-11-04",
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
        "2018-03-01",
    )
    return started


def record(invoke: Invoke, reference: str = "TR-1", *extra: str, expect: int = 0) -> str:
    return invoke(
        "run",
        "record",
        reference,
        "--meter",
        "84-119302",
        "--bench",
        "B2",
        "--on",
        "2025-03-04",
        "--by",
        "R Ellis",
        "--fl",
        "100.12",
        "--ll",
        "99.60",
        *extra,
        expect=expect,
    ).output


def test_recording_a_run_judges_it(shop: Invoke) -> None:
    assert "passed at 100.02%" in record(shop)


def test_the_standard_comes_off_the_bench(shop: Invoke) -> None:
    record(shop)
    assert "RS-5511" in shop("run", "show", "TR-1").output


def test_the_standard_can_be_overridden(shop: Invoke) -> None:
    shop(
        "standard",
        "add",
        "RS-7002",
        "--maker",
        "Radian",
        "--model",
        "RD-23",
        "--certificate",
        "NVLAP-90001",
        "--certified",
        "2024-01-01",
        "--due",
        "2026-01-01",
        "--uncertainty",
        "0.02",
    )
    record(shop, "TR-1", "--standard", "RS-7002")
    assert "RS-7002" in shop("run", "show", "TR-1").output


def test_a_failing_run_says_why(shop: Invoke) -> None:
    output = record(shop, "TR-1", "--fl", "104.00", "--ll", "103.00")
    assert "failed" in output
    result = shop("run", "judge", "TR-1", expect=1)
    assert "outside the +/-2.0 percent band" in result.output


def test_a_run_against_an_expired_certificate(shop: Invoke) -> None:
    output = shop(
        "run",
        "record",
        "TR-1",
        "--meter",
        "84-119302",
        "--bench",
        "B2",
        "--on",
        "2025-12-01",
        "--by",
        "R Ellis",
        "--fl",
        "100.12",
        "--ll",
        "99.60",
    ).output
    assert "void" in output
    assert "no reading" in output


def test_creep_words(shop: Invoke) -> None:
    record(shop, "TR-1", "--kind", "as_left", "--creep", "held")
    assert "held" in shop("run", "show", "TR-1").output
    output = record(shop, "TR-2", "--kind", "as_left", "--creep", "crept")
    assert "failed" in output


def test_a_creep_word_nobody_uses(shop: Invoke) -> None:
    output = record(shop, "TR-1", "--creep", "maybe", expect=2)
    assert "held or crept" in output


def test_a_run_kind_nobody_uses(shop: Invoke) -> None:
    output = record(shop, "TR-1", "--kind", "guesswork", expect=2)
    assert "is not one of" in output


def test_the_voltage_override(shop: Invoke) -> None:
    record(shop, "TR-1", "--volts", "277")
    assert "277 V" in shop("run", "show", "TR-1").output


def test_show_prints_the_working(shop: Invoke) -> None:
    record(shop)
    result = shop("run", "show", "TR-1")
    assert "(4x100.12 + 1x99.60) / 5 = 100.02" in result.output
    assert "FL" in result.output
    assert "LL" in result.output


def test_listing_runs(shop: Invoke) -> None:
    record(shop, "TR-1")
    record(shop, "TR-2", "--kind", "as_left")
    assert "TR-1" in shop("run", "list").output
    assert "TR-2" in shop("run", "list", "--meter", "84-119302").output
    assert "TR-1" not in shop("run", "list", "--kind", "as_left").output
    assert "TR-1" in shop("run", "list", "--bench", "B2").output


def test_listing_a_window(shop: Invoke) -> None:
    record(shop, "TR-1")
    assert "TR-1" in shop("run", "list", "--from", "2025-01-01", "--to", "2025-12-31").output
    assert "TR-1" not in shop("run", "list", "--from", "2024-01-01", "--to", "2024-12-31").output
    result = shop("run", "list", "--from", "2025-01-01", expect=2)
    assert "both --from and --to" in result.output


def test_a_run_that_names_a_meter_nobody_has(shop: Invoke) -> None:
    result = shop(
        "run",
        "record",
        "TR-1",
        "--meter",
        "84-000000",
        "--bench",
        "B2",
        "--on",
        "2025-03-04",
        "--by",
        "R Ellis",
        "--fl",
        "100.12",
        expect=2,
    )
    assert "no meter on the book" in result.output


def test_recording_with_no_readings(shop: Invoke) -> None:
    result = shop(
        "run",
        "record",
        "TR-1",
        "--meter",
        "84-119302",
        "--bench",
        "B2",
        "--on",
        "2025-03-04",
        "--by",
        "R Ellis",
        expect=2,
    )
    assert "no readings" in result.output


def test_deleting_a_run(shop: Invoke) -> None:
    record(shop)
    shop("run", "delete", "TR-1", "--yes")
    assert "TR-1" not in shop("run", "list").output


def test_showing_a_run_that_is_not_there(shop: Invoke) -> None:
    result = shop("run", "show", "TR-9", expect=2)
    assert "no bench run" in result.output
