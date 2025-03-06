"""Turning records into rows and rows back into records.

Everything numeric is stored as text. That looks wasteful until the first time
somebody stores a registration as a REAL and gets 99.86999999999999 back out of
a book that a hearing is going to be run off. sqlite has no decimal type, so the
choice is text or a scaled integer, and text keeps the book readable with the
sqlite3 shell, which the shop supervisor genuinely does use.

Booleans go in as 0 and 1 because sqlite has no boolean either, and the tri
state on a creep point (crept, held, not applicable) needs NULL to stay
distinguishable from held.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from kilodial.errors import ConfigError
from kilodial.model.bench import Bench, ReferenceStandard
from kilodial.model.device import DeviceType
from kilodial.model.form import Technology, form, meter_class
from kilodial.model.meter import Meter, MeterState
from kilodial.model.run import BenchPoint, BenchRun, PointKind, RunKind
from kilodial.units.electrical import Amperes, PowerFactor, Sense, Volts
from kilodial.units.registration import Registration
from kilodial.units.span import parse_date

Row = tuple[Any, ...]


def _bool(value: object) -> int:
    return 1 if value else 0


def _maybe_date(value: object) -> str | None:
    return None if value is None else parse_date(value).isoformat()


def _enum(cls: type[Any], value: object, what: str) -> Any:
    for member in cls:
        if member.value == value or member.name == value:
            return member
    raise ConfigError(f"the book holds {value!r}, which is not a {what}")


def device_row(device: DeviceType) -> Row:
    return (
        device.manufacturer,
        device.model_code,
        device.form.code,
        device.meter_class.code,
        str(device.voltage.value),
        str(device.kh),
        device.technology.value,
        None if device.register_ratio is None else str(device.register_ratio),
        _bool(device.demand_capable),
        device.introduced.isoformat(),
        _maybe_date(device.retired),
    )


def read_device(row: Row) -> DeviceType:
    return DeviceType(
        manufacturer=str(row[0]),
        model_code=str(row[1]),
        form=form(row[2]),
        meter_class=meter_class(row[3]),
        voltage=Volts(str(row[4])),
        kh=Decimal(str(row[5])),
        technology=_enum(Technology, row[6], "technology"),
        register_ratio=None if row[7] is None else Decimal(str(row[7])),
        demand_capable=bool(row[8]),
        introduced=parse_date(str(row[9])),
        retired=None if row[10] is None else parse_date(str(row[10])),
    )


def meter_row(meter: Meter) -> Row:
    return (
        meter.serial,
        meter.device_key,
        meter.state.value,
        meter.acquired.isoformat(),
        meter.owner,
        meter.seal,
        _maybe_date(meter.retired_on),
    )


def read_meter(row: Row) -> Meter:
    return Meter(
        serial=str(row[0]),
        device_key=str(row[1]),
        state=_enum(MeterState, row[2], "meter state"),
        acquired=parse_date(str(row[3])),
        owner=str(row[4]),
        seal=None if row[5] is None else str(row[5]),
        retired_on=None if row[6] is None else parse_date(str(row[6])),
    )


def standard_row(standard: ReferenceStandard) -> Row:
    return (
        standard.serial,
        standard.maker,
        standard.model_code,
        standard.certificate,
        standard.certified_on.isoformat(),
        standard.certificate_due.isoformat(),
        str(standard.uncertainty),
        standard.traceable_to,
    )


def read_standard(row: Row) -> ReferenceStandard:
    return ReferenceStandard(
        serial=str(row[0]),
        maker=str(row[1]),
        model_code=str(row[2]),
        certificate=str(row[3]),
        certified_on=parse_date(str(row[4])),
        certificate_due=parse_date(str(row[5])),
        uncertainty=Decimal(str(row[6])),
        traceable_to=str(row[7]),
    )


def bench_row(bench: Bench) -> Row:
    return (
        bench.code,
        bench.name,
        bench.positions,
        bench.standard_serial,
        str(bench.max_amperes.value),
        str(bench.max_volts.value),
        _bool(bench.polyphase),
        bench.installed.isoformat(),
        _maybe_date(bench.removed),
    )


def read_bench(row: Row) -> Bench:
    return Bench(
        code=str(row[0]),
        name=str(row[1]),
        positions=int(row[2]),
        standard_serial=str(row[3]),
        max_amperes=Amperes(str(row[4])),
        max_volts=Volts(str(row[5])),
        polyphase=bool(row[6]),
        installed=parse_date(str(row[7])),
        removed=None if row[8] is None else parse_date(str(row[8])),
    )


def run_row(run: BenchRun) -> Row:
    return (
        run.reference,
        run.meter_serial,
        run.bench_code,
        run.standard_serial,
        run.kind.value,
        run.tested_on.isoformat(),
        run.technician,
        run.note,
    )


def read_run(row: Row, points: list[BenchPoint]) -> BenchRun:
    return BenchRun(
        reference=str(row[0]),
        meter_serial=str(row[1]),
        bench_code=str(row[2]),
        standard_serial=str(row[3]),
        kind=_enum(RunKind, row[4], "run kind"),
        tested_on=parse_date(str(row[5])),
        technician=str(row[6]),
        points=tuple(points),
        note=None if row[7] is None else str(row[7]),
    )


def point_row(reference: str, position: int, point: BenchPoint) -> Row:
    return (
        reference,
        position,
        point.kind.code,
        str(point.amperes.value),
        str(point.volts.value),
        str(point.power_factor.value),
        point.power_factor.sense.value,
        None if point.registration is None else str(point.registration.percent),
        None if point.crept is None else _bool(point.crept),
    )


def read_point(row: Row) -> BenchPoint:
    kind = _point_kind(row[2])
    sense = _enum(Sense, row[6], "power factor sense")
    return BenchPoint(
        kind=kind,
        amperes=Amperes(str(row[3])),
        volts=Volts(str(row[4])),
        power_factor=PowerFactor(str(row[5]), sense),
        registration=None if row[7] is None else Registration(str(row[7])),
        crept=None if row[8] is None else bool(row[8]),
    )


def _point_kind(code: object) -> PointKind:
    for member in PointKind:
        if member.code == code:
            return member
    raise ConfigError(f"the book holds {code!r}, which is not a test point kind")


__all__ = [
    "bench_row",
    "device_row",
    "meter_row",
    "point_row",
    "read_bench",
    "read_device",
    "read_meter",
    "read_point",
    "read_run",
    "read_standard",
    "run_row",
    "standard_row",
]
