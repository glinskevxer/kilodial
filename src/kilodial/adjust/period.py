"""How far back an adjustment reaches, and which rule stopped it there.

Three things can stop an adjustment reaching further back and only the latest of
them matters:

The tariff cap, counted back from the day the error was found.

The day the meter was set at that service point. Nothing before it was billed
through this meter, so nothing before it can be adjusted, however far the cap
reaches.

The day after the last test that found the installation inside tolerance. That
test is the utility's evidence that the meter was good then, and it is equally
the customer's evidence that it was good then. An adjustment that reaches past a
clean test is claiming the meter was already wrong on a day the shop certified
it was not.

Which of the three won is kept on the record. "Twelve months" and "twelve months
because that is as far as the tariff goes" are answers to different questions,
and the second is the one a customer asks.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass
from datetime import date, timedelta

from kilodial.errors import RuleError
from kilodial.units.span import DateSpan, add_months, parse_date


class Boundary(enum.Enum):
    """What stopped the period reaching further back."""

    TARIFF_CAP = "the tariff lookback"
    METER_SET = "the day the meter was set"
    CLEAN_TEST = "the last test inside tolerance"

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class Period:
    """The window an adjustment covers, and why it starts where it does."""

    span: DateSpan
    reason: Boundary
    capped_at: date
    set_at: date
    clean_at: date | None

    @property
    def days(self) -> int:
        return self.span.days

    @property
    def months(self) -> list[DateSpan]:
        return self.span.by_month()

    def explain(self) -> str:
        return f"{self.span} ({self.days} days), starting at {self.reason}"

    def __str__(self) -> str:
        return self.explain()


def period_for(
    *,
    found_on: object,
    set_on: object,
    cap_months: int,
    pulled_on: object = None,
    last_clean_on: object = None,
) -> Period:
    """Work out the window an adjustment covers.

    ``found_on`` is the day of the test that found the error. ``pulled_on``, if
    the meter has come out, ends the period there instead, because nothing after
    the pull was billed through it.
    """
    if cap_months <= 0:
        raise RuleError("a tariff lookback has to be a positive month count")
    found = parse_date(found_on)
    set_day = parse_date(set_on)
    end = found if pulled_on is None else min(found, parse_date(pulled_on))
    capped = add_months(found, -cap_months)
    clean = None if last_clean_on is None else parse_date(last_clean_on)
    candidates: list[tuple[date, Boundary]] = [
        (capped, Boundary.TARIFF_CAP),
        (set_day, Boundary.METER_SET),
    ]
    if clean is not None:
        candidates.append((clean + timedelta(days=1), Boundary.CLEAN_TEST))
    start, reason = max(candidates, key=lambda pair: (pair[0], _rank(pair[1])))
    if start > end:
        raise RuleError(
            f"there is no adjustment period: it would start {start.isoformat()} "
            f"and end {end.isoformat()}"
        )
    return Period(
        span=DateSpan(start, end),
        reason=reason,
        capped_at=capped,
        set_at=set_day,
        clean_at=clean,
    )


def _rank(boundary: Boundary) -> int:
    """Break a tie between two boundaries on the same day.

    A clean test is the most informative answer and the tariff cap is the least,
    so when two land on the same day the record names the one that tells the
    customer the most.
    """
    return {
        Boundary.CLEAN_TEST: 3,
        Boundary.METER_SET: 2,
        Boundary.TARIFF_CAP: 1,
    }[boundary]


__all__ = ["Boundary", "Period", "period_for"]
