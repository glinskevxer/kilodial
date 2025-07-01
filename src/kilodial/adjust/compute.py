"""Turning an error and a period into money the customer can check.

The arithmetic is not hard and it is easy to do in a way nobody can audit. Three
choices here are about auditability rather than about accuracy:

The total is computed once, from the whole period's billed amount, and then
split across the billing months. Computing each month separately and adding them
up gives a total that can be a few cents off the direct calculation, and a
customer who checks it will find that difference and reasonably ask what else is
approximate.

A billing month that only partly overlaps the period is prorated by days. That
is what every tariff says and it is wrong in a mild, well understood way, since
usage is not flat across a month. It is defensible because it is the same
assumption for everybody.

Interest runs on a refund only, from the end of each billing month to the day of
the adjustment. Not on a back bill, because the tariff does not let the utility
charge a customer interest for the utility's own meter being slow.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from kilodial.adjust.period import Period
from kilodial.adjust.rules import STATE_TARIFF, Direction, Tariff, direction_of, error_share
from kilodial.errors import RuleError
from kilodial.install.multiplier import InstalledAccuracy
from kilodial.units.money import Money
from kilodial.units.span import DateSpan, parse_date

DAYS_IN_YEAR = Decimal("365")
MONTHS_IN_YEAR = Decimal("12")


@dataclass(frozen=True)
class BilledMonth:
    """What the customer was actually billed over one period."""

    span: DateSpan
    amount: Money

    @classmethod
    def of(cls, first: object, last: object, amount: object) -> BilledMonth:
        return cls(DateSpan(first, last), Money(amount))

    def share_over(self, window: DateSpan) -> Money:
        """The part of this bill that falls inside a window, prorated by days."""
        overlap = self.span.intersect(window)
        if overlap is None:
            return Money.zero()
        if overlap.days == self.span.days:
            return self.amount
        return self.amount.scaled(Decimal(overlap.days) / Decimal(self.span.days))

    def __str__(self) -> str:
        return f"{self.span} {self.amount}"


@dataclass(frozen=True)
class Line:
    """One billing month of an adjustment."""

    span: DateSpan
    billed: Money
    moved: Money
    interest: Money

    @property
    def total(self) -> Money:
        return self.moved + self.interest

    def __str__(self) -> str:
        return f"{self.span} billed {self.billed} moved {self.moved}"


@dataclass(frozen=True)
class Adjustment:
    """The whole adjustment, ready to be argued about."""

    point_code: str
    meter_serial: str
    direction: Direction
    period: Period
    share: Decimal
    lines: tuple[Line, ...]
    tariff: Tariff
    computed_on: date

    @property
    def billed(self) -> Money:
        return _sum(line.billed for line in self.lines)

    @property
    def moved(self) -> Money:
        return _sum(line.moved for line in self.lines)

    @property
    def interest(self) -> Money:
        return _sum(line.interest for line in self.lines)

    @property
    def total(self) -> Money:
        return self.moved + self.interest

    def explain(self) -> str:
        return (
            f"{self.direction} of {self.total} on {self.point_code} over "
            f"{self.period.span}, {self.billed} billed at "
            f"{(self.share * 100).quantize(Decimal('0.0001'))} percent"
        )

    def __str__(self) -> str:
        return self.explain()


def _sum(amounts: object) -> Money:
    total = Money.zero()
    for amount in amounts:  # type: ignore[attr-defined]
        total = total + amount
    return total


def compute(
    *,
    point_code: str,
    meter_serial: str,
    accuracy: InstalledAccuracy,
    period: Period,
    billed: list[BilledMonth],
    on: object,
    tariff: Tariff = STATE_TARIFF,
) -> Adjustment:
    """Work out the money, month by month, from the billed history."""
    direction = direction_of(accuracy)
    if not direction.moves_money:
        raise RuleError("an installation registering exactly a hundred owes nobody anything")
    if not billed:
        raise RuleError("there is no billed history to adjust")
    share = abs(error_share(accuracy))
    computed = parse_date(on)
    pieces = period.months
    attributed = [_billed_over(billed, piece) for piece in pieces]
    total_billed = _sum(attributed)
    if total_billed.is_zero:
        raise RuleError(f"nothing was billed on {point_code} over {period.span}, so nothing moves")
    moved_total = total_billed.scaled(share)
    weights = [amount.cents for amount in attributed]
    moved = moved_total.split(weights)
    lines = []
    for piece, was_billed, amount in zip(pieces, attributed, moved, strict=True):
        lines.append(
            Line(
                span=piece,
                billed=was_billed,
                moved=amount,
                interest=_interest(amount, piece, computed, direction, tariff),
            )
        )
    return Adjustment(
        point_code=point_code.strip().upper(),
        meter_serial=meter_serial.strip().upper(),
        direction=direction,
        period=period,
        share=share,
        lines=tuple(lines),
        tariff=tariff,
        computed_on=computed,
    )


def _billed_over(billed: list[BilledMonth], window: DateSpan) -> Money:
    return _sum(month.share_over(window) for month in billed)


def _interest(
    amount: Money, piece: DateSpan, on: date, direction: Direction, tariff: Tariff
) -> Money:
    """Simple interest on a refund, from the end of the month to the adjustment."""
    if direction is not Direction.REFUND or tariff.refund_interest == 0:
        return Money.zero()
    end = piece.end
    if end is None or end >= on:
        return Money.zero()
    days = Decimal((on - end).days)
    return amount.scaled(tariff.refund_interest * days / DAYS_IN_YEAR)


__all__ = ["DAYS_IN_YEAR", "MONTHS_IN_YEAR", "Adjustment", "BilledMonth", "Line", "compute"]
