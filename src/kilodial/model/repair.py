"""What was wrong with a meter and what was done about it.

A failed run says a meter is out of tolerance. It does not say why, and the why
is what the shop needs to know, because the same registration error means a worn
jewel on one meter and a corroded potential link on the next, and only one of
those is worth repairing.

Repair codes are a fixed list on purpose. A free text fault description produces
a register nobody can count, and counting is the entire point: a type whose
bearings account for forty percent of its failures is a type to stop buying.

The economics rule is the one that gets argued about. A repair is not worth
doing when it costs more than a replacement meter, and the shop's answer is a
share rather than a figure, because meter prices move and the rule does not.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation

from kilodial.errors import BadInputError, RuleError
from kilodial.units.money import Money
from kilodial.units.span import parse_date
from kilodial.units.text import key, optional, tidy

# A repair costing more than this share of a new meter is not worth doing.
WORTH_REPAIRING = Decimal("0.60")

LABOUR_RATE = Money("68.00")


class Fault(enum.Enum):
    """What was found wrong, from the shop's fixed list."""

    BEARING = ("bearing", "mechanical")
    MAGNET = ("magnet", "mechanical")
    REGISTER = ("register", "mechanical")
    DISC = ("disc", "mechanical")
    POTENTIAL_LINK = ("potential link", "electrical")
    COIL = ("coil", "electrical")
    BOARD = ("board", "electronic")
    BATTERY = ("battery", "electronic")
    FIRMWARE = ("firmware", "electronic")
    COVER = ("cover", "enclosure")
    TERMINAL = ("terminal", "enclosure")
    NONE_FOUND = ("none found", "none")

    def __init__(self, label: str, family: str) -> None:
        self.label = label
        self.family = family

    @property
    def is_a_fault(self) -> bool:
        """A meter that came back with nothing wrong is a finding of its own."""
        return self is not Fault.NONE_FOUND

    def __str__(self) -> str:
        return self.label


def fault_named(value: object) -> Fault:
    """Read a fault code by its label or its name."""
    if isinstance(value, Fault):
        return value
    wanted = str(value).strip().lower().replace("_", " ")
    for member in Fault:
        if member.label == wanted or member.name.lower().replace("_", " ") == wanted:
            return member
    raise BadInputError(f"{value!r} is not a fault the shop records")


@dataclass(frozen=True)
class Repair:
    """One repair: what was wrong, what it took, and what it cost."""

    reference: str
    meter_serial: str
    fault: Fault
    repaired_on: date
    by: str
    hours: Decimal
    parts: Money
    replacement_cost: Money
    note: str | None

    @classmethod
    def build(
        cls,
        reference: object,
        meter_serial: object,
        fault: object,
        *,
        repaired_on: object,
        by: object,
        hours: object,
        parts: object = 0,
        replacement_cost: object,
        note: object = None,
    ) -> Repair:
        """Record a repair, refusing figures that are not figures."""
        spent = _hours(hours)
        materials = Money(parts)
        if materials.cents < 0:
            raise BadInputError("parts cannot cost less than nothing")
        replacement = Money(replacement_cost)
        if replacement.cents <= 0:
            raise RuleError("a repair is judged against a replacement price above zero")
        return cls(
            reference=key(reference, "repair reference", 24),
            meter_serial=key(meter_serial, "meter serial", 24),
            fault=fault_named(fault),
            repaired_on=parse_date(repaired_on),
            by=tidy(by, "technician name", 40),
            hours=spent,
            parts=materials,
            replacement_cost=replacement,
            note=optional(note, "repair note", 240),
        )

    @property
    def labour(self) -> Money:
        return LABOUR_RATE.scaled(self.hours)

    @property
    def cost(self) -> Money:
        return self.labour + self.parts

    @property
    def share_of_replacement(self) -> Decimal:
        return (Decimal(self.cost.cents) / Decimal(self.replacement_cost.cents)).quantize(
            Decimal("0.0001")
        )

    @property
    def was_worth_it(self) -> bool:
        """Whether the shop should have repaired this rather than replaced it."""
        return self.share_of_replacement <= WORTH_REPAIRING

    def verdict(self) -> str:
        if not self.fault.is_a_fault:
            return "nothing found, so nothing was fixed"
        if self.was_worth_it:
            return f"{self.cost} against a {self.replacement_cost} meter, worth doing"
        return f"{self.cost} against a {self.replacement_cost} meter, should have been scrapped"

    def __str__(self) -> str:
        return f"{self.reference} {self.meter_serial} {self.fault} {self.cost}"


def _hours(value: object) -> Decimal:
    try:
        spent = Decimal(str(value).strip())
    except (InvalidOperation, ValueError):
        raise BadInputError(f"{value!r} is not a number of hours") from None
    if spent <= 0:
        raise BadInputError("a repair takes more than no time at all")
    if spent > 40:
        raise RuleError("no meter repair runs to more than a working week")
    return spent.quantize(Decimal("0.01"))


def families() -> dict[str, list[Fault]]:
    """The fault list grouped by family, for a report that counts them."""
    found: dict[str, list[Fault]] = {}
    for fault in Fault:
        found.setdefault(fault.family, []).append(fault)
    return found


__all__ = [
    "LABOUR_RATE",
    "WORTH_REPAIRING",
    "Fault",
    "Repair",
    "families",
    "fault_named",
]
