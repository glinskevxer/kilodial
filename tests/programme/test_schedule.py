from __future__ import annotations

from datetime import date

import pytest

from kilodial.errors import RuleError
from kilodial.model.run import RunKind
from kilodial.programme.schedule import (
    RESTARTS_CLOCK,
    DueState,
    days_over,
    due_on,
    schedule_for,
    state_on,
)


def test_which_runs_restart_the_clock() -> None:
    assert RunKind.ACCEPTANCE in RESTARTS_CLOCK
    assert RunKind.AS_FOUND in RESTARTS_CLOCK
    assert RunKind.REFEREE in RESTARTS_CLOCK
    assert RunKind.AS_LEFT not in RESTARTS_CLOCK


def test_due_on_counts_whole_months() -> None:
    assert due_on("2019-05-31", 48) == date(2023, 5, 31)
    assert due_on("2020-02-29", 12) == date(2021, 2, 28)


def test_a_daft_interval() -> None:
    with pytest.raises(RuleError, match="positive number of months"):
        due_on("2019-05-31", 0)


@pytest.mark.parametrize(
    ("day", "state"),
    [
        ("2023-05-30", DueState.CURRENT),
        ("2023-05-31", DueState.DUE),
        ("2023-08-29", DueState.DUE),
        ("2023-08-30", DueState.OVERDUE),
    ],
)
def test_current_due_and_overdue(day: str, state: DueState) -> None:
    assert state_on("2023-05-31", day) is state


def test_the_grace_period_can_be_changed() -> None:
    assert state_on("2023-05-31", "2023-06-05", grace_days=0) is DueState.OVERDUE
    assert state_on("2023-05-31", "2023-06-05", grace_days=30) is DueState.DUE
    with pytest.raises(RuleError, match="cannot be negative"):
        state_on("2023-05-31", "2023-06-05", grace_days=-1)


def test_which_states_need_work() -> None:
    assert not DueState.CURRENT.needs_work
    assert DueState.DUE.needs_work
    assert DueState.OVERDUE.needs_work
    assert str(DueState.OVERDUE) == "overdue"


def test_days_over_goes_negative_before_the_date() -> None:
    assert days_over("2023-05-31", "2023-06-10") == 10
    assert days_over("2023-05-31", "2023-05-01") == -30


def test_a_meter_that_has_been_tested() -> None:
    line = schedule_for(
        "84-119302",
        group_code="g1",
        interval_months=48,
        acquired="2015-01-01",
        last_run=("2021-06-30", RunKind.AS_FOUND),
        on="2025-01-01",
    )
    assert line.serial == "84-119302"
    assert line.group_code == "G1"
    assert line.baseline == date(2021, 6, 30)
    assert line.due == date(2025, 6, 30)
    assert line.state is DueState.CURRENT
    assert not line.never_tested
    assert str(line) == "84-119302 current 2025-06-30"


def test_a_meter_that_has_never_been_tested_dates_from_delivery() -> None:
    line = schedule_for(
        "84-119302",
        group_code="G1",
        interval_months=48,
        acquired="2015-01-01",
        last_run=None,
        on="2025-01-01",
    )
    assert line.never_tested
    assert line.baseline == date(2015, 1, 1)
    assert line.due == date(2019, 1, 1)
    assert line.state is DueState.OVERDUE
    assert line.days_over == 2192


def test_an_as_left_run_is_not_an_answer_to_this_question() -> None:
    with pytest.raises(RuleError, match="does not restart the periodic clock"):
        schedule_for(
            "84-119302",
            group_code="G1",
            interval_months=48,
            acquired="2015-01-01",
            last_run=("2021-06-30", RunKind.AS_LEFT),
            on="2025-01-01",
        )


def test_a_referee_run_does_restart_it() -> None:
    line = schedule_for(
        "84-119302",
        group_code="G1",
        interval_months=48,
        acquired="2015-01-01",
        last_run=("2022-03-01", RunKind.REFEREE),
        on="2025-01-01",
    )
    assert line.due == date(2026, 3, 1)


def test_a_longer_interval_moves_the_same_meter_out_of_the_list() -> None:
    args = {
        "group_code": "G1",
        "acquired": "2015-01-01",
        "last_run": ("2019-06-30", RunKind.AS_FOUND),
        "on": "2025-01-01",
    }
    short = schedule_for("84-119302", interval_months=48, **args)  # type: ignore[arg-type]
    long = schedule_for("84-119302", interval_months=120, **args)  # type: ignore[arg-type]
    assert short.state is DueState.OVERDUE
    assert long.state is DueState.CURRENT
