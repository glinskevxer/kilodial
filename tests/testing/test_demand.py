from __future__ import annotations

from decimal import Decimal

import pytest

from kilodial.errors import RuleError
from kilodial.model.demand import Interval
from kilodial.model.device import DeviceType
from kilodial.model.form import Technology
from kilodial.model.run import BenchPoint, BenchRun, RunKind
from kilodial.testing.demand import DemandOutcome, band_for, judge_demand


def device(**over: object) -> DeviceType:
    args: dict[str, object] = {
        "form_code": "16S",
        "class_code": "320",
        "voltage": "277",
        "kh": "1.8",
        "technology": Technology.SOLID_STATE,
        "demand_capable": True,
        "demand_interval": 15,
        "introduced": "2014-05-01",
    }
    args.update(over)
    return DeviceType.build("Vantage", "SM3", **args)  # type: ignore[arg-type]


def run(*, demand: str | None = "100.10", kind: RunKind = RunKind.AS_FOUND) -> BenchRun:
    points = [
        BenchPoint.build("FL", amperes="30", volts="277", registration="100.10"),
        BenchPoint.build("LL", amperes="3", volts="277", registration="99.80"),
    ]
    if demand is not None:
        points.append(BenchPoint.build("DM", amperes="15", volts="277", registration=demand))
    return BenchRun.build(
        "TR-1",
        meter_serial="84-119302",
        bench_code="B2",
        standard_serial="RS-5511",
        kind=kind,
        tested_on="2025-03-04",
        technician="R Ellis",
        points=points,
    )


def test_the_demand_band_is_tighter_than_the_energy_band() -> None:
    assert band_for(RunKind.ACCEPTANCE) == Decimal("0.5")
    assert band_for(RunKind.AS_LEFT) == Decimal("1.0")
    assert band_for(RunKind.AS_FOUND) == Decimal("2.0")


def test_a_clean_demand_test_passes() -> None:
    verdict = judge_demand(run(), device())
    assert verdict.outcome is DemandOutcome.PASSED
    assert verdict.outcome.passed
    assert verdict.registration_error == Decimal("0.1000")
    assert verdict.why() == "passed"
    assert str(verdict) == "TR-1 demand passed at 100.10%"


def test_a_fast_demand_register_fails() -> None:
    verdict = judge_demand(run(demand="104.00"), device())
    assert verdict.outcome is DemandOutcome.REGISTRATION
    assert "outside the +/-2.0 percent band" in verdict.why()


def test_a_meter_can_pass_as_found_and_fail_as_left_on_demand() -> None:
    assert judge_demand(run(demand="101.40"), device()).outcome.passed
    tighter = judge_demand(run(demand="101.40", kind=RunKind.AS_LEFT), device())
    assert tighter.outcome is DemandOutcome.REGISTRATION


def test_a_run_with_no_demand_point_was_not_tested() -> None:
    verdict = judge_demand(run(demand=None), device())
    assert verdict.outcome is DemandOutcome.NOT_TESTED
    assert not verdict.outcome.was_tested
    assert not verdict.outcome.passed
    assert verdict.registration is None


def test_a_meter_that_does_not_register_demand() -> None:
    plain = device(demand_capable=False, demand_interval=None)
    assert judge_demand(run(demand=None), plain).outcome is DemandOutcome.NOT_TESTED
    with pytest.raises(RuleError, match="does not register demand"):
        judge_demand(run(), plain)


def test_the_interval_clock_is_checked_when_it_was_measured() -> None:
    verdict = judge_demand(run(), device(), interval=Interval.MIN_15, measured_seconds="900")
    assert verdict.outcome.passed
    assert verdict.timing == Decimal("0.0000")
    assert verdict.interval is Interval.MIN_15


def test_a_drifting_interval_clock_fails_on_its_own() -> None:
    verdict = judge_demand(run(), device(), interval=Interval.MIN_15, measured_seconds="880")
    assert verdict.outcome is DemandOutcome.TIMING
    assert "window measured" in verdict.why()
    assert verdict.registration is not None


def test_both_can_be_wrong_at_once() -> None:
    verdict = judge_demand(
        run(demand="104.00"), device(), interval=Interval.MIN_15, measured_seconds="880"
    )
    assert verdict.outcome is DemandOutcome.BOTH
    assert len(verdict.reasons) == 2
    assert str(verdict.outcome) == "failed on registration and on the interval clock"


def test_the_clock_cannot_be_checked_without_an_interval() -> None:
    with pytest.raises(RuleError, match="needs the interval"):
        judge_demand(run(), device(), measured_seconds="900")


def test_timing_is_not_checked_when_it_was_not_measured() -> None:
    verdict = judge_demand(run(), device(), interval=Interval.MIN_15)
    assert verdict.timing is None
    assert verdict.outcome.passed
