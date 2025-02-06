from __future__ import annotations

from decimal import Decimal

import pytest

from kilodial.errors import RuleError
from kilodial.model.run import BenchPoint, BenchRun, PointKind, RunKind
from kilodial.testing.weighted import (
    WEIGHTS,
    required_kinds,
    weighted_average,
    weights_for,
)
from kilodial.units.electrical import PowerFactor


def point(kind: str, pct: str, pf: PowerFactor | None = None) -> BenchPoint:
    return BenchPoint.build(kind, amperes="30", volts="240", registration=pct, power_factor=pf)


def run_with(*points: BenchPoint) -> BenchRun:
    return BenchRun.build(
        "TR-1",
        meter_serial="84-119302",
        bench_code="B2",
        standard_serial="RS-5511",
        kind=RunKind.AS_FOUND,
        tested_on="2025-03-04",
        technician="R Ellis",
        points=list(points),
    )


def test_every_weighting_row_adds_to_five() -> None:
    for row in WEIGHTS.values():
        assert sum(row.values()) == 5


def test_a_single_element_meter_ignores_the_power_factor_point() -> None:
    assert required_kinds(Decimal("1")) == frozenset({PointKind.FULL_LOAD, PointKind.LIGHT_LOAD})
    run = run_with(
        point("FL", "100.00"),
        point("LL", "99.00"),
        point("PF", "50.00", PowerFactor.lagging("0.5")),
    )
    wa = weighted_average(run, Decimal("1"))
    assert wa.value.percent == Decimal("99.8000")
    assert [k for k, _, _ in wa.parts] == [PointKind.FULL_LOAD, PointKind.LIGHT_LOAD]


def test_a_three_element_meter_leans_on_the_lagging_point() -> None:
    run = run_with(
        point("FL", "100.00"),
        point("LL", "100.00"),
        point("PF", "95.00", PowerFactor.lagging("0.5")),
    )
    wa = weighted_average(run, Decimal("3"))
    assert wa.value.percent == Decimal("98.0000")


def test_the_same_run_averages_differently_by_element_count() -> None:
    run = run_with(
        point("FL", "100.00"),
        point("LL", "98.00"),
        point("PF", "96.00", PowerFactor.lagging("0.5")),
    )
    assert weighted_average(run, Decimal("1")).value.percent == Decimal("99.6000")
    assert weighted_average(run, Decimal("2")).value.percent == Decimal("98.8000")
    assert weighted_average(run, Decimal("3")).value.percent == Decimal("98.0000")


def test_the_two_and_a_half_element_row_matches_the_two_element_row() -> None:
    assert WEIGHTS[Decimal("2.5")] == WEIGHTS[Decimal("2")]


def test_a_polyphase_run_without_a_lagging_point_is_refused() -> None:
    run = run_with(point("FL", "100.00"), point("LL", "99.00"))
    with pytest.raises(RuleError, match="missing the power_factor point"):
        weighted_average(run, Decimal("3"))


def test_a_run_missing_light_load() -> None:
    run = run_with(point("FL", "100.00"))
    with pytest.raises(RuleError, match="missing the light_load point"):
        weighted_average(run, Decimal("1"))


def test_an_element_count_nobody_weights() -> None:
    with pytest.raises(RuleError, match="no weighting is defined"):
        weights_for(Decimal("4"))


def test_the_working_is_kept_and_printable() -> None:
    run = run_with(
        point("FL", "100.24"),
        point("LL", "99.10"),
    )
    wa = weighted_average(run, Decimal("1"))
    assert wa.divisor == 5
    assert wa.show() == "(4x100.24 + 1x99.10) / 5 = 100.01"
    assert str(wa) == "100.01%"
    assert wa.elements == Decimal("1")
