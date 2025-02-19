"""Judging a run, with the order of precedence written down.

This is where the pieces meet, and the order they are applied in is the whole
point. A run against a standard whose certificate had run out is void before
anybody looks at the numbers, and a shop that reports it as a failure has just
told a customer their meter was bad on the strength of a measurement it cannot
stand behind. Equally, a registration of four hundred percent is not a fast
meter, it is a meter wired through the wrong current transformer, and calling
it a failure sends a crew to change the wrong thing.

So the order is fixed:

  1. void      the run cannot be relied on at all
  2. suspect   the numbers are real but they are not a meter error
  3. failed    creep, or a weighted average outside the band
  4. passed

Nothing below a step is evaluated once that step fires, and every step that
fires adds its reason to the record.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass
from decimal import Decimal

from kilodial.errors import RuleError
from kilodial.model.bench import Bench, ReferenceStandard
from kilodial.model.device import DeviceType
from kilodial.model.run import BenchRun, PointKind
from kilodial.testing.sequence import check_conditions, check_sequence
from kilodial.testing.tolerance import Band, band_for
from kilodial.testing.weighted import WeightedAverage, weighted_average
from kilodial.units.registration import Registration


class Outcome(enum.Enum):
    """What the shop decided about a run."""

    PASSED = "passed"
    FAILED = "failed"
    SUSPECT = "suspect"
    VOID = "void"

    @property
    def is_usable(self) -> bool:
        """Whether the run may be relied on for anything downstream."""
        return self in (Outcome.PASSED, Outcome.FAILED)

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class Verdict:
    """The decision, with the working and the reasons kept."""

    run_reference: str
    outcome: Outcome
    average: WeightedAverage | None
    band: Band
    reasons: tuple[str, ...]

    @property
    def registration(self) -> Registration | None:
        return None if self.average is None else self.average.value

    @property
    def error(self) -> Decimal | None:
        """Percentage points away from nominal, or nothing on a void run."""
        return None if self.average is None else self.average.value.error

    @property
    def passed(self) -> bool:
        return self.outcome is Outcome.PASSED

    def why(self) -> str:
        return "; ".join(self.reasons) if self.reasons else "within band"

    def __str__(self) -> str:
        shown = "no reading" if self.registration is None else str(self.registration)
        return f"{self.run_reference} {self.outcome} at {shown}"


def _void(run: BenchRun, band: Band, reasons: list[str]) -> Verdict:
    return Verdict(run.reference, Outcome.VOID, None, band, tuple(reasons))


def judge(
    run: BenchRun,
    device: DeviceType,
    *,
    standard: ReferenceStandard,
    bench: Bench,
) -> Verdict:
    """Decide a run against the device type, the standard and the bench."""
    band = band_for(run.kind, device.meter_class)
    reasons: list[str] = []

    if standard.serial != run.standard_serial:
        reasons.append(
            f"run names standard {run.standard_serial} and was judged against {standard.serial}"
        )
    elif not standard.is_valid_on(run.tested_on):
        reasons.append(
            f"standard {standard.serial} was outside its certificate on {run.tested_on.isoformat()}"
        )
    if bench.code != run.bench_code:
        reasons.append(f"run names bench {run.bench_code} and was judged against {bench.code}")
    elif not bench.is_available_on(run.tested_on):
        reasons.append(f"bench {bench.code} was out of service on {run.tested_on.isoformat()}")
    elif not bench.can_hold(device):
        reasons.append(f"bench {bench.code} cannot hold a {device.key}")
    for check in (check_sequence, check_conditions):
        try:
            check(run, device)
        except RuleError as exc:
            reasons.append(str(exc))
    if reasons:
        return _void(run, band, reasons)

    try:
        average = weighted_average(run, device.elements)
    except RuleError as exc:
        return _void(run, band, [str(exc)])

    if not average.value.is_plausible:
        return Verdict(
            run.reference,
            Outcome.SUSPECT,
            average,
            band,
            (
                f"a weighted average of {average.value} is not a meter error, "
                "check the wiring and the multiplier",
            ),
        )

    if run.has(PointKind.CREEP) and run.point(PointKind.CREEP).crept:
        reasons.append("the disc crept at no load")
    if not band.accepts(average.value):
        reasons.append(
            f"weighted average {average.value} is outside the "
            f"+/-{band.weighted} percent band for an {run.kind} run"
        )
    for point in run.points:
        if point.registration is None or not point.kind.weighted:
            continue
        if not band.accepts_point(point.kind, point.registration):
            reasons.append(
                f"{point.kind.name.lower()} at {point.registration} is outside the "
                f"+/-{band.limit_for(point.kind)} percent point band"
            )
    outcome = Outcome.FAILED if reasons else Outcome.PASSED
    return Verdict(run.reference, outcome, average, band, tuple(reasons))


__all__ = ["Outcome", "Verdict", "judge"]
