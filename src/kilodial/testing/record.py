"""Building a run from the readings a technician actually writes down.

Nobody records the load. A technician records six percentages and whether the
disc moved, because the bench held the nominal load and everyone in the shop
knows what the nominal load for a class 200 meter is. So the readings are the
input and the conditions are derived from the device type, which is the only
place that pairing is written down.

The override exists because it has to. A meter set on a 277 volt service gets
tested at 277 rather than at its nameplate 240, and a run that records the
nameplate voltage when the bench held something else is a lie in the record even
though every number in it is right.
"""

from __future__ import annotations

from dataclasses import dataclass

from kilodial.errors import RuleError
from kilodial.model.device import DeviceType
from kilodial.model.run import BenchPoint, BenchRun, PointKind, RunKind
from kilodial.testing.sequence import condition_for
from kilodial.units.electrical import Volts
from kilodial.units.registration import Registration

ORDER = (
    PointKind.FULL_LOAD,
    PointKind.LIGHT_LOAD,
    PointKind.POWER_FACTOR,
    PointKind.HEAVY_LOAD,
    PointKind.REGISTER,
    PointKind.DEMAND,
)


@dataclass(frozen=True)
class Readings:
    """What came off the bench, in the order the shop sheet lists it."""

    full_load: Registration | None = None
    light_load: Registration | None = None
    power_factor: Registration | None = None
    heavy_load: Registration | None = None
    register: Registration | None = None
    demand: Registration | None = None
    crept: bool | None = None

    @classmethod
    def of(
        cls,
        *,
        full_load: object = None,
        light_load: object = None,
        power_factor: object = None,
        heavy_load: object = None,
        register: object = None,
        demand: object = None,
        crept: bool | None = None,
    ) -> Readings:
        """Build from whatever the caller has, coercing each percentage."""
        return cls(
            full_load=_reading(full_load),
            light_load=_reading(light_load),
            power_factor=_reading(power_factor),
            heavy_load=_reading(heavy_load),
            register=_reading(register),
            demand=_reading(demand),
            crept=None if crept is None else bool(crept),
        )

    def get(self, kind: PointKind) -> Registration | None:
        return {
            PointKind.FULL_LOAD: self.full_load,
            PointKind.LIGHT_LOAD: self.light_load,
            PointKind.POWER_FACTOR: self.power_factor,
            PointKind.HEAVY_LOAD: self.heavy_load,
            PointKind.REGISTER: self.register,
            PointKind.DEMAND: self.demand,
        }.get(kind)

    @property
    def is_empty(self) -> bool:
        return all(self.get(k) is None for k in ORDER) and self.crept is None


def _reading(value: object) -> Registration | None:
    if value is None:
        return None
    if isinstance(value, Registration):
        return value
    return Registration(value)


def points_from(
    readings: Readings, device: DeviceType, *, volts: object = None
) -> list[BenchPoint]:
    """Turn readings into points at the nominal load for that device type."""
    if readings.is_empty:
        raise RuleError("there are no readings to build a run from")
    override = None if volts is None else Volts(volts)
    built: list[BenchPoint] = []
    for kind in ORDER:
        reading = readings.get(kind)
        if reading is None:
            continue
        condition = condition_for(device, kind)
        built.append(
            BenchPoint(
                kind=kind,
                amperes=condition.amperes,
                volts=condition.volts if override is None else override,
                power_factor=condition.power_factor,
                registration=reading,
                crept=None,
            )
        )
    if readings.crept is not None:
        condition = condition_for(device, PointKind.CREEP)
        built.append(
            BenchPoint(
                kind=PointKind.CREEP,
                amperes=condition.amperes,
                volts=condition.volts if override is None else _over_voltage(override),
                power_factor=condition.power_factor,
                registration=None,
                crept=readings.crept,
            )
        )
    return built


def _over_voltage(volts: Volts) -> Volts:
    """Creep runs ten percent over whatever the service voltage was."""
    return Volts(volts.value * 11 / 10)


def build_run(
    reference: str,
    *,
    device: DeviceType,
    meter_serial: str,
    bench_code: str,
    standard_serial: str,
    kind: RunKind,
    tested_on: object,
    technician: str,
    readings: Readings,
    note: object = None,
    volts: object = None,
    demand_seconds: object = None,
) -> BenchRun:
    """Assemble a whole run from readings."""
    return BenchRun.build(
        reference,
        meter_serial=meter_serial,
        bench_code=bench_code,
        standard_serial=standard_serial,
        kind=kind,
        tested_on=tested_on,
        technician=technician,
        points=points_from(readings, device, volts=volts),
        note=note,
        demand_seconds=demand_seconds,
    )


__all__ = ["ORDER", "Readings", "build_run", "points_from"]
