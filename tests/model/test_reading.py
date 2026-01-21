from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from kilodial.errors import BadInputError, RuleError
from kilodial.model.reading import (
    Reading,
    ReadingKind,
    across_change,
    consumption,
    reading_kind,
    wrap_at,
)


def reading(value: int, on: str, **over: object) -> Reading:
    args: dict[str, object] = {"dials": 5, "value": value, "read_on": on}
    args.update(over)
    return Reading.build(
        str(args.pop("point_code", "SP-1042")),
        str(args.pop("meter_serial", "84-119302")),
        **args,
    )


def test_kind_lookup() -> None:
    assert reading_kind("actual") is ReadingKind.ACTUAL
    assert reading_kind(ReadingKind.FINAL) is ReadingKind.FINAL
    with pytest.raises(BadInputError, match="kind of register reading"):
        reading_kind("guessed")


def test_which_kinds_can_end_a_billing_period() -> None:
    assert ReadingKind.ACTUAL.bills
    assert ReadingKind.ESTIMATED.bills
    assert not ReadingKind.CUSTOMER.bills
    assert ReadingKind.ACTUAL.is_read
    assert not ReadingKind.ESTIMATED.is_read
    assert str(ReadingKind.FINAL) == "final"


def test_a_register_wraps_at_its_dial_count() -> None:
    assert wrap_at(4) == 10_000
    assert wrap_at(5) == 100_000
    with pytest.raises(BadInputError, match="between 4 and 8 dials"):
        wrap_at(3)
    with pytest.raises(BadInputError, match="whole number"):
        wrap_at("five")


def test_a_reading_prints_with_its_leading_zeroes() -> None:
    r = reading(140, "2025-02-01")
    assert str(r) == "SP-1042 84-119302 2025-02-01 00140 (actual)"
    assert r.read_on == date(2025, 2, 1)


def test_a_reading_the_register_could_not_show() -> None:
    with pytest.raises(RuleError, match="rolls at 100000"):
        reading(100_000, "2025-02-01")


@pytest.mark.parametrize("bad", [-1, "140", 140.0, True])
def test_a_reading_that_is_not_a_reading(bad: object) -> None:
    with pytest.raises(BadInputError):
        reading(bad, "2025-02-01")  # type: ignore[arg-type]


def test_an_ordinary_period() -> None:
    found = consumption(reading(41_200, "2025-01-01"), reading(41_480, "2025-02-01"))
    assert found.units == 280
    assert not found.rolled
    assert found.days == 31
    assert found.billed_units == Decimal("280.000")
    assert found.plausible
    assert "280.000 units over 31 days" in found.show()


def test_a_rollover() -> None:
    found = consumption(reading(99_860, "2025-01-01"), reading(140, "2025-02-01"))
    assert found.rolled
    assert found.units == 280
    assert found.plausible


def test_a_multiplier_is_applied_to_the_dials() -> None:
    found = consumption(
        reading(41_200, "2025-01-01"), reading(41_480, "2025-02-01"), multiplier="40"
    )
    assert found.units == 280
    assert found.billed_units == Decimal("11200.000")
    assert found.daily == Decimal("361.290")


def test_an_implausible_rollover_is_flagged_rather_than_billed() -> None:
    found = consumption(reading(90_000, "2025-01-01"), reading(100, "2025-01-02"))
    assert found.rolled
    assert not found.plausible
    assert found.reason is not None
    assert "may not have rolled" in found.reason


def test_the_plausibility_limit_can_be_moved() -> None:
    args = (reading(90_000, "2025-01-01"), reading(100, "2025-01-02"))
    assert not consumption(*args).plausible
    assert consumption(*args, daily_limit="20000").plausible


def test_readings_off_different_meters() -> None:
    with pytest.raises(RuleError, match="different meters"):
        consumption(
            reading(100, "2025-01-01"),
            reading(200, "2025-02-01", meter_serial="84-119303"),
        )


def test_readings_from_different_points() -> None:
    with pytest.raises(RuleError, match="different service points"):
        consumption(
            reading(100, "2025-01-01"),
            reading(200, "2025-02-01", point_code="SP-1043"),
        )


def test_readings_off_different_sized_registers() -> None:
    with pytest.raises(RuleError, match="different sizes"):
        consumption(reading(100, "2025-01-01"), reading(200, "2025-02-01", dials=6))


def test_readings_in_the_wrong_order() -> None:
    with pytest.raises(RuleError, match="dated before"):
        consumption(reading(100, "2025-02-01"), reading(200, "2025-01-01"))


def test_a_daily_figure_over_no_days() -> None:
    found = consumption(reading(100, "2025-01-01"), reading(200, "2025-01-01"))
    assert found.days == 0
    assert found.daily == Decimal(0)


def test_across_a_meter_change() -> None:
    final = reading(41_900, "2025-02-01", kind=ReadingKind.FINAL)
    initial = reading(0, "2025-02-01", meter_serial="84-119303", kind=ReadingKind.INITIAL)
    current = reading(310, "2025-03-01", meter_serial="84-119303")
    found = across_change(final, initial, current)
    assert found.units == 310
    assert found.days == 28


def test_a_meter_change_needs_two_meters() -> None:
    same = reading(100, "2025-02-01")
    with pytest.raises(RuleError, match="two different meters"):
        across_change(same, same, same)


def test_the_initial_reading_has_to_be_off_the_new_meter() -> None:
    final = reading(41_900, "2025-02-01")
    initial = reading(0, "2025-02-01", meter_serial="84-119304")
    current = reading(310, "2025-03-01", meter_serial="84-119303")
    with pytest.raises(RuleError, match="is off 84-119304"):
        across_change(final, initial, current)


def test_an_initial_reading_dated_after_the_current_one() -> None:
    final = reading(41_900, "2025-02-01")
    initial = reading(0, "2025-04-01", meter_serial="84-119303")
    current = reading(310, "2025-03-01", meter_serial="84-119303")
    with pytest.raises(RuleError, match="dated after the current one"):
        across_change(final, initial, current)


def test_a_multiplier_of_nothing() -> None:
    with pytest.raises(BadInputError, match="above zero"):
        consumption(reading(100, "2025-01-01"), reading(200, "2025-02-01"), multiplier="0")
