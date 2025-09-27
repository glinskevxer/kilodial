"""Judging the demand half of a run.

A demand test asks two questions of a meter and the shop's rules answer them
separately, because the remedies are different. A meter whose demand
registration is out gets adjusted or replaced. A meter whose interval clock is
out gets reprogrammed, and its registration was never the problem.

The band is tighter than the energy band and that is not an oversight. Demand is
billed on a single peak rather than on a total, so a two percent error on demand
follows one reading straight onto the bill with nothing to average it out, where
the same error on energy is spread over a month of consumption that the customer
has some feel for.

A run with no demand point is not a demand failure. It is a run that did not ask
the question, and saying so is different from saying the meter passed.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass
from decimal import Decimal

from kilodial.errors import RuleError
from kilodial.model.demand import TIMING_BAND, Interval, timing_error
from kilodial.model.device import DeviceType
from kilodial.model.run import BenchRun, PointKind, RunKind
from kilodial.units.registration import Registration

# What a demand register is held to, by run kind. Tighter than energy across the
# board, and tightest on the run that puts a meter back into service.
DEMAND_BANDS: dict[RunKind, Decimal] = {
    RunKind.ACCEPTANCE: Decimal("0.5"),
    RunKind.AS_FOUND: Decimal("2.0"),
    RunKind.AS_LEFT: Decimal("1.0"),
    RunKind.REFEREE: Decimal("2.0"),
}


class DemandOutcome(enum.Enum):
    """What a demand test decided."""

    PASSED = "passed"
    REGISTRATION = "failed on registration"
    TIMING = "failed on the interval clock"
    BOTH = "failed on registration and on the interval clock"
    NOT_TESTED = "not tested"

    @property
    def passed(self) -> bool:
        return self is DemandOutcome.PASSED

    @property
    def was_tested(self) -> bool:
        return self is not DemandOutcome.NOT_TESTED

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class DemandVerdict:
    """The demand half of a run, with both errors kept apart."""

    run_reference: str
    outcome: DemandOutcome
    registration: Registration | None
    band: Decimal
    interval: Interval | None
    timing: Decimal | None
    reasons: tuple[str, ...]

    @property
    def registration_error(self) -> Decimal | None:
        return None if self.registration is None else self.registration.error

    def why(self) -> str:
        return "; ".join(self.reasons) if self.reasons else str(self.outcome)

    def __str__(self) -> str:
        shown = "no reading" if self.registration is None else str(self.registration)
        return f"{self.run_reference} demand {self.outcome} at {shown}"


def band_for(kind: RunKind) -> Decimal:
    """The demand band a run of that kind is held to."""
    return DEMAND_BANDS[kind]


def judge_demand(
    run: BenchRun,
    device: DeviceType,
    *,
    interval: Interval | None = None,
    measured_seconds: object = None,
) -> DemandVerdict:
    """Judge a run's demand point, and its interval clock when one was measured.

    ``interval`` names the window the meter is programmed for. It has to be
    supplied to check timing at all, because the nameplate does not carry it:
    the same meter is programmed for fifteen minutes on one service and thirty
    on the next.
    """
    band = band_for(run.kind)
    if not device.demand_capable:
        if run.has(PointKind.DEMAND):
            raise RuleError(
                f"run {run.reference} carries a demand point and {device.key} "
                "does not register demand"
            )
        return DemandVerdict(
            run.reference, DemandOutcome.NOT_TESTED, None, band, interval, None, ()
        )
    if not run.has(PointKind.DEMAND):
        return DemandVerdict(
            run.reference, DemandOutcome.NOT_TESTED, None, band, interval, None, ()
        )

    reading = run.point(PointKind.DEMAND).percent
    reasons: list[str] = []
    if not reading.within(band):
        reasons.append(
            f"demand registration {reading} is outside the +/-{band} percent band "
            f"for an {run.kind} run"
        )
    drift: Decimal | None = None
    if measured_seconds is not None:
        if interval is None:
            raise RuleError("checking the interval clock needs the interval it is set to")
        drift = timing_error(measured_seconds, interval)
        if abs(drift) > TIMING_BAND:
            reasons.append(
                f"the {interval} window measured {drift} percent off, outside "
                f"+/-{TIMING_BAND} percent"
            )
    outcome = _outcome(reasons)
    return DemandVerdict(run.reference, outcome, reading, band, interval, drift, tuple(reasons))


def _outcome(reasons: list[str]) -> DemandOutcome:
    on_registration = any("registration" in r for r in reasons)
    on_timing = any("window measured" in r for r in reasons)
    if on_registration and on_timing:
        return DemandOutcome.BOTH
    if on_registration:
        return DemandOutcome.REGISTRATION
    if on_timing:
        return DemandOutcome.TIMING
    return DemandOutcome.PASSED


__all__ = ["DEMAND_BANDS", "DemandOutcome", "DemandVerdict", "band_for", "judge_demand"]
