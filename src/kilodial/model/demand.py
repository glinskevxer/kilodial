"""Demand metering: the other half of what a commercial meter sells.

A demand meter measures two things and bills two things. The energy register
counts kilowatthours, which is everything the rest of this package has been
about. The demand register holds the highest average power over any interval
since it was last reset, and that number carries a separate charge, often the
larger of the two on an industrial account.

It follows that a demand meter can be perfectly accurate on energy and wrong on
demand, and the two errors do not compose into one figure. A meter whose energy
register is dead on and whose demand register reads four percent high has
overbilled a customer with no error at all in its kilowatthours.

Two things decide a demand reading and both can be wrong on their own:

The measurement, which is the same registration question as energy asked about
power instead. A meter that registers 102 percent of the demand applied to it is
two percent fast on demand.

The interval, which is where a demand meter is different from an energy meter.
Demand is an average over a fixed window, so a meter whose fifteen minute window
is actually running at fourteen and a half minutes averages over less time and
reports a higher peak, and it does that with a measurement circuit that is
exactly right. That is the timing error, and it is checked separately.

Rolling demand is a block demand meter that reports the highest average of the
last several subintervals rather than of each block on its own. It answers a
different question, produces a higher number on the same load, and is a
different tariff. The register records which it is because a meter programmed
one way and billed the other is a whole class of complaint.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from kilodial.errors import BadInputError, RuleError
from kilodial.units.registration import Registration
from kilodial.units.span import parse_date
from kilodial.units.text import number, positive

SECONDS_PER_MINUTE = Decimal("60")

# How far the interval clock may sit from nominal. Tighter than the measurement
# band because a timing error moves every reading the same way.
TIMING_BAND = Decimal("0.5")


class Interval(enum.Enum):
    """The window demand is averaged over."""

    MIN_5 = ("5 minute", 5)
    MIN_15 = ("15 minute", 15)
    MIN_30 = ("30 minute", 30)
    MIN_60 = ("60 minute", 60)

    def __init__(self, label: str, minutes: int) -> None:
        self.label = label
        self.minutes = minutes

    @property
    def seconds(self) -> Decimal:
        return Decimal(self.minutes) * SECONDS_PER_MINUTE

    def __str__(self) -> str:
        return self.label


class DemandKind(enum.Enum):
    """How the peak is picked out of the intervals."""

    BLOCK = "block"
    ROLLING = "rolling"

    def __str__(self) -> str:
        return self.value


def interval_of(value: object) -> Interval:
    """Read a demand interval from its minute count or its label."""
    if isinstance(value, Interval):
        return value
    written = str(value).strip().lower()
    bare = written.removesuffix(" minute").removesuffix("min").strip()
    for member in Interval:
        if member.label == written or str(member.minutes) == bare:
            return member
    raise BadInputError(f"{value!r} is not a demand interval this shop meters")


def demand_kind(value: object) -> DemandKind:
    """Read a demand kind by name."""
    if isinstance(value, DemandKind):
        return value
    wanted = str(value).strip().lower()
    for member in DemandKind:
        if member.value == wanted:
            return member
    raise BadInputError(f"{value!r} is not a demand kind")


@dataclass(frozen=True)
class DemandRegister:
    """How a meter is programmed to measure demand, and what it is holding."""

    interval: Interval
    kind: DemandKind
    subintervals: int
    maximum_kw: Decimal
    reset_on: date | None

    @classmethod
    def build(
        cls,
        *,
        interval: object,
        kind: object = DemandKind.BLOCK,
        subintervals: int = 1,
        maximum_kw: object = 0,
        reset_on: object = None,
    ) -> DemandRegister:
        """Build a register, refusing a programming nobody could bill."""
        window = interval_of(interval)
        shape = demand_kind(kind)
        if not isinstance(subintervals, int) or isinstance(subintervals, bool):
            raise BadInputError("a subinterval count has to be a whole number")
        if shape is DemandKind.BLOCK and subintervals != 1:
            raise RuleError("a block demand register has one subinterval, not several")
        if shape is DemandKind.ROLLING and subintervals < 2:
            raise RuleError("a rolling demand register averages two or more subintervals")
        if subintervals > 12:
            raise RuleError("no tariff rolls demand over more than twelve subintervals")
        peak = number(maximum_kw, "demand reading")
        if peak < 0:
            raise BadInputError("a demand register cannot hold a negative peak")
        return cls(
            interval=window,
            kind=shape,
            subintervals=subintervals,
            maximum_kw=peak,
            reset_on=None if reset_on is None else parse_date(reset_on),
        )

    @property
    def subinterval_minutes(self) -> Decimal:
        """How long each averaging step is, which is the window on a block meter."""
        return (Decimal(self.interval.minutes) / self.subintervals).quantize(Decimal("0.01"))

    @property
    def was_reset(self) -> bool:
        return self.reset_on is not None

    def reset(self, on: object) -> DemandRegister:
        """Zero the peak and record the day, which is what a billing read does."""
        when = parse_date(on)
        if self.reset_on is not None and when < self.reset_on:
            raise RuleError("a demand register cannot be reset backwards")
        return DemandRegister(
            interval=self.interval,
            kind=self.kind,
            subintervals=self.subintervals,
            maximum_kw=Decimal(0),
            reset_on=when,
        )

    def holding(self, kw: object) -> DemandRegister:
        """Record a new peak, keeping the higher of the two."""
        offered = positive(kw, "demand reading")
        if offered <= self.maximum_kw:
            return self
        return DemandRegister(
            interval=self.interval,
            kind=self.kind,
            subintervals=self.subintervals,
            maximum_kw=offered,
            reset_on=self.reset_on,
        )

    def __str__(self) -> str:
        shape = (
            f"{self.kind} {self.subintervals}x{self.subinterval_minutes.normalize():f} minute"
            if self.kind is DemandKind.ROLLING
            else f"{self.kind} {self.interval}"
        )
        return f"{shape}, holding {self.maximum_kw.normalize():f} kW"


def demand_registration(indicated_kw: object, actual_kw: object) -> Registration:
    """What the demand register read against the demand that was applied."""
    return Registration.from_readings(
        number(indicated_kw, "demand reading"), number(actual_kw, "demand applied")
    )


def timing_error(measured_seconds: object, interval: object) -> Decimal:
    """How far the meter's own interval clock sits from nominal, in percent.

    Positive means the meter's window is longer than it should be, which
    averages over more time and reports a lower peak than the truth.
    """
    nominal = interval_of(interval).seconds
    measured = positive(measured_seconds, "measured interval")
    return ((measured - nominal) / nominal * 100).quantize(Decimal("0.0001"))


def timing_holds(measured_seconds: object, interval: object) -> bool:
    """Whether the interval clock is inside the band."""
    return abs(timing_error(measured_seconds, interval)) <= TIMING_BAND


__all__ = [
    "SECONDS_PER_MINUTE",
    "TIMING_BAND",
    "DemandKind",
    "DemandRegister",
    "Interval",
    "demand_kind",
    "demand_registration",
    "interval_of",
    "timing_error",
    "timing_holds",
]
