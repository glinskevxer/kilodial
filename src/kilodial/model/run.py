"""Test points and test runs: what the bench actually recorded.

A run is one meter on one bench on one day, and it holds a handful of points.
A point is a load the bench held and the registration the meter turned in at
that load. Creep is the odd one out and it is worth saying why: there is no
registration at creep because there is no load, only the question of whether
the disc moved when it should have stood still.

Runs are frozen and points are ordered. The order is the order the technician
ran them, which is not always the order they get reported in, and a shop that
loses it cannot answer why a light load point came back different the second
time.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from kilodial.errors import BadInputError, RuleError
from kilodial.units.electrical import Amperes, PowerFactor, Volts
from kilodial.units.registration import Registration
from kilodial.units.span import parse_date
from kilodial.units.text import optional, positive, tidy


class PointKind(enum.Enum):
    """The loads a shop sequence is made of."""

    FULL_LOAD = ("FL", True)
    LIGHT_LOAD = ("LL", True)
    POWER_FACTOR = ("PF", True)
    HEAVY_LOAD = ("HL", False)
    CREEP = ("CR", False)
    REGISTER = ("RG", False)
    DEMAND = ("DM", False)

    def __init__(self, code: str, weighted: bool) -> None:
        self.code = code
        self.weighted = weighted

    @property
    def has_registration(self) -> bool:
        """Creep is a yes or no, everything else turns in a percentage."""
        return self is not PointKind.CREEP

    def __str__(self) -> str:
        return self.code


class RunKind(enum.Enum):
    """Why the run happened, which decides what its result is allowed to do."""

    ACCEPTANCE = "acceptance"
    AS_FOUND = "as found"
    AS_LEFT = "as left"
    REFEREE = "referee"

    @property
    def bills(self) -> bool:
        """Only an as found or a referee run can move money."""
        return self in (RunKind.AS_FOUND, RunKind.REFEREE)

    def __str__(self) -> str:
        return self.value


def point_kind(code: object) -> PointKind:
    """Look a point kind up by its two letter code or its name."""
    if isinstance(code, PointKind):
        return code
    if not isinstance(code, str):
        raise BadInputError(f"cannot read a test point kind from {type(code).__name__}")
    key = code.strip().upper().replace(" ", "_")
    for member in PointKind:
        if key in (member.code, member.name):
            return member
    raise BadInputError(f"{code!r} is not a test point kind")


@dataclass(frozen=True)
class BenchPoint:
    """One load held, and what the meter did at it."""

    kind: PointKind
    amperes: Amperes
    volts: Volts
    power_factor: PowerFactor
    registration: Registration | None
    crept: bool | None

    @classmethod
    def build(
        cls,
        kind: object,
        *,
        amperes: object,
        volts: object,
        power_factor: PowerFactor | None = None,
        registration: object = None,
        crept: bool | None = None,
    ) -> BenchPoint:
        the_kind = point_kind(kind)
        pf = power_factor if power_factor is not None else PowerFactor.unity()
        if not isinstance(pf, PowerFactor):
            raise BadInputError("the power factor has to be a PowerFactor")
        if the_kind.has_registration:
            if registration is None:
                raise RuleError(f"a {the_kind.name.lower()} point needs a registration")
            if crept is not None:
                raise RuleError("only a creep point records whether the disc moved")
            reading = (
                registration
                if isinstance(registration, Registration)
                else Registration(registration)
            )
            return cls(the_kind, Amperes(amperes), Volts(volts), pf, reading, None)
        if registration is not None:
            raise RuleError("a creep point has no registration to record")
        if crept is None:
            raise RuleError("a creep point has to say whether the disc moved")
        return cls(the_kind, Amperes(amperes), Volts(volts), pf, None, bool(crept))

    @property
    def percent(self) -> Registration:
        """The registration, refusing rather than handing back nothing."""
        if self.registration is None:
            raise RuleError(f"a {self.kind.name.lower()} point has no registration")
        return self.registration

    def __str__(self) -> str:
        if self.registration is None:
            return f"{self.kind} {'crept' if self.crept else 'held'}"
        return f"{self.kind} {self.registration}"


@dataclass(frozen=True)
class BenchRun:
    """One meter, one bench, one day."""

    reference: str
    meter_serial: str
    bench_code: str
    standard_serial: str
    kind: RunKind
    tested_on: date
    technician: str
    points: tuple[BenchPoint, ...]
    note: str | None
    demand_seconds: Decimal | None

    @classmethod
    def build(
        cls,
        reference: object,
        *,
        meter_serial: str,
        bench_code: str,
        standard_serial: str,
        kind: RunKind,
        tested_on: object,
        technician: object,
        points: list[BenchPoint],
        note: object = None,
        demand_seconds: object = None,
    ) -> BenchRun:
        if not isinstance(kind, RunKind):
            raise BadInputError("the run kind has to be a RunKind")
        if not points:
            raise RuleError("a run with no points on it is not a run")
        seen: set[PointKind] = set()
        for p in points:
            if not isinstance(p, BenchPoint):
                raise BadInputError("a run holds bench points")
            if p.kind in seen:
                raise RuleError(f"the run has two {p.kind.name.lower()} points on it")
            seen.add(p.kind)
        return cls(
            reference=_ref(reference),
            meter_serial=meter_serial,
            bench_code=bench_code,
            standard_serial=standard_serial,
            kind=kind,
            tested_on=parse_date(tested_on),
            technician=_tech(technician),
            points=tuple(points),
            note=_note(note),
            demand_seconds=_seconds(demand_seconds, seen),
        )

    @property
    def kinds(self) -> frozenset[PointKind]:
        return frozenset(p.kind for p in self.points)

    def point(self, kind: object) -> BenchPoint:
        wanted = point_kind(kind)
        for p in self.points:
            if p.kind is wanted:
                return p
        raise RuleError(f"run {self.reference} has no {wanted.name.lower()} point")

    def has(self, kind: object) -> bool:
        return point_kind(kind) in self.kinds

    def __str__(self) -> str:
        return f"{self.reference} {self.meter_serial} {self.kind} {self.tested_on.isoformat()}"


def _ref(value: object) -> str:
    if not isinstance(value, str):
        raise BadInputError(f"cannot read a run reference from {type(value).__name__}")
    ref = value.strip().upper()
    if not ref or len(ref) > 24 or " " in ref:
        raise BadInputError(f"{value!r} is not a run reference")
    return ref


def _seconds(value: object, kinds: set[PointKind]) -> Decimal | None:
    """The measured demand interval, which only belongs on a demand run.

    A number here says the technician timed the meter's own averaging window
    with a stopwatch against the bench clock. Recording one on a run with no
    demand point is a transcription error, because there was nothing to time.
    """
    if value is None:
        return None
    if PointKind.DEMAND not in kinds:
        raise RuleError("a measured demand interval belongs on a run with a demand point")
    return positive(value, "measured demand interval")


def _tech(value: object) -> str:
    return tidy(value, "technician name", 40)


def _note(value: object) -> str | None:
    return optional(value, "run note", 240)


__all__ = ["BenchPoint", "BenchRun", "PointKind", "RunKind", "point_kind"]
