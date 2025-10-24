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
    started("meter", "receive", "84-220001", "--type", "Vantage/SM3", "--acquired", "2019-04-02")
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
        "--polyphase",
        "--installed",
        "2010-01-01",
    )
    return started


def certify(invoke: Invoke, badge: str = "T-441", grade: str = "bench", **over: str) -> None:
    invoke(
        "tech",
        "add",
        badge,
        over.get("name", "R Ellis"),
        "--grade",
        grade,
        "--certified",
        over.get("certified", "2023-01-01"),
        "--due",
        over.get("due", "2029-01-01"),
    )


def test_adding_a_technician(wired: Invoke) -> None:
    certify(wired)
    assert "T-441" in wired("tech", "list").output
    assert "bench" in wired("tech", "list").output


def test_a_grade_nobody_awards(wired: Invoke) -> None:
    result = wired(
        "tech",
        "add",
        "T-441",
        "R Ellis",
        "--grade",
        "apprentice",
        "--certified",
        "2023-01-01",
        "--due",
        "2029-01-01",
        expect=2,
    )
    assert "not a certification grade" in result.output


def test_recertifying_and_promoting(wired: Invoke) -> None:
    certify(wired)
    result = wired(
        "tech",
        "recertify",
        "T-441",
        "--certified",
        "2029-01-01",
        "--due",
        "2032-01-01",
        "--grade",
        "supervisor",
    )
    assert "as supervisor" in result.output
    assert "2032-01-01" in wired("tech", "list").output


def test_listing_by_day_and_grade(wired: Invoke) -> None:
    certify(wired, "T-441", "bench")
    certify(wired, "T-902", "supervisor", name="M Okafor")
    assert "T-902" in wired("tech", "list", "--grade", "supervisor").output
    assert "T-441" not in wired("tech", "list", "--grade", "supervisor").output
    assert "T-441" in wired("tech", "list", "--on", "2025-03-04").output
    assert "T-441" not in wired("tech", "list", "--on", "2030-03-04").output


def test_listing_what_is_coming_due(wired: Invoke) -> None:
    certify(wired)
    assert "T-441" in wired("tech", "list", "--on", "2028-12-01", "--due-within", "60").output
    result = wired("tech", "list", "--due-within", "60", expect=2)
    assert "needs --on" in result.output


def test_lapsed_certifications(wired: Invoke) -> None:
    certify(wired, "T-441", "bench", due="2024-01-01")
    result = wired("tech", "lapsed", "--on", "2024-01-11")
    assert "T-441" in result.output
    assert "10" in result.output


def test_may_sign(wired: Invoke) -> None:
    certify(wired)
    result = wired("tech", "may", "T-441", "84-119302", "--on", "2025-03-04")
    assert "may sign" in result.output
    assert "yes" in result.output


def test_may_not_sign_polyphase(wired: Invoke) -> None:
    certify(wired)
    result = wired("tech", "may", "T-441", "84-220001", "--on", "2025-03-04", expect=1)
    assert "is polyphase" in result.output


def test_may_not_sign_a_referee_run(wired: Invoke) -> None:
    certify(wired, "T-902", "polyphase", name="M Okafor")
    result = wired(
        "tech",
        "may",
        "T-902",
        "84-119302",
        "--kind",
        "referee",
        "--on",
        "2025-03-04",
        expect=1,
    )
    assert "signed by a supervisor" in result.output


def test_a_signed_run_carries_its_badge(wired: Invoke) -> None:
    certify(wired)
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
        "--badge",
        "T-441",
        "--fl",
        "100.10",
        "--ll",
        "99.80",
    )
    assert "T-441" in wired("run", "show", "TR-1").output


def test_a_run_signed_by_somebody_who_may_not_is_void(wired: Invoke) -> None:
    certify(wired, "T-441", "bench")
    output = wired(
        "run",
        "record",
        "TR-1",
        "--meter",
        "84-220001",
        "--bench",
        "B2",
        "--on",
        "2025-03-04",
        "--by",
        "R Ellis",
        "--badge",
        "T-441",
        "--fl",
        "100.10",
        "--ll",
        "99.80",
        "--pf",
        "99.90",
    ).output
    assert "void" in output


def test_the_grades_command(wired: Invoke) -> None:
    result = wired("tech", "grades")
    assert "supervisor" in result.output
    assert "polyphase" in result.output
