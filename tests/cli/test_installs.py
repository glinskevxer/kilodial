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
    return started


def test_adding_a_point(wired: Invoke) -> None:
    assert "SP-1042" in wired("point", "list").output
    assert "18 Fenwick Row" in wired("point", "list").output


def test_a_service_nobody_runs(started: Invoke) -> None:
    result = started(
        "point",
        "add",
        "SP-1042",
        "--account",
        "44-9021",
        "--address",
        "18 Fenwick Row",
        "--service",
        "4P9W",
        "--volts",
        "240",
        "--rate",
        "R1",
        "--energised",
        "2011-06-14",
        expect=2,
    )
    assert "is not one of" in result.output


def test_setting_and_pulling_a_meter(wired: Invoke) -> None:
    wired("point", "set", "SP-1042", "84-119302", "--multiplier", "1", "--on", "2019-05-02")
    assert "84-119302" in wired("point", "list").output
    wired("point", "pull", "SP-1042", "--on", "2023-08-14")
    assert "2023-08-14" in wired("point", "history", "SP-1042").output


def test_setting_a_meter_nobody_has(wired: Invoke) -> None:
    result = wired(
        "point",
        "set",
        "SP-1042",
        "84-000000",
        "--multiplier",
        "1",
        "--on",
        "2019-05-02",
        expect=2,
    )
    assert "no meter on the book" in result.output


def test_setting_with_a_transformer_nobody_has(wired: Invoke) -> None:
    result = wired(
        "point",
        "set",
        "SP-1042",
        "84-119302",
        "--ct",
        "CT-0000",
        "--multiplier",
        "40",
        "--on",
        "2019-05-02",
        expect=2,
    )
    assert "no instrument transformer" in result.output


def test_two_meters_at_one_point(wired: Invoke) -> None:
    wired(
        "meter",
        "receive",
        "84-119303",
        "--type",
        "Halvern/R4S",
        "--acquired",
        "2019-04-02",
    )
    wired("point", "set", "SP-1042", "84-119302", "--multiplier", "1", "--on", "2019-05-02")
    result = wired(
        "point",
        "set",
        "SP-1042",
        "84-119303",
        "--multiplier",
        "1",
        "--on",
        "2021-01-01",
        expect=2,
    )
    assert "already set at SP-1042" in result.output


def test_pulling_nothing(wired: Invoke) -> None:
    result = wired("point", "pull", "SP-1042", "--on", "2023-08-14", expect=2)
    assert "nothing is set" in result.output


def test_disconnecting_a_point(wired: Invoke) -> None:
    wired("point", "disconnect", "SP-1042", "--on", "2024-02-01")
    assert "SP-1042" not in wired("point", "list", "--on", "2024-06-01").output
    assert "SP-1042" in wired("point", "list", "--on", "2023-06-01").output


def test_listing_by_account(wired: Invoke) -> None:
    assert "SP-1042" in wired("point", "list", "--account", "44-9021").output
    assert "SP-1042" not in wired("point", "list", "--account", "44-0000").output


def test_accuracy_of_a_self_contained_installation(wired: Invoke) -> None:
    wired("point", "set", "SP-1042", "84-119302", "--multiplier", "1", "--on", "2019-05-02")
    wired(
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
        "--fl",
        "100.30",
        "--ll",
        "100.30",
    )
    result = wired("point", "accuracy", "SP-1042")
    assert "100.30%" in result.output
    assert "multiplier right" in result.output
    assert "yes" in result.output


def test_accuracy_of_a_transformer_rated_installation(wired: Invoke) -> None:
    wired(
        "xfmr",
        "add",
        "CT-8841",
        "--kind",
        "current",
        "--maker",
        "Ferrand",
        "--ratio",
        "40",
        "--accuracy",
        "0.3",
        "--rcf",
        "1.0020",
        "--minutes",
        "0",
        "--tested",
        "2024-05-01",
    )
    wired(
        "point",
        "set",
        "SP-1042",
        "84-119302",
        "--ct",
        "CT-8841",
        "--multiplier",
        "40",
        "--on",
        "2019-05-02",
    )
    wired(
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
        "--fl",
        "100.30",
        "--ll",
        "100.30",
    )
    result = wired("point", "accuracy", "SP-1042")
    assert "current transformer" in result.output
    assert "SP-1042" in wired("xfmr", "where", "CT-8841").output


def test_a_multiplier_typed_in_wrong_is_a_finding(wired: Invoke) -> None:
    wired(
        "xfmr",
        "add",
        "CT-8841",
        "--kind",
        "current",
        "--maker",
        "Ferrand",
        "--ratio",
        "40",
        "--accuracy",
        "0.3",
        "--rcf",
        "1.0000",
        "--tested",
        "2024-05-01",
    )
    wired(
        "point",
        "set",
        "SP-1042",
        "84-119302",
        "--ct",
        "CT-8841",
        "--multiplier",
        "20",
        "--on",
        "2019-05-02",
    )
    wired(
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
        "--fl",
        "100.00",
        "--ll",
        "100.00",
    )
    result = wired("point", "accuracy", "SP-1042", expect=1)
    assert "programmed multiplier 20 against a computed 40" in result.output
    assert "50.00%" in result.output


def test_accuracy_with_nothing_set(wired: Invoke) -> None:
    result = wired("point", "accuracy", "SP-1042", expect=2)
    assert "nothing was set" in result.output


def test_accuracy_of_a_meter_that_was_never_tested(wired: Invoke) -> None:
    wired("point", "set", "SP-1042", "84-119302", "--multiplier", "1", "--on", "2019-05-02")
    result = wired("point", "accuracy", "SP-1042", expect=2)
    assert "no usable as found run" in result.output
