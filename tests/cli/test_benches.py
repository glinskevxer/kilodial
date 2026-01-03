from __future__ import annotations

import pytest

from tests.cli.conftest import Invoke


def add_standard(invoke: Invoke, serial: str = "RS-5511", *extra: str) -> None:
    invoke(
        "standard",
        "add",
        serial,
        "--maker",
        "Radian",
        "--model",
        "RD-23",
        "--certificate",
        f"NVLAP-{serial[-4:]}",
        "--certified",
        "2024-11-04",
        "--due",
        "2025-11-04",
        "--uncertainty",
        "0.02",
        *extra,
    )


@pytest.fixture
def kitted(started: Invoke) -> Invoke:
    add_standard(started)
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
        "--polyphase",
        "--installed",
        "2018-03-01",
    )
    return started


def test_adding_a_standard(started: Invoke) -> None:
    add_standard(started)
    assert "RS-5511" in started("standard", "list").output


def test_an_uncertainty_looser_than_shop_grade(started: Invoke) -> None:
    result = started(
        "standard",
        "add",
        "RS-5511",
        "--maker",
        "Radian",
        "--model",
        "RD-23",
        "--certificate",
        "X",
        "--certified",
        "2024-11-04",
        "--due",
        "2025-11-04",
        "--uncertainty",
        "0.9",
        expect=2,
    )
    assert "looser than" in result.output


def test_recertifying(started: Invoke) -> None:
    add_standard(started)
    result = started(
        "standard",
        "recertify",
        "RS-5511",
        "--certificate",
        "NVLAP-90001",
        "--certified",
        "2025-11-01",
        "--due",
        "2026-11-01",
    )
    assert "NVLAP-5511 replaced by NVLAP-90001" in result.output
    assert "2026-11-01" in started("standard", "list").output


def test_recertifying_something_that_is_not_there(started: Invoke) -> None:
    result = started(
        "standard",
        "recertify",
        "RS-0000",
        "--certificate",
        "X",
        "--certified",
        "2025-11-01",
        "--due",
        "2026-11-01",
        expect=2,
    )
    assert "no reference standard" in result.output


def test_listing_valid_standards(started: Invoke) -> None:
    add_standard(started)
    assert "RS-5511" in started("standard", "list", "--on", "2025-03-04").output
    assert "RS-5511" not in started("standard", "list", "--on", "2026-03-04").output


def test_listing_standards_coming_due(started: Invoke) -> None:
    add_standard(started)
    assert (
        "RS-5511" in started("standard", "list", "--on", "2025-10-20", "--due-within", "30").output
    )
    result = started("standard", "list", "--due-within", "30", expect=2)
    assert "needs --on" in result.output


def test_listing_expired_standards(started: Invoke) -> None:
    add_standard(started)
    result = started("standard", "expired", "--on", "2025-11-14")
    assert "RS-5511" in result.output
    assert "10" in result.output


def test_a_bench_needs_its_standard_first(started: Invoke) -> None:
    result = started(
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
        expect=2,
    )
    assert "not on the book" in result.output


def test_adding_a_bench(kitted: Invoke) -> None:
    result = kitted("bench", "list")
    assert "B2" in result.output
    assert "north wall" in result.output


def test_moving_a_standard_onto_a_bench(kitted: Invoke) -> None:
    add_standard(kitted, "RS-7002")
    result = kitted("bench", "restandard", "B2", "RS-7002")
    assert "now runs against RS-7002" in result.output
    assert "RS-7002" in kitted("bench", "show", "B2").output


def test_restandarding_onto_something_that_is_not_there(kitted: Invoke) -> None:
    result = kitted("bench", "restandard", "B2", "RS-0000", expect=2)
    assert "no reference standard" in result.output


def test_showing_a_bench(kitted: Invoke) -> None:
    result = kitted("bench", "show", "B2")
    assert "north wall" in result.output
    assert "NVLAP-5511" in result.output
    assert "0.02 percent" in result.output


def test_listing_benches_in_service_on_a_day(kitted: Invoke) -> None:
    assert "B2" in kitted("bench", "list", "--on", "2025-01-01").output
    assert "B2" not in kitted("bench", "list", "--on", "2017-01-01").output


@pytest.fixture
def busy(kitted: Invoke) -> Invoke:
    kitted(
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
    for n in range(3):
        kitted(
            "meter",
            "receive",
            f"84-11930{n}",
            "--type",
            "Halvern/R4S",
            "--acquired",
            "2015-01-01",
        )
        kitted("work", "raise", f"WO-{n}", "test", f"84-11930{n}", "--on", "2025-03-04")
    return kitted


def test_a_day_is_planned(busy: Invoke) -> None:
    result = busy("bench", "day", "--on", "2025-03-04")
    assert "B2" in result.output
    assert "84-119300" in result.output
    assert "3 placed" in result.output


def test_what_will_not_fit_is_named(busy: Invoke) -> None:
    busy(
        "bench",
        "add",
        "B3",
        "small",
        "--positions",
        "1",
        "--standard",
        "RS-5511",
        "--max-amps",
        "100",
        "--max-volts",
        "480",
        "--installed",
        "2010-01-01",
    )
    result = busy("bench", "day", "--on", "2025-03-04")
    assert "3 placed" in result.output


def test_a_day_with_more_work_than_positions(kitted: Invoke) -> None:
    kitted(
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
    for n in range(9):
        kitted(
            "meter",
            "receive",
            f"84-11930{n}",
            "--type",
            "Halvern/R4S",
            "--acquired",
            "2015-01-01",
        )
        kitted("work", "raise", f"WO-{n}", "test", f"84-11930{n}", "--on", "2025-03-04")
    result = kitted("bench", "day", "--on", "2025-03-04", expect=1)
    assert "could not place" in result.output
    assert "is full" in result.output


def test_a_day_filtered_to_one_bench(busy: Invoke) -> None:
    assert "84-119300" in busy("bench", "day", "--on", "2025-03-04", "--bench", "b2").output
    assert "84-119300" not in busy("bench", "day", "--on", "2025-03-04", "--bench", "B9").output


def test_a_day_with_no_usable_bench(busy: Invoke) -> None:
    result = busy("bench", "day", "--on", "2036-01-01", expect=2)
    assert "no bench can be used" in result.output


def test_the_capacity_command(kitted: Invoke) -> None:
    result = kitted("bench", "capacity", "--on", "2025-03-04")
    assert "8 positions" in result.output
    assert "yes" in result.output


def test_capacity_says_why_a_bench_is_out(kitted: Invoke) -> None:
    result = kitted("bench", "capacity", "--on", "2036-01-01")
    assert "out of certificate" in result.output
    assert "0 positions" in result.output
