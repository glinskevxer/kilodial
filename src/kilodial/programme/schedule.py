"""When a meter is next due, and what to call it when it is late.

A meter's clock starts at the last run that says something about it in service,
and only two kinds of run do: an acceptance run, which is the shop certifying
the meter before it goes out, and an as found run, which is the shop measuring
what the customer had. An as left run says the meter is fit to go back out and
says nothing about how long it will stay fit, so it does not restart the clock.
A referee run does restart it, because it is a real measurement of a meter in
service, and refusing to count it would mean testing a meter twice in a month.

A meter that has never been tested at all is due from the day the shop took
delivery of it. That is harsher than dating from the day it was set, and it is
deliberate: a meter that sat in stock for six years has aged in stock.

The grace period exists because a programme that calls a meter overdue on the
day after it falls due generates a list nobody can work. Inside grace the meter
is due; past grace it is overdue and it goes on the report the commission sees.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass
from datetime import date

from kilodial.errors import RuleError
from kilodial.model.run import RunKind
from kilodial.units.span import add_months, parse_date

# Runs that restart a meter's periodic clock.
RESTARTS_CLOCK = frozenset({RunKind.ACCEPTANCE, RunKind.AS_FOUND, RunKind.REFEREE})

GRACE_DAYS = 90


class DueState(enum.Enum):
    """Where a meter sits against its own due date."""

    CURRENT = "current"
    DUE = "due"
    OVERDUE = "overdue"

    @property
    def needs_work(self) -> bool:
        return self is not DueState.CURRENT

    def __str__(self) -> str:
        return self.value


def due_on(baseline: object, interval_months: int) -> date:
    """The day a meter falls due, given when its clock last started."""
    if interval_months <= 0:
        raise RuleError("a test interval has to be a positive number of months")
    return add_months(parse_date(baseline), interval_months)


def state_on(due: object, day: object, *, grace_days: int = GRACE_DAYS) -> DueState:
    """Whether a meter is current, due or overdue on a given day."""
    if grace_days < 0:
        raise RuleError("a grace period cannot be negative")
    when = parse_date(day)
    falls = parse_date(due)
    if when < falls:
        return DueState.CURRENT
    return DueState.DUE if (when - falls).days <= grace_days else DueState.OVERDUE


def days_over(due: object, day: object) -> int:
    """How far past due a meter is, negative when it is not there yet."""
    return (parse_date(day) - parse_date(due)).days


@dataclass(frozen=True)
class DueMeter:
    """One line of the due list."""

    serial: str
    group_code: str
    interval_months: int
    baseline: date
    last_kind: RunKind | None
    due: date
    state: DueState
    days_over: int

    @property
    def never_tested(self) -> bool:
        return self.last_kind is None

    def __str__(self) -> str:
        return f"{self.serial} {self.state} {self.due.isoformat()}"


def schedule_for(
    serial: str,
    *,
    group_code: str,
    interval_months: int,
    acquired: object,
    last_run: tuple[object, RunKind] | None,
    on: object,
    grace_days: int = GRACE_DAYS,
) -> DueMeter:
    """Work out one meter's position in the programme.

    ``last_run`` is the most recent run that restarts the clock, as a date and
    kind pair. Passing a run of a kind that does not restart the clock is an
    error rather than something to be quietly ignored, because a caller that
    hands over an as left run has misunderstood the question.
    """
    if last_run is None:
        baseline = parse_date(acquired)
        kind = None
    else:
        when, kind = last_run
        if kind not in RESTARTS_CLOCK:
            raise RuleError(f"an {kind} run does not restart the periodic clock")
        baseline = parse_date(when)
    falls = due_on(baseline, interval_months)
    return DueMeter(
        serial=serial.strip().upper(),
        group_code=group_code.strip().upper(),
        interval_months=interval_months,
        baseline=baseline,
        last_kind=kind,
        due=falls,
        state=state_on(falls, on, grace_days=grace_days),
        days_over=days_over(falls, on),
    )


__all__ = [
    "GRACE_DAYS",
    "RESTARTS_CLOCK",
    "DueMeter",
    "DueState",
    "days_over",
    "due_on",
    "schedule_for",
    "state_on",
]
