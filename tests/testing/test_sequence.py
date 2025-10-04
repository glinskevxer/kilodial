from __future__ import annotations

from decimal import Decimal

import pytest

from kilodial.errors import RuleError
from kilodial.model.device import DeviceType
from kilodial.model.form import Technology
from kilodial.model.run import BenchPoint, BenchRun, PointKind, RunKind
from kilodial.testing.sequence import (
    check_conditions,
    check_sequence,
    condition_faults,
    condition_for,
    missing_points,
    required_points,
)
from kilodial.units.electrical import PowerFactor


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


def point(kind: str, **over: object) -> BenchPoint:
    args: dict[str, object] = {"amperes": "30", "volts": "240", "registration": "100.00"}
    if kind == "CR":
        args = {"amperes": "0", "volts": "264", "crept": False}
    args.update(over)
    return BenchPoint.build(kind, **args)  # type: ignore[arg-type]


def run_with(*points: BenchPoint, kind: RunKind = RunKind.AS_FOUND) -> BenchRun:
    return BenchRun.build(
        "TR-1",
        meter_serial="84-119302",
        bench_code="B2",
        standard_serial="RS-5511",
        kind=kind,
        tested_on="2025-03-04",
        technician="R Ellis",
        points=list(points),
    )


def test_nominal_conditions_come_off_the_class_and_the_nameplate() -> None:
    d = device()
    assert condition_for(d, PointKind.FULL_LOAD).amperes.value == Decimal("30.000")
    assert condition_for(d, PointKind.LIGHT_LOAD).amperes.value == Decimal("3.000")
    assert condition_for(d, PointKind.POWER_FACTOR).amperes.value == Decimal("15.000")
    assert condition_for(d, PointKind.HEAVY_LOAD).amperes.value == Decimal("60.000")
    assert condition_for(d, PointKind.REGISTER).amperes.value == Decimal("30.000")
    assert condition_for(d, PointKind.DEMAND).amperes.value == Decimal("15.000")


def test_the_lagging_point_is_half_a_power_factor_lagging() -> None:
    pf = condition_for(device(), PointKind.POWER_FACTOR).power_factor
    assert pf == PowerFactor.lagging("0.5")


def test_creep_runs_at_no_load_and_ten_percent_over_voltage() -> None:
    c = condition_for(device(), PointKind.CREEP)
    assert c.amperes.value == Decimal("0.000")
    assert c.volts.value == Decimal("264.00")
    assert str(c) == "0 A 264 V 1.0 PF"


def test_a_single_element_as_found_sequence_is_two_points() -> None:
    assert required_points(device(), RunKind.AS_FOUND) == frozenset(
        {PointKind.FULL_LOAD, PointKind.LIGHT_LOAD}
    )


def test_a_polyphase_sequence_needs_the_lagging_point() -> None:
    poly = device(form_code="16S", class_code="320")
    assert PointKind.POWER_FACTOR in required_points(poly, RunKind.AS_FOUND)


def test_an_induction_meter_owes_a_creep_point_on_the_way_out() -> None:
    d = device()
    assert PointKind.CREEP not in required_points(d, RunKind.AS_FOUND)
    assert PointKind.CREEP in required_points(d, RunKind.AS_LEFT)
    assert PointKind.CREEP in required_points(d, RunKind.ACCEPTANCE)


def test_a_referee_run_does_not_owe_a_creep_point() -> None:
    assert PointKind.CREEP not in required_points(device(), RunKind.REFEREE)


def test_a_solid_state_meter_is_never_asked_to_creep() -> None:
    ss = device(technology=Technology.SOLID_STATE, register_ratio=None)
    for kind in RunKind:
        assert PointKind.CREEP not in required_points(ss, kind)


def test_acceptance_of_an_induction_meter_wants_a_register_check() -> None:
    assert PointKind.REGISTER in required_points(device(), RunKind.ACCEPTANCE)
    assert PointKind.REGISTER not in required_points(device(), RunKind.AS_LEFT)


def test_a_demand_meter_owes_a_demand_point_on_acceptance_only() -> None:
    d = device(demand_capable=True, demand_interval=15)
    assert PointKind.DEMAND in required_points(d, RunKind.ACCEPTANCE)
    assert PointKind.DEMAND not in required_points(d, RunKind.AS_LEFT)


def test_missing_points_are_named() -> None:
    run = run_with(point("FL"), kind=RunKind.AS_LEFT)
    assert missing_points(run, device()) == frozenset({PointKind.LIGHT_LOAD, PointKind.CREEP})
    with pytest.raises(RuleError, match="missing its creep, light_load point"):
        check_sequence(run, device())


def test_a_complete_sequence_passes_quietly() -> None:
    run = run_with(point("FL"), point("LL", amperes="3"))
    check_sequence(run, device())


def test_a_full_load_point_run_at_light_load_current_is_caught() -> None:
    bad = point("FL", amperes="3")
    faults = condition_faults(bad, device())
    assert faults == ["full_load was run at 3 A, nominal is 30 A"]


def test_five_percent_of_slack_is_allowed() -> None:
    assert condition_faults(point("FL", amperes="31.5"), device()) == []
    assert condition_faults(point("FL", amperes="31.6"), device()) != []


def test_a_point_run_at_the_wrong_voltage() -> None:
    faults = condition_faults(point("FL", volts="120"), device())
    assert faults == ["full_load was run at 120 V, nominal is 240 V"]


def test_a_lagging_point_run_at_unity() -> None:
    flat = BenchPoint.build("PF", amperes="15", volts="240", registration="100")
    assert condition_faults(flat, device()) == [
        "power_factor was run at 1.0 PF, nominal is 0.5 PF lagging"
    ]


def test_a_lagging_point_run_at_the_wrong_power_factor() -> None:
    off = BenchPoint.build(
        "PF",
        amperes="15",
        volts="240",
        registration="100",
        power_factor=PowerFactor.lagging("0.8"),
    )
    assert condition_faults(off, device()) == [
        "power_factor was run at 0.8 PF lagging, nominal is 0.5 PF lagging"
    ]


def test_creep_run_under_load_is_caught() -> None:
    crept = BenchPoint.build("CR", amperes="1", volts="264", crept=False)
    assert condition_faults(crept, device()) == ["creep was run at 1 A rather than no load"]


def test_check_conditions_collects_every_fault() -> None:
    run = run_with(point("FL", amperes="3"), point("LL", amperes="3", volts="120"))
    with pytest.raises(RuleError, match="full_load was run at 3 A.*light_load was run at 120 V"):
        check_conditions(run, device())


def test_check_conditions_passes_a_clean_run() -> None:
    run = run_with(point("FL"), point("LL", amperes="3"))
    check_conditions(run, device())
