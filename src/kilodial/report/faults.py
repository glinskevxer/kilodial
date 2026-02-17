"""What breaks, on which types, and what it costs to keep fixing it.

This is the report that should decide the next purchase order and usually does
not, because the numbers live in three places and nobody assembles them. The
question it answers is narrow and worth answering: for each type the shop
stocks, how many of them failed, what failed on them, and what the shop spent
keeping them going.

The rate is the number that matters and it is the one most easily got wrong. A
type with forty repairs sounds worse than a type with four until you notice
there are eight hundred of the first and eleven of the second. So the report
carries the population alongside the count and states the rate per hundred
meters, which is the figure a purchasing conversation can actually use.

A repair that cost more than the tariff share of a new meter is counted apart.
A type where that happens often is a type the shop should stop repairing rather
than one it should stop buying, and those are different decisions.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from kilodial.model.repair import Fault, families
from kilodial.report.document import Document, Grid
from kilodial.store.shop import Shop
from kilodial.units.money import Money
from kilodial.units.span import DateSpan

HEADINGS = [
    "type",
    "meters",
    "repairs",
    "per hundred",
    "spent",
    "a meter",
    "not worth it",
    "commonest fault",
]


@dataclass(frozen=True)
class TypeFaults:
    """One device type's repair record over a window."""

    device_key: str
    meters: int
    repairs: int
    spent: Money
    wasteful: int
    counts: dict[Fault, int]

    @property
    def per_hundred(self) -> Decimal:
        """Repairs per hundred meters, which is the comparable number."""
        if self.meters == 0:
            return Decimal(0)
        return (Decimal(self.repairs) / self.meters * 100).quantize(Decimal("0.1"))

    @property
    def a_meter(self) -> Money:
        """What the shop spent per meter of this type."""
        if self.meters == 0:
            return Money.zero()
        return self.spent.scaled(Decimal(1) / Decimal(self.meters))

    @property
    def commonest(self) -> Fault | None:
        """The fault that came up most, or nothing when there were none."""
        found = [(count, fault) for fault, count in self.counts.items() if count]
        if not found:
            return None
        return max(found, key=lambda pair: (pair[0], -list(Fault).index(pair[1])))[1]

    def row(self) -> list[str]:
        return [
            self.device_key,
            str(self.meters),
            str(self.repairs),
            str(self.per_hundred),
            str(self.spent),
            str(self.a_meter),
            str(self.wasteful),
            "-" if self.commonest is None else self.commonest.label,
        ]


def for_type(shop: Shop, device_key: str, window: DateSpan) -> TypeFaults:
    """One type's figures over a window."""
    serials = {m.serial for m in shop.meters.by_device(device_key)}
    counts = dict.fromkeys(Fault, 0)
    spent = Money.zero()
    wasteful = 0
    repairs = 0
    for repair in shop.repairs.between(window.start, window.end or window.start):
        if repair.meter_serial not in serials:
            continue
        repairs += 1
        counts[repair.fault] += 1
        spent = spent + repair.cost
        if repair.fault.is_a_fault and not repair.was_worth_it:
            wasteful += 1
    return TypeFaults(device_key, len(serials), repairs, spent, wasteful, counts)


def grid(rows: list[TypeFaults]) -> Grid:
    """A row per device type, worst rate first."""
    ordered = sorted(rows, key=lambda r: (-r.per_hundred, r.device_key))
    return Grid.of(HEADINGS, [r.row() for r in ordered])


def family_grid(rows: list[TypeFaults]) -> Grid:
    """A row per fault family, which is the shape of the problem."""
    totals: dict[str, int] = {}
    for row in rows:
        for fault, count in row.counts.items():
            totals[fault.family] = totals.get(fault.family, 0) + count
    whole = sum(totals.values())
    return Grid.of(
        ["family", "repairs", "percent"],
        [
            [
                family,
                str(totals.get(family, 0)),
                "0.0" if whole == 0 else f"{totals.get(family, 0) / whole * 100:.1f}",
            ]
            for family in sorted(families())
        ],
    )


def build(shop: Shop, *, first: object, last: object) -> Document:
    """The whole fault report for a window."""
    window = DateSpan(first, last)
    rows = [for_type(shop, d.key, window) for d in shop.devices.all()]
    doc = Document(f"Fault report, {window}")

    section = doc.section("By type", grid(rows))
    section.fact("types", len(rows))
    section.fact("meters", sum(r.meters for r in rows))
    section.fact("repairs", sum(r.repairs for r in rows))
    section.fact("spent", _total(rows))
    section.fact("not worth doing", sum(r.wasteful for r in rows))
    worst = sorted(rows, key=lambda r: -r.per_hundred)
    if worst and worst[0].repairs:
        head = worst[0]
        section.note(
            f"{head.device_key} is the worst at {head.per_hundred} repairs per "
            f"hundred meters, mostly {head.commonest}"
        )

    doc.section("By family", family_grid(rows)).note(
        "a type whose failures are mostly electronic is a different purchasing "
        "decision from one whose failures are mostly bearings"
    )
    return doc


def _total(rows: list[TypeFaults]) -> Money:
    total = Money.zero()
    for row in rows:
        total = total + row.spent
    return total


__all__ = ["HEADINGS", "TypeFaults", "build", "family_grid", "for_type", "grid"]
