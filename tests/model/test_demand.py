from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from kilodial.errors import BadInputError, RuleError
from kilodial.model.demand import (
    TIMING_BAND,
    DemandKind,
    DemandRegister,
    Interval,
    demand_kind,
    demand_registration,
    interval_of,
    timing_error,
    timing_holds,
)
from kilodial.units.registration import Registration


def block(**over: object) -> DemandRegister:
    args: dict[str, object] = {"interval": Interval.MIN_15}
    args.update(over)
    return DemandRegister.build(**args)  # type: ignore[arg-type]


def test_interval_lookup() -> None:
    assert interval_of(15) is Interval.MIN_15
    assert interval_of("15") is Interval.MIN_15
    assert interval_of("15 minute") is Interval.MIN_15
    assert interval_of(Interval.MIN_60) is Interval.MIN_60


@pytest.mark.parametrize("bad", ["20", "", None, "quarter hour"])
def test_an_interval_nobody_meters(bad: object) -> None:
    with pytest.raises(BadInputError, match="demand interval"):
        interval_of(bad)


def test_the_interval_carries_its_seconds() -> None:
    assert Interval.MIN_15.seconds == Decimal(900)
    assert str(Interval.MIN_30) == "30 minute"


def test_demand_kind_lookup() -> None:
    assert demand_kind("rolling") is DemandKind.ROLLING
    assert demand_kind(DemandKind.BLOCK) is DemandKind.BLOCK
    with pytest.raises(BadInputError, match="demand kind"):
        demand_kind("sliding")


def test_a_block_register() -> None:
    register = block()
    assert register.kind is DemandKind.BLOCK
    assert register.subintervals == 1
    assert register.subinterval_minutes == Decimal("15.00")
    assert not register.was_reset
    assert str(register) == "block 15 minute, holding 0 kW"


def test_a_rolling_register() -> None:
    register = block(kind="rolling", subintervals=3)
    assert register.subinterval_minutes == Decimal("5.00")
    assert "rolling 3x5 minute" in str(register)


def test_a_block_register_cannot_have_subintervals() -> None:
    with pytest.raises(RuleError, match="one subinterval"):
        block(subintervals=3)


def test_a_rolling_register_needs_at_least_two() -> None:
    with pytest.raises(RuleError, match="two or more"):
        block(kind="rolling", subintervals=1)


def test_nobody_rolls_over_a_dozen() -> None:
    with pytest.raises(RuleError, match="twelve subintervals"):
        block(kind="rolling", subintervals=13)


@pytest.mark.parametrize("bad", ["three", 3.0, True])
def test_a_subinterval_count_that_is_not_a_count(bad: object) -> None:
    with pytest.raises(BadInputError, match="whole number"):
        block(kind="rolling", subintervals=bad)


def test_a_negative_peak() -> None:
    with pytest.raises(BadInputError, match="negative peak"):
        block(maximum_kw="-1")


def test_holding_keeps_the_higher_peak() -> None:
    register = block().holding("412.5")
    assert register.maximum_kw == Decimal("412.5")
    assert register.holding("300").maximum_kw == Decimal("412.5")
    assert register.holding("500").maximum_kw == Decimal("500")


def test_holding_refuses_a_reading_that_is_not_one() -> None:
    with pytest.raises(BadInputError):
        block().holding("-1")


def test_resetting_zeroes_the_peak_and_dates_it() -> None:
    register = block().holding("412.5").reset("2025-06-30")
    assert register.maximum_kw == Decimal(0)
    assert register.reset_on == date(2025, 6, 30)
    assert register.was_reset


def test_a_register_cannot_be_reset_backwards() -> None:
    register = block().reset("2025-06-30")
    with pytest.raises(RuleError, match="reset backwards"):
        register.reset("2025-01-01")
    assert register.reset("2025-07-31").reset_on == date(2025, 7, 31)


def test_demand_registration_is_the_same_question_as_energy() -> None:
    assert demand_registration("102", "100") == Registration("102")
    assert demand_registration("412.5", "412.5") == Registration.nominal()
    with pytest.raises(BadInputError):
        demand_registration("100", "0")


def test_a_short_interval_reports_a_higher_peak() -> None:
    assert timing_error("870", Interval.MIN_15) < 0
    assert timing_error("930", 15) > 0
    assert timing_error("900", 15) == Decimal("0.0000")


def test_the_timing_band() -> None:
    assert timing_holds("900", 15)
    assert timing_holds("904", 15)
    assert not timing_holds("894", 15)
    assert Decimal("0.5") == TIMING_BAND


def test_a_measured_interval_that_is_not_one() -> None:
    with pytest.raises(BadInputError, match="above zero"):
        timing_error("0", 15)


def test_a_meter_can_be_right_on_energy_and_wrong_on_demand() -> None:
    energy = Registration("100.00")
    demand = demand_registration("104", "100")
    assert energy.within(Decimal("2"))
    assert not demand.within(Decimal("2"))
