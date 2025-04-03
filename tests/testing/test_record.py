from __future__ import annotations

from decimal import Decimal

import pytest

from kilodial.errors import RuleError
from kilodial.model.device import DeviceType
from kilodial.model.form import Technology
from kilodial.model.run import PointKind, RunKind
from kilodial.testing.record import Readings, build_run, points_from
from kilodial.units.registration import Registration


def device(**over: object) -> DeviceType:
    args: dict[str, object] = {
        "form_code": "2S",
        "class_code": "200",
        "voltage": "240",
        "kh": "7.2",
        "technology": Technology.INDUCTION,
        "register_ratio": "100",
        "introduced": "2004-05-01",
    }
    args.update(over)
    return DeviceType.build("Halvern", "R4S", **args)  # type: ignore[arg-type]


def test_readings_coerce_whatever_they_are_given() -> None:
    r = Readings.of(full_load="100.12", light_load=99.6, power_factor=Registration("99.9"))
    assert r.full_load == Registration("100.12")
    assert r.light_load == Registration("99.6")
    assert r.power_factor == Registration("99.9")
    assert r.crept is None
    assert not r.is_empty


def test_empty_readings() -> None:
    assert Readings.of().is_empty
    assert not Readings.of(crept=False).is_empty


def test_points_are_built_at_the_nominal_load() -> None:
    points = points_from(Readings.of(full_load="100.12", light_load="99.60"), device())
    assert [p.kind for p in points] == [PointKind.FULL_LOAD, PointKind.LIGHT_LOAD]
    assert points[0].amperes.value == Decimal("30.000")
    assert points[1].amperes.value == Decimal("3.000")
    assert points[0].volts.value == Decimal("240.00")


def test_the_lagging_point_gets_its_power_factor() -> None:
    points = points_from(Readings.of(power_factor="99.90"), device())
    assert str(points[0].power_factor) == "0.5 PF lagging"
    assert points[0].amperes.value == Decimal("15.000")


def test_points_come_out_in_sheet_order() -> None:
    readings = Readings.of(demand="99.1", full_load="100.1", register="100.0", light_load="99.6")
    assert [p.kind for p in points_from(readings, device())] == [
        PointKind.FULL_LOAD,
        PointKind.LIGHT_LOAD,
        PointKind.REGISTER,
        PointKind.DEMAND,
    ]


def test_creep_lands_last_and_carries_no_registration() -> None:
    points = points_from(Readings.of(full_load="100.1", crept=True), device())
    assert points[-1].kind is PointKind.CREEP
    assert points[-1].crept is True
    assert points[-1].registration is None
    assert points[-1].volts.value == Decimal("264.00")


def test_a_voltage_override_moves_every_point() -> None:
    points = points_from(Readings.of(full_load="100.1", crept=False), device(), volts="277")
    assert points[0].volts.value == Decimal("277.00")
    assert points[-1].volts.value == Decimal("304.70")


def test_nothing_to_build_from() -> None:
    with pytest.raises(RuleError, match="no readings"):
        points_from(Readings.of(), device())


def test_building_a_whole_run() -> None:
    run = build_run(
        "TR-1",
        device=device(),
        meter_serial="84-119302",
        bench_code="B2",
        standard_serial="RS-5511",
        kind=RunKind.AS_FOUND,
        tested_on="2025-03-04",
        technician="R Ellis",
        readings=Readings.of(full_load="100.12", light_load="99.60", crept=False),
        note="cover cracked",
    )
    assert run.reference == "TR-1"
    assert run.has(PointKind.CREEP)
    assert run.note == "cover cracked"
    assert run.point("FL").percent == Registration("100.12")


def test_a_class_20_meter_gets_its_own_currents() -> None:
    tight = device(form_code="9S", class_code="20")
    points = points_from(Readings.of(full_load="100.1", light_load="99.9"), tight)
    assert points[0].amperes.value == Decimal("2.500")
    assert points[1].amperes.value == Decimal("0.250")
