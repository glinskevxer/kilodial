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


def log(invoke: Invoke, kind: str = "seal cut", reference: str = "TF-1") -> str:
    return invoke(
        "tamper",
        "log",
        reference,
        "SP-1042",
        kind,
        "--on",
        "2025-06-30",
        "--by",
        "R Ellis",
        "--evidence",
        "seal wire hanging",
    ).output


def test_logging_a_suspicion(stocked: Invoke) -> None:
    assert "nothing moves until it is confirmed" in log(stocked)
    assert "TF-1" in stocked("tamper", "list").output


def test_a_kind_nobody_finds(stocked: Invoke) -> None:
    result = stocked(
        "tamper",
        "log",
        "TF-1",
        "SP-1042",
        "vandalism",
        "--on",
        "2025-06-30",
        "--by",
        "R Ellis",
        expect=2,
    )
    assert "not a tamper finding" in result.output


def test_a_point_nobody_has(stocked: Invoke) -> None:
    result = stocked(
        "tamper",
        "log",
        "TF-1",
        "SP-9999",
        "seal cut",
        "--on",
        "2025-06-30",
        "--by",
        "R Ellis",
        expect=2,
    )
    assert "not on the book" in result.output


def test_confirming(stocked: Invoke) -> None:
    log(stocked)
    result = stocked(
        "tamper",
        "confirm",
        "TF-1",
        "--on",
        "2025-07-01",
        "--since",
        "2024-01-01",
        "--evidence",
        "seal replaced by a copper wire",
    )
    assert "confirmed over 2024-01-01 to 2025-06-30" in result.output
    assert "TF-1" not in stocked("tamper", "list").output
    assert "TF-1" in stocked("tamper", "list", "--all").output


def test_confirming_a_bypass_says_the_usage_has_to_be_estimated(stocked: Invoke) -> None:
    log(stocked, "bypass")
    result = stocked(
        "tamper",
        "confirm",
        "TF-1",
        "--on",
        "2025-07-01",
        "--since",
        "2024-01-01",
        "--evidence",
        "jumper on the load side",
    )
    assert "has to be estimated" in result.output


def test_interference_cannot_start_after_it_was_found(stocked: Invoke) -> None:
    log(stocked)
    result = stocked(
        "tamper",
        "confirm",
        "TF-1",
        "--on",
        "2025-07-01",
        "--since",
        "2026-01-01",
        "--evidence",
        "x",
        expect=2,
    )
    assert "started after it was found" in result.output


def test_clearing(stocked: Invoke) -> None:
    log(stocked)
    stocked("tamper", "clear", "TF-1", "--on", "2025-07-01", "--why", "tree crew cut it")
    result = stocked("tamper", "show", "TF-1")
    assert "cleared" in result.output
    assert "tree crew cut it" in result.output


def test_settling_a_settled_finding(stocked: Invoke) -> None:
    log(stocked)
    stocked("tamper", "clear", "TF-1", "--on", "2025-07-01", "--why", "tree crew")
    result = stocked(
        "tamper",
        "confirm",
        "TF-1",
        "--on",
        "2025-07-02",
        "--since",
        "2024-01-01",
        "--evidence",
        "x",
        expect=2,
    )
    assert "already cleared" in result.output


def test_listing_by_point_and_window(stocked: Invoke) -> None:
    log(stocked)
    assert "TF-1" in stocked("tamper", "list", "--point", "sp-1042").output
    assert "TF-1" in stocked("tamper", "list", "--from", "2025-01-01", "--to", "2025-12-31").output
    assert (
        "TF-1" not in stocked("tamper", "list", "--from", "2024-01-01", "--to", "2024-12-31").output
    )
    result = stocked("tamper", "list", "--from", "2025-01-01", expect=2)
    assert "both --from and --to" in result.output


def test_a_confirmed_finding_lengthens_the_adjustment(stocked: Invoke) -> None:
    stocked(
        "run",
        "record",
        "TR-1",
        "--meter",
        "84-119302",
        "--bench",
        "B2",
        "--on",
        "2025-06-30",
        "--by",
        "R Ellis",
        "--fl",
        "96.00",
        "--ll",
        "96.00",
    )
    before = stocked("adjust", "period", "SP-1042").output
    log(stocked)
    stocked(
        "tamper",
        "confirm",
        "TF-1",
        "--on",
        "2025-07-01",
        "--since",
        "2023-01-01",
        "--evidence",
        "copper wire",
    )
    after = stocked("adjust", "period", "SP-1042").output
    assert "2024-06-30" in before
    assert "2022-06-30" in after


def test_a_confirmed_bypass_stops_the_adjustment(stocked: Invoke) -> None:
    stocked(
        "run",
        "record",
        "TR-1",
        "--meter",
        "84-119302",
        "--bench",
        "B2",
        "--on",
        "2025-06-30",
        "--by",
        "R Ellis",
        "--fl",
        "96.00",
        "--ll",
        "96.00",
    )
    log(stocked, "bypass")
    stocked(
        "tamper",
        "confirm",
        "TF-1",
        "--on",
        "2025-07-01",
        "--since",
        "2023-01-01",
        "--evidence",
        "jumper",
    )
    result = stocked("adjust", "show", "SP-1042", "--on", "2025-07-15")
    assert "has to be estimated" in result.output


def test_the_kinds_command(stocked: Invoke) -> None:
    result = stocked("tamper", "kinds")
    assert "bypass" in result.output
    assert "stops measuring" in result.output
