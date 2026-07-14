"""Importing billed history out of the billing system's extract.

This is the least interesting file in the package and the one that has to be
most careful, because everything downstream of it is money. Three habits:

Nothing is inferred. If the extract has no end date for a period, the row is
skipped rather than having an end guessed from the next row's start. Guessing
would work almost always and be wrong at exactly the point where a customer
moved out mid month, which is exactly the case somebody is checking.

Overlaps are refused by the repository, and the refusal is reported per row
rather than aborting. An extract that overlaps something already on the book is
usually a re-run of a file that was already loaded, and the useful output is the
list of what was already there.

Amounts go through Money, which accepts the parentheses and dollar signs a
billing extract puts in and refuses everything else.
"""

from __future__ import annotations

from pathlib import Path

from kilodial.adjust.compute import BilledMonth
from kilodial.errors import ShopError
from kilodial.ingest.sheet import Outcome, Row, Sheet, read_file, read_text
from kilodial.store.shop import Shop
from kilodial.units.money import Money
from kilodial.units.span import DateSpan

REQUIRED = ["point", "from", "to", "amount"]


def month_from(row: Row) -> tuple[str, BilledMonth, str | None]:
    """One billing period out of one row, with the point it belongs to."""
    return (
        row.need("point"),
        BilledMonth(
            span=DateSpan(row.need("from"), row.need("to")),
            amount=Money(row.need("amount")),
        ),
        row.get("kwh"),
    )


def load(shop: Shop, sheet: Sheet) -> Outcome:
    """Put every billing period that can be read onto the book."""
    taken = 0
    skipped: list[tuple[int, str]] = []
    for row in sheet:
        try:
            code, month, kwh = month_from(row)
        except ShopError as exc:
            skipped.append((row.line, str(exc)))
            continue
        try:
            shop.billing.add(code, month, kwh=kwh)
        except ShopError as exc:
            skipped.append((row.line, str(exc)))
            continue
        taken += 1
    return Outcome(taken, tuple(skipped))


def load_text(shop: Shop, text: str) -> Outcome:
    """Import a billing extract held in a string."""
    return load(shop, read_text(text, required=REQUIRED))


def load_file(shop: Shop, path: str | Path) -> Outcome:
    """Import a billing extract off disk."""
    return load(shop, read_file(path, required=REQUIRED))


def total_loaded(shop: Shop, point_code: str) -> Money:
    """What a point's whole billed history adds to, for a sanity check."""
    return Money.total(m.amount for m in shop.billing.for_point(point_code))


__all__ = ["REQUIRED", "load", "load_file", "load_text", "month_from", "total_loaded"]
