"""Tolerance bands: how far out a meter is allowed to be, and when.

There is no single tolerance. What a meter is held to depends on why it is on
the bench and on what class it is, and the two interact:

  acceptance   a meter going into service for the first time or coming off a
               repair. Tightest band there is, because the shop is choosing to
               put it out and has no excuse for a known error.
  as found     a meter pulled off a service and tested before anything is
               adjusted. Widest band, because it has been out in the weather
               for fifteen years. This is the band that decides money.
  as left      the run that says the meter is fit to go back out. Between the
               two, and tighter than as found on purpose, so that a meter is
               never returned sitting at the edge of the band it will be judged
               against next time.
  referee      a customer asked for the test. Same band as as found, because it
               would be indefensible to hold a meter to a different standard
               depending on who asked for the run.

Class 10 and class 20 meters get a tighter band than everything else, and the
reason is arithmetic rather than quality: those meters sit behind current
transformers with ratios of 200 to 1 and up, so a one percent error on the
meter is a one percent error on a very large bill.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from kilodial.errors import BadInputError
from kilodial.model.form import MeterClass
from kilodial.model.run import PointKind, RunKind
from kilodial.units.registration import Registration


@dataclass(frozen=True)
class Band:
    """A symmetric tolerance, in percentage points either side of nominal."""

    weighted: Decimal
    per_point: Decimal
    light_load: Decimal
    creep_allowed: bool

    def accepts(self, reading: Registration) -> bool:
        return reading.within(self.weighted)

    def accepts_point(self, kind: PointKind, reading: Registration) -> bool:
        return reading.within(self.limit_for(kind))

    def limit_for(self, kind: PointKind) -> Decimal:
        """The band a single load point is held to."""
        if kind is PointKind.LIGHT_LOAD:
            return self.light_load
        return self.per_point

    def __str__(self) -> str:
        return f"+/-{self.weighted} percent weighted, +/-{self.per_point} per point"


# The house band table. Read it as run kind first, then narrow for the tight
# classes, because that is the order the rules were written in.
BANDS: dict[RunKind, Band] = {
    RunKind.ACCEPTANCE: Band(Decimal("0.5"), Decimal("1.0"), Decimal("1.5"), False),
    RunKind.AS_FOUND: Band(Decimal("2.0"), Decimal("3.0"), Decimal("4.0"), False),
    RunKind.AS_LEFT: Band(Decimal("1.0"), Decimal("2.0"), Decimal("2.5"), False),
    RunKind.REFEREE: Band(Decimal("2.0"), Decimal("3.0"), Decimal("4.0"), False),
}

# How much of the band a transformer class meter gives back. Two thirds of the
# ordinary band, floored so the tightest band does not collapse to nothing.
TIGHT_CLASS_SHARE = Decimal("0.667")
TIGHTEST_WEIGHTED = Decimal("0.25")


def _tighten(value: Decimal, floor: Decimal) -> Decimal:
    narrowed = (value * TIGHT_CLASS_SHARE).quantize(Decimal("0.01"))
    return max(narrowed, floor)


def band_for(kind: object, meter_class: object = None) -> Band:
    """The band a run of that kind on a meter of that class is held to.

    ``meter_class`` is optional because plenty of callers are judging a run in
    the abstract. Leaving it out gives the ordinary band, never the tight one.
    """
    if not isinstance(kind, RunKind):
        raise BadInputError("the run kind has to be a RunKind")
    base = BANDS[kind]
    if meter_class is None:
        return base
    if not isinstance(meter_class, MeterClass):
        raise BadInputError("the meter class has to be a MeterClass")
    if not meter_class.is_transformer_class:
        return base
    return Band(
        weighted=_tighten(base.weighted, TIGHTEST_WEIGHTED),
        per_point=_tighten(base.per_point, TIGHTEST_WEIGHTED),
        light_load=_tighten(base.light_load, TIGHTEST_WEIGHTED),
        creep_allowed=base.creep_allowed,
    )


__all__ = ["BANDS", "TIGHTEST_WEIGHTED", "TIGHT_CLASS_SHARE", "Band", "band_for"]
