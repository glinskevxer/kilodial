"""What a run has to contain, and at what load, before it counts.

Two separate questions live here and they are easy to blur. The first is which
points a sequence needs: a three element meter cannot be judged without a
lagging point, and an induction meter that has never been checked for creep has
not really been tested. The second is whether the points that are there were run
at the right load, because a full load point recorded at three amperes is a
light load point that somebody mislabelled, and averaging it as full load moves
the answer a long way.

Creep is worth one more line. A solid state meter has no disc and cannot creep,
so demanding a creep point from one is asking a technician to invent a reading.
The sequence follows the technology, not the form.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from kilodial.errors import RuleError
from kilodial.model.device import DeviceType
from kilodial.model.form import Technology
from kilodial.model.run import BenchPoint, BenchRun, PointKind, RunKind
from kilodial.units.electrical import Amperes, PowerFactor, Sense, Volts

# How far a recorded load may sit from the nominal one before the point is
# treated as mislabelled rather than merely imprecise.
CURRENT_SLACK = Decimal("0.05")
VOLTAGE_SLACK = Decimal("0.05")

CREEP_VOLTAGE_SHARE = Decimal("1.10")
HEAVY_LOAD_SHARE = Decimal("2")


@dataclass(frozen=True)
class Condition:
    """The load a point is supposed to be run at."""

    amperes: Amperes
    volts: Volts
    power_factor: PowerFactor

    def __str__(self) -> str:
        return f"{self.amperes} {self.volts} {self.power_factor}"


def condition_for(device: DeviceType, kind: PointKind) -> Condition:
    """The nominal load for one point on one device type."""
    ta = device.meter_class.test_amperes
    volts = device.voltage
    if kind is PointKind.FULL_LOAD:
        return Condition(Amperes(ta), volts, PowerFactor.unity())
    if kind is PointKind.LIGHT_LOAD:
        return Condition(Amperes(ta / 10), volts, PowerFactor.unity())
    if kind is PointKind.POWER_FACTOR:
        return Condition(Amperes(ta / 2), volts, PowerFactor.lagging("0.5"))
    if kind is PointKind.HEAVY_LOAD:
        return Condition(Amperes(ta * HEAVY_LOAD_SHARE), volts, PowerFactor.unity())
    if kind is PointKind.CREEP:
        return Condition(Amperes(0), Volts(volts.value * CREEP_VOLTAGE_SHARE), PowerFactor.unity())
    if kind is PointKind.REGISTER:
        return Condition(Amperes(ta), volts, PowerFactor.unity())
    return Condition(Amperes(ta / 2), volts, PowerFactor.unity())


def required_points(device: DeviceType, kind: RunKind) -> frozenset[PointKind]:
    """The points a run of that kind on that device type has to carry."""
    wanted = {PointKind.FULL_LOAD, PointKind.LIGHT_LOAD}
    if device.elements >= Decimal("2"):
        wanted.add(PointKind.POWER_FACTOR)
    if device.technology is Technology.INDUCTION and kind is not RunKind.AS_FOUND:
        wanted.add(PointKind.CREEP)
    if device.demand_capable and kind is RunKind.ACCEPTANCE:
        wanted.add(PointKind.DEMAND)
    if device.technology is Technology.INDUCTION and kind is RunKind.ACCEPTANCE:
        wanted.add(PointKind.REGISTER)
    return frozenset(wanted)


def missing_points(run: BenchRun, device: DeviceType) -> frozenset[PointKind]:
    """Which required points a run does not have."""
    return frozenset(k for k in required_points(device, run.kind) if not run.has(k))


def check_sequence(run: BenchRun, device: DeviceType) -> None:
    """Refuse a run that is not a complete sequence for that device type."""
    gaps = missing_points(run, device)
    if gaps:
        names = ", ".join(sorted(k.name.lower() for k in gaps))
        raise RuleError(
            f"run {run.reference} on a {device.key} is missing its {names} "
            f"point for an {run.kind} sequence"
        )


def _off_by(actual: Decimal, nominal: Decimal) -> Decimal:
    if nominal == 0:
        return abs(actual)
    return abs(actual - nominal) / nominal


def condition_faults(point: BenchPoint, device: DeviceType) -> list[str]:
    """Everything wrong with the load a point says it was run at."""
    want = condition_for(device, point.kind)
    faults: list[str] = []
    if point.kind is PointKind.CREEP:
        if point.amperes.value != 0:
            faults.append(f"creep was run at {point.amperes} rather than no load")
    elif _off_by(point.amperes.value, want.amperes.value) > CURRENT_SLACK:
        faults.append(
            f"{point.kind.name.lower()} was run at {point.amperes}, nominal is {want.amperes}"
        )
    if _off_by(point.volts.value, want.volts.value) > VOLTAGE_SLACK:
        faults.append(
            f"{point.kind.name.lower()} was run at {point.volts}, nominal is {want.volts}"
        )
    if (
        point.power_factor.sense is not want.power_factor.sense
        or point.power_factor.sense is Sense.LAGGING
        and (point.power_factor.value != want.power_factor.value)
    ):
        faults.append(
            f"{point.kind.name.lower()} was run at {point.power_factor}, "
            f"nominal is {want.power_factor}"
        )
    return faults


def check_conditions(run: BenchRun, device: DeviceType) -> None:
    """Refuse a run whose points were held at the wrong load."""
    faults = [fault for p in run.points for fault in condition_faults(p, device)]
    if faults:
        raise RuleError(f"run {run.reference}: " + "; ".join(faults))


__all__ = [
    "CURRENT_SLACK",
    "VOLTAGE_SLACK",
    "Condition",
    "check_conditions",
    "check_sequence",
    "condition_faults",
    "condition_for",
    "missing_points",
    "required_points",
]
