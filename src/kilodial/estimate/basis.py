"""Estimating a period nobody metered, and saying how the number was arrived at.

When a meter has been bypassed, or was missing, or ran backwards, there is no
registration to correct. There is a period with usage in it and nothing on the
book that measured it, and the utility has to put a number on it anyway.

Three ways of doing that are defensible and they are defensible for different
reasons, so the basis is recorded alongside the figure rather than folded into
it. A customer arguing about an estimate is arguing about the basis, and an
estimate that arrives as a bare total gives them nothing to argue with, which
looks like confidence and reads like evasion.

  metered either side     the strongest of all where it is available, because it
                          is not an inference about money at all: it is the
                          energy the register actually counted on the days
                          around the gap, priced at the tariff rate. It needs
                          real readings either side, which a service whose meter
                          was missing does not have.

  same period last year   the next strongest, because it carries the season with
                          it.
                          Useless on a service that changed hands or changed
                          load, and there is no way to tell from here that it
                          did, so it is offered rather than assumed.

  neighbouring periods    the daily rate either side of the gap, applied across
                          it. Handles a service whose load is steady and gets
                          winter badly wrong on electric heat.

  connected load          nameplate kilowatts times a stated duty cycle. The
                          weakest and the only one available when there is no
                          history at all, which is exactly the bypass case where
                          the meter was interfered with from the day it was set.

Nothing here picks between them. That is a judgement with a person's name on it.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass
from decimal import Decimal

from kilodial.adjust.compute import BilledMonth
from kilodial.errors import RuleError
from kilodial.units.money import Money
from kilodial.units.span import DateSpan
from kilodial.units.text import optional, positive

HOURS_PER_DAY = Decimal("24")


class Basis(enum.Enum):
    """How an estimate was arrived at."""

    LAST_YEAR = ("same period last year", 3)
    NEIGHBOURS = ("neighbouring periods", 2)
    METERED = ("metered either side", 4)
    CONNECTED_LOAD = ("connected load", 1)
    DECLARED = ("declared by the customer", 1)

    def __init__(self, label: str, strength: int) -> None:
        self.label = label
        self.strength = strength

    def __str__(self) -> str:
        return self.label


@dataclass(frozen=True)
class Estimate:
    """A figure, the period it covers, and how it was arrived at."""

    point_code: str
    span: DateSpan
    basis: Basis
    amount: Money
    working: str
    note: str | None

    @property
    def daily(self) -> Money:
        """What the estimate works out at per day, for a sanity check."""
        return self.amount.scaled(Decimal(1) / Decimal(self.span.days))

    def explain(self) -> str:
        return (
            f"{self.amount} over {self.span} ({self.span.days} days) "
            f"on {self.basis}: {self.working}"
        )

    def __str__(self) -> str:
        return self.explain()


def _outside(billed: list[BilledMonth], span: DateSpan) -> list[BilledMonth]:
    return [month for month in billed if not month.span.overlaps(span)]


def daily_rate(billed: list[BilledMonth]) -> Money:
    """The average amount per day across a set of billing periods."""
    if not billed:
        raise RuleError("there is no billed history to work a daily rate off")
    days = sum(month.span.days for month in billed)
    total = Money.zero()
    for month in billed:
        total = total + month.amount
    return total.scaled(Decimal(1) / Decimal(days))


def from_last_year(
    point_code: str, billed: list[BilledMonth], span: DateSpan, *, note: object = None
) -> Estimate:
    """Estimate a gap from the same days a year earlier."""
    if span.end is None:
        raise RuleError("an estimate needs a period with an end on it")
    earlier = span.shifted_back(12)
    covering = [m for m in billed if m.span.overlaps(earlier)]
    if not covering:
        raise RuleError(f"there is nothing billed over {earlier}, so last year is no basis")
    total = Money.zero()
    for month in covering:
        total = total + month.share_over(earlier)
    if total.is_zero:
        raise RuleError(f"nothing was billed over {earlier}, so last year is no basis")
    return Estimate(
        point_code=point_code.strip().upper(),
        span=span,
        basis=Basis.LAST_YEAR,
        amount=total,
        working=f"{total} billed over {earlier}",
        note=optional(note, "estimate note", 240),
    )


def from_neighbours(
    point_code: str, billed: list[BilledMonth], span: DateSpan, *, note: object = None
) -> Estimate:
    """Estimate a gap from the daily rate on either side of it."""
    if span.end is None:
        raise RuleError("an estimate needs a period with an end on it")
    around = _outside(billed, span)
    if not around:
        raise RuleError("every billed period overlaps the gap, so the neighbours are no basis")
    rate = daily_rate(around)
    amount = rate.scaled(Decimal(span.days))
    return Estimate(
        point_code=point_code.strip().upper(),
        span=span,
        basis=Basis.NEIGHBOURS,
        amount=amount,
        working=f"{rate} a day across {len(around)} billing periods either side",
        note=optional(note, "estimate note", 240),
    )


def from_connected_load(
    point_code: str,
    span: DateSpan,
    *,
    kilowatts: object,
    duty: object,
    rate_per_kwh: object,
    note: object = None,
) -> Estimate:
    """Estimate a gap from nameplate load and a stated duty cycle.

    ``duty`` is the share of the day the load is judged to have run, between
    nothing and one. It is the weakest number in the calculation and it is the
    one a customer will challenge, so it goes on the record rather than being
    folded into the kilowatts.
    """
    if span.end is None:
        raise RuleError("an estimate needs a period with an end on it")
    load = positive(kilowatts, "connected load")
    share = positive(duty, "duty cycle")
    if share > 1:
        raise RuleError("a duty cycle is a share of the day, so it cannot be over one")
    rate = positive(rate_per_kwh, "energy rate")
    kwh = load * HOURS_PER_DAY * share * Decimal(span.days)
    return Estimate(
        point_code=point_code.strip().upper(),
        span=span,
        basis=Basis.CONNECTED_LOAD,
        amount=Money(kwh * rate),
        working=(
            f"{load.normalize():f} kW at {share.normalize():f} duty for "
            f"{span.days} days is {kwh.normalize():f} kWh at {rate.normalize():f}"
        ),
        note=optional(note, "estimate note", 240),
    )


def from_metered(
    point_code: str,
    daily_kwh: object,
    span: DateSpan,
    *,
    rate_per_kwh: object,
    note: object = None,
) -> Estimate:
    """Estimate a gap from the energy the register counted around it.

    ``daily_kwh`` is what the meter actually recorded per day either side of the
    gap, which the caller works out from the readings. It is passed in rather
    than derived here because pairing readings across a meter change is a
    question this module has no business answering.
    """
    if span.end is None:
        raise RuleError("an estimate needs a period with an end on it")
    daily = positive(daily_kwh, "daily energy")
    rate = positive(rate_per_kwh, "energy rate")
    kwh = daily * Decimal(span.days)
    return Estimate(
        point_code=point_code.strip().upper(),
        span=span,
        basis=Basis.METERED,
        amount=Money(kwh * rate),
        working=(
            f"{daily.normalize():f} kWh a day metered either side over "
            f"{span.days} days is {kwh.normalize():f} kWh at {rate.normalize():f}"
        ),
        note=optional(note, "estimate note", 240),
    )


def declared(point_code: str, span: DateSpan, amount: object, *, note: object = None) -> Estimate:
    """Take a figure somebody has agreed, and record that it was agreed."""
    settled = Money(amount)
    if settled.cents <= 0:
        raise RuleError("a declared estimate has to be more than nothing")
    return Estimate(
        point_code=point_code.strip().upper(),
        span=span,
        basis=Basis.DECLARED,
        amount=settled,
        working="agreed rather than calculated",
        note=optional(note, "estimate note", 240),
    )


def strongest(estimates: list[Estimate]) -> Estimate:
    """The best supported of several estimates, ties broken by the larger figure."""
    if not estimates:
        raise RuleError("there are no estimates to choose between")
    return max(estimates, key=lambda e: (e.basis.strength, e.amount.cents))


__all__ = [
    "HOURS_PER_DAY",
    "Basis",
    "Estimate",
    "daily_rate",
    "declared",
    "from_connected_load",
    "from_last_year",
    "from_metered",
    "from_neighbours",
    "strongest",
]
