"""The billed history: what the customer was actually charged, month by month.

This is the one table on the book that the shop does not own. It is loaded from
the billing system, and the only reason it is here at all is that an adjustment
cannot be computed without it and reaching across to the billing system in the
middle of a calculation is not something anybody wants to defend later.

Amounts are stored as whole cents in an INTEGER column rather than as text like
every other number in this package. Money is already an integer number of cents
and there is no decimal to lose, so text would only make the column harder to
sum in a spreadsheet, which is exactly what the billing clerk does with it.

Overlapping months are refused. A period that overlaps another means the same
day is billed twice, and an adjustment over that period would move the money
twice with nothing in the output showing why.
"""

from __future__ import annotations

import sqlite3

from kilodial.adjust.compute import BilledMonth
from kilodial.errors import DuplicateError, NotFoundError, RuleError
from kilodial.units.money import Money
from kilodial.units.span import DateSpan, parse_date

COLUMNS = "point_code, first_day, last_day, amount, kwh"


class BillingRepository:
    """Billed months on one book."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._conn = connection

    def add(self, point_code: str, month: BilledMonth, *, kwh: object = None) -> BilledMonth:
        """Record one billing period, refusing anything that double bills a day."""
        code = point_code.strip().upper()
        found = self._conn.execute("SELECT 1 FROM service_point WHERE code = ?", (code,)).fetchone()
        if found is None:
            raise RuleError(f"service point {code} is not on the book")
        if month.span.end is None:
            raise RuleError("a billing period has to have an end")
        for existing in self.for_point(code):
            if existing.span.overlaps(month.span):
                raise DuplicateError("billed month", f"{code}/{month.span.start.isoformat()}")
        self._conn.execute(
            f"INSERT INTO billed_month ({COLUMNS}) VALUES (?, ?, ?, ?, ?)",
            (
                code,
                month.span.start.isoformat(),
                month.span.end.isoformat(),
                month.amount.cents,
                None if kwh is None else str(kwh),
            ),
        )
        return month

    def for_point(self, point_code: str) -> list[BilledMonth]:
        rows = self._conn.execute(
            f"SELECT {COLUMNS} FROM billed_month WHERE point_code = ? ORDER BY first_day",
            (point_code.strip().upper(),),
        ).fetchall()
        return [self._read(r) for r in rows]

    def covering(self, point_code: str, span: DateSpan) -> list[BilledMonth]:
        """Every billing period that touches a window."""
        return [m for m in self.for_point(point_code) if m.span.overlaps(span)]

    def get(self, point_code: str, first_day: object) -> BilledMonth:
        code = point_code.strip().upper()
        start = parse_date(first_day).isoformat()
        row = self._conn.execute(
            f"SELECT {COLUMNS} FROM billed_month WHERE point_code = ? AND first_day = ?",
            (code, start),
        ).fetchone()
        if row is None:
            raise NotFoundError("billed month", f"{code}/{start}")
        return self._read(row)

    def delete(self, point_code: str, first_day: object) -> None:
        code = point_code.strip().upper()
        start = parse_date(first_day).isoformat()
        self.get(code, start)
        self._conn.execute(
            "DELETE FROM billed_month WHERE point_code = ? AND first_day = ?", (code, start)
        )

    def total_for(self, point_code: str, span: DateSpan) -> Money:
        """What the customer paid over a window, prorated at the edges."""
        total = Money.zero()
        for month in self.covering(point_code, span):
            total = total + month.share_over(span)
        return total

    def kwh_for(self, point_code: str, first_day: object) -> str | None:
        code = point_code.strip().upper()
        row = self._conn.execute(
            "SELECT kwh FROM billed_month WHERE point_code = ? AND first_day = ?",
            (code, parse_date(first_day).isoformat()),
        ).fetchone()
        if row is None:
            raise NotFoundError("billed month", f"{code}/{first_day}")
        return None if row[0] is None else str(row[0])

    def count(self) -> int:
        return int(self._conn.execute("SELECT COUNT(*) FROM billed_month").fetchone()[0])

    @staticmethod
    def _read(row: tuple[object, ...]) -> BilledMonth:
        return BilledMonth(
            span=DateSpan(str(row[1]), str(row[2])),
            amount=Money.from_cents(int(str(row[3]))),
        )


__all__ = ["COLUMNS", "BillingRepository"]
