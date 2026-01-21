"""Register readings, and the rollover that makes the arithmetic interesting.

A meter register has a fixed number of dials and it wraps. A five dial register
reading 99,860 last month and 00,140 this month recorded 280 units, not minus
ninety nine thousand seven hundred and twenty, and every billing system that has
ever existed has got that wrong at least once.

Assuming a rollover whenever the number goes down is the obvious fix and it is
wrong in a way that costs a customer real money. A misread, a meter change
entered as an ordinary reading, or a register that was reset all look exactly
like a rollover, and treating them as one bills the customer for a whole
register's worth of energy they never used. So a rollover is only assumed when
what it implies is plausible against the service's own history, and when it is
not, the reading is flagged instead of being quietly turned into a bill.

Multipliers are applied here and only here. The dials count what passed through
the meter and the customer is billed for that times the multiplier, and keeping
those two numbers apart on the record is what makes a multiplier error visible
years later.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from kilodial.errors import BadInputError, RuleError
from kilodial.units.span import parse_date
from kilodial.units.text import key, optional, positive

MIN_DIALS = 4
MAX_DIALS = 8

# How much a service can plausibly use in a day, per unit of multiplier, before
# a rollover stops being the likely explanation.
PLAUSIBLE_DAILY_UNITS = Decimal("400")


class ReadingKind(enum.Enum):
    """Where the number came from."""

    ACTUAL = ("actual", True)
    ESTIMATED = ("estimated", False)
    CUSTOMER = ("customer", False)
    FINAL = ("final", True)
    INITIAL = ("initial", True)

    def __init__(self, label: str, is_read: bool) -> None:
        self.label = label
        self.is_read = is_read

    @property
    def bills(self) -> bool:
        """Whether this reading can end a billing period on its own."""
        return self is not ReadingKind.CUSTOMER

    def __str__(self) -> str:
        return self.label


def reading_kind(value: object) -> ReadingKind:
    """Read a reading kind by name."""
    if isinstance(value, ReadingKind):
        return value
    wanted = str(value).strip().lower()
    for member in ReadingKind:
        if member.label == wanted:
            return member
    raise BadInputError(f"{value!r} is not a kind of register reading")


def _dials(value: object) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise BadInputError("a dial count has to be a whole number")
    if value < MIN_DIALS or value > MAX_DIALS:
        raise BadInputError(f"a register has between {MIN_DIALS} and {MAX_DIALS} dials")
    return value


def wrap_at(dials: object) -> int:
    """The number a register of that many dials rolls over at."""
    return int(10 ** _dials(dials))


@dataclass(frozen=True)
class Reading:
    """One reading off one register."""

    point_code: str
    meter_serial: str
    read_on: date
    dials: int
    value: int
    kind: ReadingKind
    note: str | None

    @classmethod
    def build(
        cls,
        point_code: object,
        meter_serial: object,
        *,
        read_on: object,
        dials: object,
        value: object,
        kind: object = ReadingKind.ACTUAL,
        note: object = None,
    ) -> Reading:
        """Record a reading, refusing one the register could not show."""
        count = _dials(dials)
        if not isinstance(value, int) or isinstance(value, bool):
            raise BadInputError("a register reading is a whole number of units")
        if value < 0:
            raise BadInputError("a register cannot read below zero")
        if value >= wrap_at(count):
            raise RuleError(
                f"a {count} dial register cannot read {value}, it rolls at {wrap_at(count)}"
            )
        return cls(
            point_code=key(point_code, "service point code", 16),
            meter_serial=key(meter_serial, "meter serial", 24),
            read_on=parse_date(read_on),
            dials=count,
            value=value,
            kind=reading_kind(kind),
            note=optional(note, "reading note", 240),
        )

    def __str__(self) -> str:
        return (
            f"{self.point_code} {self.meter_serial} {self.read_on.isoformat()} "
            f"{self.value:0{self.dials}d} ({self.kind})"
        )


@dataclass(frozen=True)
class Consumption:
    """What two readings say passed, and whether the register rolled."""

    units: int
    rolled: bool
    days: int
    multiplier: Decimal
    plausible: bool
    reason: str | None

    @property
    def billed_units(self) -> Decimal:
        """What the customer is billed for: the dials times the multiplier."""
        return (Decimal(self.units) * self.multiplier).quantize(Decimal("0.001"))

    @property
    def daily(self) -> Decimal:
        if self.days <= 0:
            return Decimal(0)
        return (self.billed_units / self.days).quantize(Decimal("0.001"))

    def show(self) -> str:
        rolled = ", register rolled" if self.rolled else ""
        return f"{self.billed_units} units over {self.days} days{rolled}"

    def __str__(self) -> str:
        return self.show()


def consumption(
    previous: Reading,
    current: Reading,
    *,
    multiplier: object = 1,
    daily_limit: object = PLAUSIBLE_DAILY_UNITS,
) -> Consumption:
    """What passed between two readings, deciding whether the register rolled.

    The two readings have to be off the same meter at the same point on the same
    register. A reading pair that spans a meter change is a different question
    and needs the final and initial readings handled as a pair, which is what
    ``across_change`` is for.
    """
    if previous.meter_serial != current.meter_serial:
        raise RuleError(f"{previous.meter_serial} and {current.meter_serial} are different meters")
    if previous.point_code != current.point_code:
        raise RuleError("those readings are from different service points")
    if previous.dials != current.dials:
        raise RuleError("those readings are off registers of different sizes")
    if current.read_on < previous.read_on:
        raise RuleError("the later reading is dated before the earlier one")
    factor = positive(multiplier, "multiplier")
    limit = positive(daily_limit, "daily limit")
    days = (current.read_on - previous.read_on).days
    rolled = current.value < previous.value
    units = current.value - previous.value
    if rolled:
        units += wrap_at(current.dials)
    billed = Decimal(units) * factor
    ceiling = limit * factor * Decimal(max(days, 1))
    plausible = billed <= ceiling
    reason = None
    if not plausible:
        reason = (
            f"{billed} units over {days} days is past the {ceiling} this service "
            "could plausibly use, so the register may not have rolled"
        )
    return Consumption(units, rolled, days, factor, plausible, reason)


def across_change(
    final: Reading,
    initial: Reading,
    current: Reading,
    *,
    multiplier: object = 1,
) -> Consumption:
    """What passed across a meter change, which is two readings plus a new start.

    ``final`` is the old meter's last reading and ``initial`` the new meter's
    first, which is usually but not always zero. The period is the old meter's
    consumption to its final reading plus the new meter's from its initial, and
    the caller supplies the old meter's own previous reading separately.
    """
    if final.meter_serial == current.meter_serial:
        raise RuleError("a meter change needs two different meters")
    if initial.meter_serial != current.meter_serial:
        raise RuleError(
            f"the initial reading is off {initial.meter_serial} and the current one "
            f"is off {current.meter_serial}"
        )
    if initial.read_on > current.read_on:
        raise RuleError("the initial reading is dated after the current one")
    after = consumption(initial, current, multiplier=multiplier)
    days = (current.read_on - final.read_on).days
    return Consumption(
        units=after.units,
        rolled=after.rolled,
        days=days,
        multiplier=after.multiplier,
        plausible=after.plausible,
        reason=after.reason,
    )


__all__ = [
    "MAX_DIALS",
    "MIN_DIALS",
    "PLAUSIBLE_DAILY_UNITS",
    "Consumption",
    "Reading",
    "ReadingKind",
    "across_change",
    "consumption",
    "reading_kind",
    "wrap_at",
]
