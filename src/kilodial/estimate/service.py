"""Working an estimate out off the book, and offering every basis that holds.

The service does not pick a basis. It works out which ones the book can support
for a given gap and hands them all back with their figures, because choosing
between them is a judgement somebody signs their name to and a program that made
that choice quietly would be making it in the dark.

What it does do is find the gap. For a tampered service point that is the period
the confirmed findings cover, clipped to the days a meter was actually set,
because a period with no meter on it at all is a different problem and one this
package does not price.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from kilodial.errors import RuleError, ShopError
from kilodial.estimate.basis import (
    Basis,
    Estimate,
    from_last_year,
    from_metered,
    from_neighbours,
)
from kilodial.model.reading import consumption
from kilodial.store.shop import Shop
from kilodial.units.money import Money
from kilodial.units.span import DateSpan


@dataclass(frozen=True)
class Options:
    """Every estimate the book can support for one gap, strongest first."""

    point_code: str
    span: DateSpan
    offered: tuple[Estimate, ...]
    refused: tuple[tuple[Basis, str], ...]

    @property
    def has_any(self) -> bool:
        return bool(self.offered)

    def best(self) -> Estimate:
        """The strongest offer, refusing rather than inventing one."""
        if not self.offered:
            raise RuleError(
                f"nothing on the book supports an estimate for {self.point_code} over {self.span}"
            )
        return self.offered[0]

    def spread(self) -> Money:
        """How far apart the offers are, which is the argument in one number."""
        if len(self.offered) < 2:
            return Money.zero()
        amounts = [e.amount.cents for e in self.offered]
        return Money.from_cents(max(amounts) - min(amounts))

    def show(self) -> str:
        return (
            f"{self.point_code} over {self.span}: {len(self.offered)} bases, "
            f"{len(self.refused)} refused"
        )

    def __str__(self) -> str:
        return self.show()


def gap_for(shop: Shop, point_code: str, *, on: object) -> DateSpan:
    """The period confirmed interference covered at a point, clipped to a meter set.

    The findings say when the interference ran. The installation history says
    when there was a meter there to be interfered with. The overlap is what can
    be estimated, and a point with no overlap has a records problem rather than
    an estimate.
    """
    code = point_code.strip().upper()
    confirmed = shop.tamper.confirmed_at(code, on)
    if not confirmed:
        raise RuleError(f"nothing is confirmed at {code}, so there is no gap to estimate")
    spans = [f.span() for f in confirmed]
    start = min(s.start for s in spans)
    ends = [s.end for s in spans if s.end is not None]
    if not ends:
        raise RuleError(f"the findings at {code} have no end between them")
    whole = DateSpan(start, max(ends))
    covered = [s.span.intersect(whole) for s in shop.installs.covering(code, whole)]
    live = [s for s in covered if s is not None]
    if not live:
        raise RuleError(f"no meter was set at {code} over {whole}")
    return DateSpan(min(s.start for s in live), whole.end)


def daily_metered(shop: Shop, point_code: str, span: DateSpan) -> Decimal:
    """What the register counted per day on the readings around a gap.

    Both readings have to be on the same meter, which is what makes this the
    strongest basis when it is available and unavailable at all when it is not:
    a service whose meter was taken away has no pair to work from.
    """
    code = point_code.strip().upper()
    readings = [r for r in shop.readings.for_point(code) if not span.contains(r.read_on)]
    if len(readings) < 2:
        raise RuleError(
            f"{code} has {len(readings)} readings outside {span}, which is not "
            "enough to meter either side of it"
        )
    first, last = readings[0], readings[-1]
    if first.meter_serial != last.meter_serial:
        raise RuleError(f"the readings around {span} are off different meters, so they do not pair")
    found = consumption(first, last)
    if found.days <= 0:
        raise RuleError(f"the readings around {span} are on the same day")
    return (found.billed_units / found.days).quantize(Decimal("0.001"))


def options_for(
    shop: Shop,
    point_code: str,
    span: DateSpan,
    *,
    note: object = None,
    rate_per_kwh: object = None,
) -> Options:
    """Every estimate the book can support for a gap.

    ``rate_per_kwh`` unlocks the metered basis. Without it the register readings
    cannot be turned into money and the basis is refused by name rather than
    silently left off the list.
    """
    code = point_code.strip().upper()
    billed = shop.billing.for_point(code)
    offered: list[Estimate] = []
    refused: list[tuple[Basis, str]] = []
    if rate_per_kwh is None:
        refused.append(
            (Basis.METERED, "no energy rate was given, so the readings cannot be priced")
        )
    else:
        try:
            offered.append(
                from_metered(
                    code,
                    daily_metered(shop, code, span),
                    span,
                    rate_per_kwh=rate_per_kwh,
                    note=note,
                )
            )
        except ShopError as exc:
            refused.append((Basis.METERED, str(exc)))
    for basis, build in (
        (Basis.LAST_YEAR, from_last_year),
        (Basis.NEIGHBOURS, from_neighbours),
    ):
        try:
            offered.append(build(code, billed, span, note=note))
        except ShopError as exc:
            refused.append((basis, str(exc)))
    offered.sort(key=lambda e: (-e.basis.strength, -e.amount.cents))
    return Options(code, span, tuple(offered), tuple(refused))


def estimate_point(
    shop: Shop,
    point_code: str,
    *,
    on: object,
    note: object = None,
    rate_per_kwh: object = None,
) -> Options:
    """Find the gap at a point and work out what can be said about it."""
    span = gap_for(shop, point_code, on=on)
    return options_for(shop, point_code, span, note=note, rate_per_kwh=rate_per_kwh)


__all__ = ["Options", "daily_metered", "estimate_point", "gap_for", "options_for"]
