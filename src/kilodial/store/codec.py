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
from kilodial.install.point import MeterSet, ServicePoint
from kilodial.model.bench import Bench, ReferenceStandard
from kilodial.model.device import DeviceType
from kilodial.model.form import Service, Technology, form, meter_class
from kilodial.model.meter import Meter, MeterState
from kilodial.model.run import BenchPoint, BenchRun, PointKind, RunKind
from kilodial.sampling.decision import Decision
from kilodial.sampling.group import Group
from kilodial.sampling.plan import DEFAULT_BAND, SampleOutcome, required
from kilodial.units.electrical import Amperes, PowerFactor, Sense, Volts
from kilodial.units.registration import Registration
from kilodial.units.span import parse_date
from kilodial.xfmr.transformer import (
    AccuracyClass,
    InstrumentTransformer,
    TransformerKind,
    accuracy_class,
)

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
    """The device as a row, in the column order the table is declared in."""
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
    """The device back off a row, refusing a value the book should not hold."""
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
    """The meter as a row, in the column order the table is declared in."""
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
    """The meter back off a row, refusing a value the book should not hold."""
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
    """The standard as a row, in the column order the table is declared in."""
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
    """The standard back off a row, refusing a value the book should not hold."""
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
    """The bench as a row, in the column order the table is declared in."""
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
    """The bench back off a row, refusing a value the book should not hold."""
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
    """The run as a row, in the column order the table is declared in."""
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
    """The run back off a row, refusing a value the book should not hold."""
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
    """The point as a row, in the column order the table is declared in."""
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
    """The point back off a row, refusing a value the book should not hold."""
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


def transformer_row(transformer: InstrumentTransformer) -> Row:
    """The transformer as a row, in the column order the table is declared in."""
    return (
        transformer.serial,
        transformer.kind.value,
        transformer.maker,
        str(transformer.marked_ratio),
        transformer.accuracy.code,
        str(transformer.rcf),
        str(transformer.phase_minutes),
        transformer.burden,
        transformer.tested_on.isoformat(),
    )


def read_transformer(row: Row) -> InstrumentTransformer:
    """The transformer back off a row, refusing a value the book should not hold."""
    return InstrumentTransformer(
        serial=str(row[0]),
        kind=_enum(TransformerKind, row[1], "transformer kind"),
        maker=str(row[2]),
        marked_ratio=Decimal(str(row[3])),
        accuracy=_accuracy(row[4]),
        rcf=Decimal(str(row[5])),
        phase_minutes=Decimal(str(row[6])),
        burden=str(row[7]),
        tested_on=parse_date(str(row[8])),
    )


def _accuracy(code: object) -> AccuracyClass:
    try:
        return accuracy_class(code)
    except Exception:
        raise ConfigError(f"the book holds {code!r}, which is not an accuracy class") from None


def service_point_row(point: ServicePoint) -> Row:
    """The service point as a row, in the column order the table is declared in."""
    return (
        point.code,
        point.account,
        point.address,
        point.service.value,
        str(point.voltage.value),
        point.rate_code,
        point.energised.isoformat(),
        _maybe_date(point.disconnected),
    )


def read_service_point(row: Row) -> ServicePoint:
    """The service point back off a row, refusing a value the book should not hold."""
    return ServicePoint(
        code=str(row[0]),
        account=str(row[1]),
        address=str(row[2]),
        service=_enum(Service, row[3], "service"),
        voltage=Volts(str(row[4])),
        rate_code=str(row[5]),
        energised=parse_date(str(row[6])),
        disconnected=None if row[7] is None else parse_date(str(row[7])),
    )


def meter_set_row(meter_set: MeterSet) -> Row:
    """The meter set as a row, in the column order the table is declared in."""
    return (
        meter_set.point_code,
        meter_set.meter_serial,
        meter_set.ct_serial,
        meter_set.vt_serial,
        str(meter_set.register_multiplier),
        str(meter_set.programmed_multiplier),
        meter_set.set_on.isoformat(),
        _maybe_date(meter_set.removed_on),
    )


def read_meter_set(row: Row) -> MeterSet:
    """The meter set back off a row, refusing a value the book should not hold."""
    return MeterSet(
        point_code=str(row[0]),
        meter_serial=str(row[1]),
        ct_serial=None if row[2] is None else str(row[2]),
        vt_serial=None if row[3] is None else str(row[3]),
        register_multiplier=Decimal(str(row[4])),
        programmed_multiplier=Decimal(str(row[5])),
        set_on=parse_date(str(row[6])),
        removed_on=None if row[7] is None else parse_date(str(row[7])),
    )


def group_row(group: Group) -> Row:
    """The group as a row, in the column order the table is declared in."""
    return (
        group.code,
        group.name,
        " ".join(group.device_keys),
        None if group.meter_class is None else group.meter_class.code,
        None if group.technology is None else group.technology.value,
        " ".join(group.form_codes),
        _maybe_date(group.acquired_from),
        _maybe_date(group.acquired_to),
    )


def read_group(row: Row) -> Group:
    """The group back off a row, refusing a value the book should not hold."""
    return Group(
        code=str(row[0]),
        name=str(row[1]),
        device_keys=tuple(str(row[2]).split()),
        meter_class=None if row[3] is None else meter_class(row[3]),
        technology=None if row[4] is None else _enum(Technology, row[4], "technology"),
        form_codes=tuple(str(row[5]).split()),
        acquired_from=None if row[6] is None else parse_date(str(row[6])),
        acquired_to=None if row[7] is None else parse_date(str(row[7])),
    )


def plan_row(decision: Decision) -> Row:
    """The plan as a row, in the column order the table is declared in."""
    return (
        decision.group_code,
        decision.decided_on.isoformat(),
        0 if decision.interval_months is None else decision.interval_months,
        decision.outcome.population,
        decision.outcome.tested,
        str(decision.outcome.mean),
        str(decision.outcome.deviation),
        decision.outcome.failures,
        _bool(decision.passed),
        decision.note,
    )


def read_plan(row: Row, previous_months: int) -> Decision:
    """The plan back off a row, refusing a value the book should not hold."""
    months = int(row[2])
    outcome = SampleOutcome(
        population=int(row[3]),
        required=required(int(row[3])),
        tested=int(row[4]),
        mean=Decimal(str(row[5])),
        deviation=Decimal(str(row[6])),
        failures=int(row[7]),
        band=DEFAULT_BAND,
        reasons=() if row[8] else ("recorded as a failure",),
    )
    return Decision(
        group_code=str(row[0]),
        decided_on=parse_date(str(row[1])),
        previous_months=previous_months,
        interval_months=None if months == 0 else months,
        outcome=outcome,
        note=None if row[9] is None else str(row[9]),
    )


def _point_kind(code: object) -> PointKind:
    for member in PointKind:
        if member.code == code:
            return member
    raise ConfigError(f"the book holds {code!r}, which is not a test point kind")


__all__ = [
    "Row",
    "bench_row",
    "device_row",
    "group_row",
    "meter_row",
    "meter_set_row",
    "plan_row",
    "point_row",
    "read_bench",
    "read_device",
    "read_group",
    "read_meter",
    "read_meter_set",
    "read_plan",
    "read_point",
    "read_run",
    "read_service_point",
    "read_standard",
    "read_transformer",
    "run_row",
    "service_point_row",
    "standard_row",
    "transformer_row",
]
