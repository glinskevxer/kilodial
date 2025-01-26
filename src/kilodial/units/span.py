"""Date spans, because almost every rule in the shop is bounded by one.

A reference standard is certified between two dates. A meter is in service
between two dates. A bill adjustment covers a period, and that period gets cut
at the billing month boundaries before the money is prorated across the pieces.
All of that is the same arithmetic, so it lives in one place.

Spans are closed on both ends: a span of 2025-01-01 to 2025-01-31 contains both
of those days. Half open spans read better in code and worse in a shop record,
and the shop record is what gets argued about at a hearing.
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date, timedelta

from kilodial.errors import BadInputError


def parse_date(value: object) -> date:
    """Read an ISO date from a date or a string, and refuse anything else."""
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value.strip())
        except ValueError:
            raise BadInputError(f"{value!r} is not an ISO date") from None
    raise BadInputError(f"cannot read a date from {type(value).__name__}")


def add_months(start: date, months: int) -> date:
    """Move a date by whole months, clamping at the end of a short month.

    The 31st of January plus one month is the 28th of February, or the 29th in a
    leap year. Test intervals are quoted in months and meters get set on the
    31st, so this comes up more often than it sounds like it should.
    """
    total = start.month - 1 + months
    year = start.year + total // 12
    month = total % 12 + 1
    day = min(start.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


@dataclass(frozen=True)
class DateSpan:
    """A closed range of days, with an optional open end."""

    start: date
    end: date | None

    def __init__(self, start: object, end: object = None) -> None:
        first = parse_date(start)
        last = None if end is None else parse_date(end)
        if last is not None and last < first:
            raise BadInputError(f"a span cannot end ({last}) before it starts ({first})")
        object.__setattr__(self, "start", first)
        object.__setattr__(self, "end", last)

    @property
    def is_open(self) -> bool:
        return self.end is None

    @property
    def days(self) -> int:
        """Inclusive day count. An open span has no count."""
        if self.end is None:
            raise BadInputError("an open ended span has no day count")
        return (self.end - self.start).days + 1

    def contains(self, day: object) -> bool:
        when = parse_date(day)
        if when < self.start:
            return False
        return self.end is None or when <= self.end

    def overlaps(self, other: DateSpan) -> bool:
        if self.end is not None and other.start > self.end:
            return False
        return not (other.end is not None and self.start > other.end)

    def intersect(self, other: DateSpan) -> DateSpan | None:
        """The overlap, or None when they do not touch."""
        if not self.overlaps(other):
            return None
        start = max(self.start, other.start)
        if self.end is None:
            end = other.end
        elif other.end is None:
            end = self.end
        else:
            end = min(self.end, other.end)
        return DateSpan(start, end)

    def clipped_to(self, other: DateSpan) -> DateSpan:
        """The overlap, refusing rather than returning nothing."""
        cut = self.intersect(other)
        if cut is None:
            raise BadInputError(f"{self} does not overlap {other}")
        return cut

    def by_month(self) -> list[DateSpan]:
        """Cut the span at calendar month boundaries.

        Used by the adjustment layer, which owes the customer money per billing
        month and cannot hand back a single lump for a period that straddles
        three of them.
        """
        if self.end is None:
            raise BadInputError("an open ended span cannot be cut into months")
        pieces: list[DateSpan] = []
        cursor = self.start
        while cursor <= self.end:
            last_of_month = date(
                cursor.year, cursor.month, calendar.monthrange(cursor.year, cursor.month)[1]
            )
            stop = min(last_of_month, self.end)
            pieces.append(DateSpan(cursor, stop))
            cursor = stop + timedelta(days=1)
        return pieces

    def shifted_back(self, months: int) -> DateSpan:
        """The same span moved earlier by whole months."""
        if months < 0:
            raise BadInputError("shift a span back by a whole number of months")
        end = None if self.end is None else add_months(self.end, -months)
        return DateSpan(add_months(self.start, -months), end)

    def closed_at(self, day: object) -> DateSpan:
        """Give an open span an end, or refuse to move a closed one."""
        if self.end is not None:
            raise BadInputError("that span is already closed")
        return DateSpan(self.start, parse_date(day))

    def __str__(self) -> str:
        return f"{self.start.isoformat()} to {'open' if self.end is None else self.end.isoformat()}"


__all__ = ["DateSpan", "add_months", "parse_date"]
