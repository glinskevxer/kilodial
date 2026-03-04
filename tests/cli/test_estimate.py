from __future__ import annotations

from pathlib import Path

import pytest

from kilodial.adjust.compute import BilledMonth
from kilodial.store.shop import open_shop
from kilodial.tools.smoke import LAST_DAY, stand_up
from tests.cli.conftest import Invoke


@pytest.fixture
def stocked(invoke: Invoke, book: Path) -> Invoke:
    invoke("init")
    with open_shop(book) as shop:
        stand_up(shop)
        for index in range(1, 13):
            last = LAST_DAY.get(index, 30 if index in (9, 11) else 31)
            shop.billing.add(
                "SP-1042",
                BilledMonth.of(f"2024-{index:02d}-01", f"2024-{index:02d}-{last}", "100.00"),
            )
    return invoke


def confirm(invoke: Invoke, kind: str = "bypass") -> None:
    invoke(
        "tamper",
        "log",
        "TF-1",
        "SP-1042",
        kind,
        "--on",
        "2025-05-31",
        "--by",
        "R Ellis",
    )
    invoke(
        "tamper",
        "confirm",
        "TF-1",
        "--on",
        "2025-05-31",
        "--since",
        "2025-03-01",
        "--evidence",
        "jumper",
    )


def test_the_gap_command(stocked: Invoke) -> None:
    confirm(stocked)
    result = stocked("estimate", "gap", "SP-1042", "--on", "2025-12-31")
    assert "2025-03-01 to 2025-05-31" in result.output
    assert "92" in result.output


def test_a_gap_with_nothing_confirmed(stocked: Invoke) -> None:
    result = stocked("estimate", "gap", "SP-1042", "--on", "2025-12-31", expect=2)
    assert "nothing is confirmed" in result.output


def test_listing_the_bases_for_a_found_gap(stocked: Invoke) -> None:
    confirm(stocked)
    result = stocked("estimate", "list", "SP-1042", "--on", "2025-12-31")
    assert "same period last year" in result.output
    assert "neighbouring periods" in result.output
    assert "spread" in result.output


def test_listing_the_bases_for_a_period_given_by_hand(stocked: Invoke) -> None:
    result = stocked("estimate", "list", "SP-1042", "--from", "2025-03-01", "--to", "2025-05-31")
    assert "2 bases, 0 refused" in result.output


def test_a_basis_the_history_cannot_support_is_named(stocked: Invoke, book: Path) -> None:
    with open_shop(book) as shop:
        for month in shop.billing.for_point("SP-1042"):
            shop.billing.delete("SP-1042", month.span.start)
    result = stocked(
        "estimate",
        "list",
        "SP-1042",
        "--from",
        "2025-03-01",
        "--to",
        "2025-05-31",
        expect=1,
    )
    assert "no same period last year" in result.output
    assert "0 bases, 2 refused" in result.output


def test_the_list_needs_a_period_from_somewhere(stocked: Invoke) -> None:
    result = stocked("estimate", "list", "SP-1042", expect=2)
    assert "either --on or both --from and --to" in result.output


def test_estimating_from_connected_load(stocked: Invoke) -> None:
    result = stocked(
        "estimate",
        "load",
        "SP-1042",
        "--from",
        "2025-03-01",
        "--to",
        "2025-03-10",
        "--kw",
        "10",
        "--duty",
        "0.5",
        "--rate",
        "0.12",
        "--note",
        "shop compressor",
    )
    assert "connected load" in result.output
    assert "$144.00" in result.output
    assert "shop compressor" in result.output


def test_a_duty_cycle_over_one(stocked: Invoke) -> None:
    result = stocked(
        "estimate",
        "load",
        "SP-1042",
        "--from",
        "2025-03-01",
        "--to",
        "2025-03-10",
        "--kw",
        "10",
        "--duty",
        "2",
        "--rate",
        "0.12",
        expect=2,
    )
    assert "cannot be over one" in result.output


def test_estimating_a_point_nobody_has(stocked: Invoke) -> None:
    result = stocked(
        "estimate",
        "load",
        "SP-9999",
        "--from",
        "2025-03-01",
        "--to",
        "2025-03-10",
        "--kw",
        "10",
        "--duty",
        "0.5",
        "--rate",
        "0.12",
        expect=2,
    )
    assert "no service point" in result.output


def test_the_bases_command(stocked: Invoke) -> None:
    result = stocked("estimate", "bases")
    assert result.output.splitlines()[2].startswith("same period last year")
    assert "connected load" in result.output


def test_settling_an_estimate(stocked: Invoke) -> None:
    confirm(stocked)
    result = stocked(
        "estimate",
        "settle",
        "ES-1",
        "SP-1042",
        "--basis",
        "same period last year",
        "--on",
        "2025-12-31",
        "--settled-on",
        "2025-12-31",
        "--by",
        "M Okafor",
    )
    assert "settled by M Okafor" in result.output
    assert "ES-1" in stocked("estimate", "settled", "SP-1042").output


def test_a_basis_the_book_does_not_support(stocked: Invoke, book: Path) -> None:
    with open_shop(book) as shop:
        for month in shop.billing.for_point("SP-1042"):
            shop.billing.delete("SP-1042", month.span.start)
    confirm(stocked)
    result = stocked(
        "estimate",
        "settle",
        "ES-1",
        "SP-1042",
        "--basis",
        "same period last year",
        "--on",
        "2025-12-31",
        "--settled-on",
        "2025-12-31",
        "--by",
        "M Okafor",
        expect=2,
    )
    assert "not one of the bases" in result.output


def test_a_basis_nobody_uses(stocked: Invoke) -> None:
    confirm(stocked)
    result = stocked(
        "estimate",
        "settle",
        "ES-1",
        "SP-1042",
        "--basis",
        "guesswork",
        "--on",
        "2025-12-31",
        "--settled-on",
        "2025-12-31",
        "--by",
        "M Okafor",
        expect=2,
    )
    assert "not a basis an estimate can rest on" in result.output


def test_settling_needs_a_period_from_somewhere(stocked: Invoke) -> None:
    result = stocked(
        "estimate",
        "settle",
        "ES-1",
        "SP-1042",
        "--basis",
        "neighbouring periods",
        "--settled-on",
        "2025-12-31",
        "--by",
        "M Okafor",
        expect=2,
    )
    assert "either --on or both --from and --to" in result.output


def test_settling_from_a_period_given_by_hand(stocked: Invoke) -> None:
    stocked(
        "estimate",
        "settle",
        "ES-1",
        "SP-1042",
        "--basis",
        "neighbouring periods",
        "--from",
        "2025-03-01",
        "--to",
        "2025-05-31",
        "--settled-on",
        "2025-12-31",
        "--by",
        "M Okafor",
    )
    assert "neighbouring periods" in stocked("estimate", "settled", "SP-1042").output


def test_a_settled_estimate_leaves_a_line_in_the_log(stocked: Invoke) -> None:
    confirm(stocked)
    stocked(
        "estimate",
        "settle",
        "ES-1",
        "SP-1042",
        "--basis",
        "same period last year",
        "--on",
        "2025-12-31",
        "--settled-on",
        "2025-12-31",
        "--by",
        "M Okafor",
    )
    assert "estimated" in stocked("book", "history").output


def test_settled_estimates_at_a_point_with_none(stocked: Invoke) -> None:
    assert "$0.00 settled at SP-1042" in stocked("estimate", "settled", "SP-1042").output
