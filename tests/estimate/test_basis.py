from __future__ import annotations

from decimal import Decimal

import pytest

from kilodial.adjust.compute import BilledMonth
from kilodial.errors import RuleError
from kilodial.estimate.basis import (
    Basis,
    daily_rate,
    declared,
    from_connected_load,
    from_last_year,
    from_metered,
    from_neighbours,
    strongest,
)
from kilodial.units.money import Money
from kilodial.units.span import DateSpan

LAST_DAY = {1: 31, 2: 28, 3: 31, 4: 30, 5: 31, 6: 30, 7: 31, 8: 31, 9: 30, 10: 31, 11: 30, 12: 31}


def months(year: int, first: int, last: int, amount: str = "100.00") -> list[BilledMonth]:
    return [
        BilledMonth.of(f"{year}-{i:02d}-01", f"{year}-{i:02d}-{LAST_DAY[i]}", amount)
        for i in range(first, last + 1)
    ]


GAP = DateSpan("2025-03-01", "2025-05-31")


def test_the_bases_are_ranked() -> None:
    assert Basis.LAST_YEAR.strength > Basis.NEIGHBOURS.strength
    assert Basis.NEIGHBOURS.strength > Basis.CONNECTED_LOAD.strength
    assert str(Basis.LAST_YEAR) == "same period last year"


def test_the_daily_rate_of_a_history() -> None:
    assert daily_rate(months(2025, 1, 1, "310.00")) == Money("10.00")
    with pytest.raises(RuleError, match="no billed history"):
        daily_rate([])


def test_last_year_takes_the_same_days_a_year_earlier() -> None:
    billed = months(2024, 1, 12, "100.00")
    found = from_last_year("sp-1042", billed, GAP)
    assert found.basis is Basis.LAST_YEAR
    assert found.point_code == "SP-1042"
    assert found.amount == Money("300.00")
    assert "billed over 2024-03-01 to 2024-05-31" in found.working


def test_last_year_with_nothing_billed_then() -> None:
    with pytest.raises(RuleError, match="last year is no basis"):
        from_last_year("SP-1042", months(2025, 1, 2), GAP)


def test_last_year_with_a_zero_history() -> None:
    with pytest.raises(RuleError, match="last year is no basis"):
        from_last_year("SP-1042", months(2024, 1, 12, "0.00"), GAP)


def test_the_neighbours_use_the_daily_rate_either_side() -> None:
    billed = months(2025, 1, 2, "310.00") + months(2025, 6, 7, "300.00")
    found = from_neighbours("SP-1042", billed, GAP)
    assert found.basis is Basis.NEIGHBOURS
    assert found.amount.cents > 0
    assert "a day across 4 billing periods" in found.working


def test_the_neighbours_with_nothing_outside_the_gap() -> None:
    with pytest.raises(RuleError, match="neighbours are no basis"):
        from_neighbours("SP-1042", months(2025, 3, 5), GAP)


def test_connected_load() -> None:
    found = from_connected_load(
        "SP-1042",
        DateSpan("2025-01-01", "2025-01-10"),
        kilowatts="10",
        duty="0.5",
        rate_per_kwh="0.12",
    )
    assert found.basis is Basis.CONNECTED_LOAD
    assert found.amount == Money("144.00")
    assert "10 kW at 0.5 duty for 10 days" in found.working


def test_a_duty_cycle_is_a_share_of_the_day() -> None:
    with pytest.raises(RuleError, match="cannot be over one"):
        from_connected_load("SP-1042", GAP, kilowatts="10", duty="2", rate_per_kwh="0.12")


@pytest.mark.parametrize(
    ("field", "value"),
    [("kilowatts", "0"), ("duty", "0"), ("rate_per_kwh", "-1")],
)
def test_connected_load_wants_real_numbers(field: str, value: str) -> None:
    args: dict[str, object] = {"kilowatts": "10", "duty": "0.5", "rate_per_kwh": "0.12"}
    args[field] = value
    with pytest.raises(Exception, match="above zero"):
        from_connected_load("SP-1042", GAP, **args)


def test_a_declared_figure() -> None:
    found = declared("SP-1042", GAP, "412.50", note="agreed at the hearing")
    assert found.basis is Basis.DECLARED
    assert found.amount == Money("412.50")
    assert found.note == "agreed at the hearing"
    assert "agreed rather than calculated" in found.explain()


def test_a_declared_figure_of_nothing() -> None:
    with pytest.raises(RuleError, match="more than nothing"):
        declared("SP-1042", GAP, "0")


def test_an_open_ended_gap_cannot_be_estimated() -> None:
    open_gap = DateSpan("2025-03-01")
    with pytest.raises(RuleError, match="a period with an end"):
        from_last_year("SP-1042", months(2024, 1, 12), open_gap)
    with pytest.raises(RuleError, match="a period with an end"):
        from_neighbours("SP-1042", months(2024, 1, 12), open_gap)
    with pytest.raises(RuleError, match="a period with an end"):
        from_connected_load("SP-1042", open_gap, kilowatts="10", duty="0.5", rate_per_kwh="0.12")


def test_the_daily_figure() -> None:
    found = declared("SP-1042", DateSpan("2025-01-01", "2025-01-10"), "100.00")
    assert found.daily == Money("10.00")


def test_the_strongest_basis_wins() -> None:
    weak = declared("SP-1042", GAP, "1000.00")
    strong = from_last_year("SP-1042", months(2024, 1, 12), GAP)
    assert strongest([weak, strong]) is strong
    with pytest.raises(RuleError, match="no estimates to choose"):
        strongest([])


def test_a_tie_is_broken_by_the_larger_figure() -> None:
    small = declared("SP-1042", GAP, "100.00")
    large = declared("SP-1042", GAP, "200.00")
    assert strongest([small, large]) is large
    assert large.amount.dollars == Decimal("200.00")


def test_a_metered_estimate_prices_what_the_register_counted() -> None:
    found = from_metered("SP-1042", "40", DateSpan("2025-01-01", "2025-01-10"), rate_per_kwh="0.12")
    assert found.basis is Basis.METERED
    assert found.amount == Money("48.00")
    assert "40 kWh a day metered either side" in found.working


def test_the_metered_basis_is_the_strongest() -> None:
    assert Basis.METERED.strength > Basis.LAST_YEAR.strength
    metered = from_metered("SP-1042", "40", GAP, rate_per_kwh="0.12")
    last_year = from_last_year("SP-1042", months(2024, 1, 12), GAP)
    assert strongest([last_year, metered]) is metered


@pytest.mark.parametrize(("field", "value"), [("daily_kwh", "0"), ("rate_per_kwh", "-1")])
def test_a_metered_estimate_wants_real_numbers(field: str, value: str) -> None:
    args: dict[str, object] = {"daily_kwh": "40", "rate_per_kwh": "0.12"}
    args[field] = value
    with pytest.raises(Exception, match="above zero"):
        from_metered("SP-1042", args.pop("daily_kwh"), GAP, **args)


def test_a_metered_estimate_of_an_open_gap() -> None:
    with pytest.raises(RuleError, match="a period with an end"):
        from_metered("SP-1042", "40", DateSpan("2025-01-01"), rate_per_kwh="0.12")
