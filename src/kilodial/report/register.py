"""The adjustment register: every point that owes money or is owed it.

The shop finds bad meters one at a time and the money is settled in a batch, so
somebody has to produce the list. This is that list, and the awkward part is
that most of the points on it will not produce an adjustment for reasons that
are perfectly good and need to be visible: the meter is within tolerance, or
there is no billed history, or the meter was never tested.

So the register has two tables and both of them matter. The first is the money.
The second is everything the register could not price, with the reason, because
a point that is quietly missing from a refund run is the thing a customer finds
out about from somebody else.
"""

from __future__ import annotations

from dataclasses import dataclass

from kilodial.adjust.compute import Adjustment
from kilodial.adjust.rules import STATE_TARIFF, Direction, Tariff
from kilodial.adjust.service import Refusal, raise_adjustment
from kilodial.errors import ShopError
from kilodial.report.document import Document, Grid
from kilodial.store.shop import Shop
from kilodial.units.money import Money
from kilodial.units.span import parse_date

MONEY_HEADINGS = [
    "point",
    "meter",
    "direction",
    "period",
    "days",
    "billed",
    "moved",
    "interest",
    "total",
]


@dataclass(frozen=True)
class Register:
    """What a register run found."""

    priced: tuple[Adjustment, ...]
    passed_over: tuple[tuple[str, str], ...]

    @property
    def refunds(self) -> list[Adjustment]:
        return [a for a in self.priced if a.direction is Direction.REFUND]

    @property
    def back_bills(self) -> list[Adjustment]:
        return [a for a in self.priced if a.direction is Direction.BACK_BILL]

    def owed_to_customers(self) -> Money:
        return Money.total(a.total for a in self.refunds)

    def owed_to_utility(self) -> Money:
        return Money.total(a.total for a in self.back_bills)

    def net(self) -> Money:
        """Positive means the utility owes money on the whole run."""
        return self.owed_to_customers() - self.owed_to_utility()

    def show(self) -> str:
        return f"{len(self.priced)} priced, {len(self.passed_over)} passed over, net {self.net()}"

    def __str__(self) -> str:
        return self.show()


def gather(shop: Shop, *, on: object, tariff: Tariff = STATE_TARIFF) -> Register:
    """Price every service point on the book, or say why it could not be."""
    when = parse_date(on)
    priced: list[Adjustment] = []
    passed_over: list[tuple[str, str]] = []
    for point in shop.points.all():
        try:
            found = raise_adjustment(shop, point.code, on=when, tariff=tariff)
        except ShopError as exc:
            passed_over.append((point.code, str(exc)))
            continue
        if isinstance(found, Refusal):
            passed_over.append((found.point_code, found.reason))
            continue
        priced.append(found)
    return Register(tuple(priced), tuple(passed_over))


def money_grid(register: Register) -> Grid:
    """A row per priced adjustment."""
    rows = [
        [
            a.point_code,
            a.meter_serial,
            str(a.direction),
            str(a.period.span),
            str(a.period.days),
            str(a.billed),
            str(a.moved),
            str(a.interest),
            str(a.total),
        ]
        for a in register.priced
    ]
    return Grid.of(MONEY_HEADINGS, rows)


def passed_over_grid(register: Register) -> Grid:
    """A row per point that could not be priced, with the reason."""
    return Grid.of(["point", "why"], [[code, why] for code, why in register.passed_over])


def build(shop: Shop, *, on: object, tariff: Tariff = STATE_TARIFF) -> Document:
    """The whole register for a day."""
    when = parse_date(on)
    register = gather(shop, on=when, tariff=tariff)
    doc = Document(f"Adjustment register as at {when.isoformat()}")

    money = doc.section("Priced", money_grid(register))
    money.fact("adjustments", len(register.priced))
    money.fact("refunds", len(register.refunds))
    money.fact("back bills", len(register.back_bills))
    money.fact("owed to customers", register.owed_to_customers())
    money.fact("owed to the utility", register.owed_to_utility())
    money.fact("net", register.net())

    skipped = doc.section("Passed over", passed_over_grid(register))
    skipped.fact("points", len(register.passed_over))

    doc.section("Tariff").fact("name", tariff.name).fact(
        "tolerance", f"+/-{tariff.tolerance} percent"
    ).fact("refund lookback", f"{tariff.refund_months} months").fact(
        "back bill lookback", f"{tariff.back_bill_months} months"
    )
    return doc


__all__ = [
    "MONEY_HEADINGS",
    "Register",
    "build",
    "gather",
    "money_grid",
    "passed_over_grid",
]
