from __future__ import annotations

from datetime import date

import pytest

from kilodial.errors import BadInputError, RuleError
from kilodial.model.run import (
    BenchPoint,
    BenchRun,
    PointKind,
    RunKind,
    point_kind,
)
from kilodial.units.electrical import PowerFactor
from kilodial.units.registration import Registration


def fl(pct: str = "100.12") -> BenchPoint:
    return BenchPoint.build("FL", amperes="30", volts="240", registration=pct)


def ll(pct: str = "99.60") -> BenchPoint:
    return BenchPoint.build("LL", amperes="3", volts="240", registration=pct)


def pf(pct: str = "99.90") -> BenchPoint:
    return BenchPoint.build(
        "PF",
        amperes="15",
        volts="240",
        power_factor=PowerFactor.lagging("0.5"),
        registration=pct,
    )


def creep(moved: bool = False) -> BenchPoint:
    return BenchPoint.build("CR", amperes="0", volts="264", crept=moved)


def a_run(**over: object) -> BenchRun:
    args: dict[str, object] = {
        "meter_serial": "84-119302",
        "bench_code": "B2",
        "standard_serial": "RS-5511",
        "kind": RunKind.AS_FOUND,
        "tested_on": "2025-03-04",
        "technician": "R Ellis",
        "points": [fl(), ll(), creep()],
    }
    args.update(over)
    ref = args.pop("reference", "TR-2025-0441")
    return BenchRun.build(ref, **args)  # type: ignore[arg-type]


def test_point_kind_lookup() -> None:
    assert point_kind("fl") is PointKind.FULL_LOAD
    assert point_kind("POWER_FACTOR") is PointKind.POWER_FACTOR
    assert point_kind(PointKind.CREEP) is PointKind.CREEP


@pytest.mark.parametrize("bad", ["ZZ", "", None, 3])
def test_bad_point_kinds(bad: object) -> None:
    with pytest.raises(BadInputError):
        point_kind(bad)


def test_which_kinds_are_weighted() -> None:
    assert PointKind.FULL_LOAD.weighted
    assert PointKind.LIGHT_LOAD.weighted
    assert PointKind.POWER_FACTOR.weighted
    assert not PointKind.HEAVY_LOAD.weighted
    assert not PointKind.CREEP.weighted


def test_a_load_point_carries_a_registration() -> None:
    p = fl("100.12")
    assert p.percent == Registration("100.12")
    assert p.crept is None
    assert str(p) == "FL 100.12%"


def test_a_load_point_without_a_registration_is_refused() -> None:
    with pytest.raises(RuleError, match="needs a registration"):
        BenchPoint.build("FL", amperes="30", volts="240")


def test_a_load_point_cannot_record_creep() -> None:
    with pytest.raises(RuleError, match="only a creep point"):
        BenchPoint.build("FL", amperes="30", volts="240", registration="100", crept=False)


def test_a_creep_point() -> None:
    held = creep(False)
    assert held.registration is None
    assert held.crept is False
    assert str(held) == "CR held"
    assert str(creep(True)) == "CR crept"
    with pytest.raises(RuleError, match="has no registration"):
        _ = held.percent


def test_a_creep_point_needs_an_answer() -> None:
    with pytest.raises(RuleError, match="whether the disc moved"):
        BenchPoint.build("CR", amperes="0", volts="264")
    with pytest.raises(RuleError, match="no registration to record"):
        BenchPoint.build("CR", amperes="0", volts="264", registration="100", crept=False)


def test_the_default_power_factor_is_unity() -> None:
    assert fl().power_factor.is_unity
    assert pf().power_factor.sense.value == "lagging"
    with pytest.raises(BadInputError, match="PowerFactor"):
        BenchPoint.build("FL", amperes="30", volts="240", registration="100", power_factor="0.5")  # type: ignore[arg-type]


def test_a_run_holds_its_points_in_order() -> None:
    run = a_run(points=[ll(), fl(), pf()])
    assert [p.kind for p in run.points] == [
        PointKind.LIGHT_LOAD,
        PointKind.FULL_LOAD,
        PointKind.POWER_FACTOR,
    ]
    assert run.tested_on == date(2025, 3, 4)
    assert run.reference == "TR-2025-0441"


def test_a_run_with_no_points() -> None:
    with pytest.raises(RuleError, match="not a run"):
        a_run(points=[])


def test_a_run_cannot_hold_the_same_kind_twice() -> None:
    with pytest.raises(RuleError, match="two full_load points"):
        a_run(points=[fl(), fl("99")])


def test_a_run_holds_test_points_and_nothing_else() -> None:
    with pytest.raises(BadInputError, match="holds bench points"):
        a_run(points=[fl(), "LL 99.6"])


def test_point_lookup() -> None:
    run = a_run()
    assert run.point("FL").percent == Registration("100.12")
    assert run.has("CR")
    assert not run.has("PF")
    with pytest.raises(RuleError, match="no power_factor point"):
        run.point("PF")


def test_which_runs_can_move_money() -> None:
    assert RunKind.AS_FOUND.bills
    assert RunKind.REFEREE.bills
    assert not RunKind.AS_LEFT.bills
    assert not RunKind.ACCEPTANCE.bills
    assert str(RunKind.AS_LEFT) == "as left"


@pytest.mark.parametrize("bad", ["", "TR 2025", "x" * 30, None])
def test_bad_run_references(bad: object) -> None:
    with pytest.raises(BadInputError):
        a_run(reference=bad)


@pytest.mark.parametrize("bad", ["", "   ", "x" * 50, None])
def test_bad_technician_names(bad: object) -> None:
    with pytest.raises(BadInputError):
        a_run(technician=bad)


def test_notes_are_tidied_and_bounded() -> None:
    assert a_run(note="  cover   cracked ").note == "cover cracked"
    assert a_run(note="  ").note is None
    assert a_run().note is None
    with pytest.raises(BadInputError, match="240 characters"):
        a_run(note="x" * 300)
    with pytest.raises(BadInputError):
        a_run(note=7)


def test_a_run_kind_that_is_not_one() -> None:
    with pytest.raises(BadInputError, match="RunKind"):
        a_run(kind="as found")


def test_str_of_a_run() -> None:
    assert str(a_run()) == "TR-2025-0441 84-119302 as found 2025-03-04"
