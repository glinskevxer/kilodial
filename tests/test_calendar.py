"""Sweep the date rules across whole years rather than across one Tuesday.

Everything in this package that takes a date is deterministic, and a suite that
runs on one day exercises one day. The rules that go wrong go wrong on the
awkward ones: the end of a short month, the twenty ninth of February, the turn
of a year, a leap day that is not a leap day because the century is not
divisible by four hundred.

So this walks whole years. It is not a property test and it does not generate
anything; it enumerates the days and asserts the invariants that have to hold on
every one of them. That is slower than picking three dates and much better at
finding the fourth.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

from kilodial.adjust.period import period_for
from kilodial.model.demand import Interval, timing_error
from kilodial.programme.schedule import DueState, due_on, state_on
from kilodial.units.span import DateSpan, add_months

LEAP = 2024
PLAIN = 2025
CENTURY = 1900
LEAP_CENTURY = 2000


def days_of(year: int) -> list[date]:
    """Every day in a year."""
    first = date(year, 1, 1)
    last = date(year, 12, 31)
    found = []
    while first <= last:
        found.append(first)
        first += timedelta(days=1)
    return found


@pytest.mark.parametrize("year", [LEAP, PLAIN])
def test_a_year_is_the_length_it_should_be(year: int) -> None:
    expected = 366 if year == LEAP else 365
    assert len(days_of(year)) == expected
    assert DateSpan(date(year, 1, 1), date(year, 12, 31)).days == expected


def test_the_century_rule() -> None:
    assert len(days_of(LEAP_CENTURY)) == 366
    assert len(days_of(CENTURY)) == 365
    assert add_months(date(LEAP_CENTURY, 1, 29), 1) == date(LEAP_CENTURY, 2, 29)
    assert add_months(date(CENTURY, 1, 29), 1) == date(CENTURY, 2, 28)


@pytest.mark.parametrize("year", [LEAP, PLAIN])
def test_adding_a_month_never_leaves_the_month_it_lands_in(year: int) -> None:
    for day in days_of(year):
        moved = add_months(day, 1)
        assert moved.month == (day.month % 12) + 1
        assert moved.day <= day.day


@pytest.mark.parametrize("year", [LEAP, PLAIN])
def test_adding_twelve_months_lands_on_the_same_day_or_the_last_of_february(
    year: int,
) -> None:
    for day in days_of(year):
        moved = add_months(day, 12)
        assert moved.year == day.year + 1
        assert moved.month == day.month
        if (day.month, day.day) == (2, 29):
            assert moved.day == 28
        else:
            assert moved.day == day.day


@pytest.mark.parametrize("year", [LEAP, PLAIN])
def test_a_month_split_covers_the_span_exactly(year: int) -> None:
    for day in days_of(year)[::7]:
        span = DateSpan(day, add_months(day, 3))
        pieces = span.by_month()
        assert sum(p.days for p in pieces) == span.days
        assert pieces[0].start == span.start
        assert pieces[-1].end == span.end


@pytest.mark.parametrize("year", [LEAP, PLAIN])
def test_a_due_date_is_always_after_the_run_that_set_it(year: int) -> None:
    for day in days_of(year):
        for months in (48, 72, 96, 120, 144, 192, 240, 300):
            assert due_on(day, months) > day


@pytest.mark.parametrize("year", [LEAP, PLAIN])
def test_a_meter_is_current_up_to_its_due_date_and_not_after(year: int) -> None:
    for day in days_of(year)[::5]:
        due = due_on(day, 48)
        assert state_on(due, due - timedelta(days=1)) is DueState.CURRENT
        assert state_on(due, due) is DueState.DUE
        assert state_on(due, due + timedelta(days=90)) is DueState.DUE
        assert state_on(due, due + timedelta(days=91)) is DueState.OVERDUE


@pytest.mark.parametrize("year", [LEAP, PLAIN])
def test_an_adjustment_period_always_ends_where_it_was_found(year: int) -> None:
    for day in days_of(year)[::3]:
        period = period_for(found_on=day, set_on=date(2010, 1, 1), cap_months=60)
        assert period.span.end == day
        assert period.span.start == add_months(day, -60)
        assert period.days == (day - add_months(day, -60)).days + 1


@pytest.mark.parametrize("year", [LEAP, PLAIN])
def test_a_span_of_one_day_is_one_day_all_year(year: int) -> None:
    for day in days_of(year):
        assert DateSpan(day, day).days == 1
        assert DateSpan(day, day).by_month() == [DateSpan(day, day)]


def test_the_demand_interval_arithmetic_has_no_dates_in_it() -> None:
    # Included here because it is the one rule that looks like it should be date
    # dependent and is not: a fifteen minute window is nine hundred seconds on
    # every day of every year, including the ones with a leap second in them,
    # because the meter counts its own seconds.
    assert timing_error("900", Interval.MIN_15) == Decimal("0.0000")
    assert Interval.MIN_60.seconds == Decimal(3600)


@pytest.mark.parametrize("year", [LEAP, PLAIN])
def test_shifting_a_span_back_a_year_keeps_its_shape(year: int) -> None:
    for day in days_of(year)[::11]:
        span = DateSpan(day, add_months(day, 1))
        moved = span.shifted_back(12)
        assert moved.start.year == day.year - 1
        assert moved.end is not None
        assert moved.end > moved.start
