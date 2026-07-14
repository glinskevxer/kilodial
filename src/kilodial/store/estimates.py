"""Storing the estimate somebody settled on, and who settled it.

The estimate module works several figures out and refuses to choose between
them. This is where the choice gets written down, and the two fields that make
it worth writing down are the basis and the person. An estimate on a bill is a
judgement, and a judgement with nobody's name on it is the kind of thing that
turns a billing dispute into a complaint about the utility.

An estimate is written once. Changing one means a new record with a note saying
what it replaces, because the customer was told the old figure and that
conversation happened.
"""

from __future__ import annotations

import sqlite3
from datetime import date

from kilodial.errors import DuplicateError, RuleError
from kilodial.estimate.basis import Basis, Estimate
from kilodial.store.base import has_row, member_of, one_row, upper
from kilodial.units.money import Money
from kilodial.units.span import DateSpan, parse_date
from kilodial.units.text import key, optional, tidy

COLUMNS = (
    "reference, point_code, first_day, last_day, basis, amount, working, "
    "settled_on, settled_by, note"
)


class SettledEstimate:
    """An estimate as the book holds it, with who settled it and when."""

    def __init__(
        self,
        reference: str,
        estimate: Estimate,
        settled_on: date,
        settled_by: str,
    ) -> None:
        self.reference = reference
        self.estimate = estimate
        self.settled_on = settled_on
        self.settled_by = settled_by

    @property
    def amount(self) -> Money:
        return self.estimate.amount

    @property
    def basis(self) -> Basis:
        return self.estimate.basis

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, SettledEstimate):
            return NotImplemented
        return (
            self.reference == other.reference
            and self.estimate == other.estimate
            and self.settled_on == other.settled_on
            and self.settled_by == other.settled_by
        )

    def __hash__(self) -> int:
        return hash((self.reference, self.settled_on, self.settled_by))

    def __str__(self) -> str:
        return (
            f"{self.reference} {self.estimate.point_code} {self.amount} on "
            f"{self.basis}, settled by {self.settled_by}"
        )


class EstimateRepository:
    """Settled estimates on one book."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._conn = connection

    def settle(
        self,
        reference: object,
        estimate: Estimate,
        *,
        on: object,
        by: object,
    ) -> SettledEstimate:
        """Write an estimate down as the one that was used."""
        wanted = key(reference, "estimate reference", 24)
        found = self._conn.execute(
            "SELECT 1 FROM service_point WHERE code = ?", (estimate.point_code,)
        ).fetchone()
        if found is None:
            raise RuleError(f"service point {estimate.point_code} is not on the book")
        if self.exists(wanted):
            raise DuplicateError("estimate", wanted)
        if estimate.span.end is None:
            raise RuleError("an estimate has to cover a period with an end on it")
        settled = SettledEstimate(wanted, estimate, parse_date(on), tidy(by, "settler", 40))
        self._conn.execute(
            f"INSERT INTO estimate ({COLUMNS}) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                settled.reference,
                estimate.point_code,
                estimate.span.start.isoformat(),
                estimate.span.end.isoformat(),
                estimate.basis.name,
                estimate.amount.cents,
                estimate.working,
                settled.settled_on.isoformat(),
                settled.settled_by,
                estimate.note,
            ),
        )
        return settled

    def exists(self, reference: str) -> bool:
        return has_row(self._conn, "estimate", "reference", upper(reference))

    def get(self, reference: str) -> SettledEstimate:
        return _read(
            one_row(self._conn, COLUMNS, "estimate", "reference", upper(reference), "estimate")
        )

    def for_point(self, point_code: str) -> list[SettledEstimate]:
        rows = self._conn.execute(
            f"SELECT {COLUMNS} FROM estimate WHERE point_code = ? ORDER BY first_day",
            (upper(point_code),),
        ).fetchall()
        return [_read(r) for r in rows]

    def all(self) -> list[SettledEstimate]:
        rows = self._conn.execute(
            f"SELECT {COLUMNS} FROM estimate ORDER BY settled_on, reference"
        ).fetchall()
        return [_read(r) for r in rows]

    def covering(self, point_code: str, span: DateSpan) -> list[SettledEstimate]:
        """Settled estimates at a point that overlap a window."""
        return [s for s in self.for_point(point_code) if s.estimate.span.overlaps(span)]

    def total_for(self, point_code: str) -> Money:
        return Money.total(s.amount for s in self.for_point(point_code))

    def count(self) -> int:
        return int(self._conn.execute("SELECT COUNT(*) FROM estimate").fetchone()[0])


def _read(row: tuple[object, ...]) -> SettledEstimate:
    estimate = Estimate(
        point_code=str(row[1]),
        span=DateSpan(str(row[2]), str(row[3])),
        basis=member_of(Basis, row[4], "estimate basis", field="name"),
        amount=Money.from_cents(int(str(row[5]))),
        working=str(row[6]),
        note=optional(row[9], "estimate note", 240),
    )
    return SettledEstimate(str(row[0]), estimate, parse_date(str(row[7])), str(row[8]))


__all__ = ["COLUMNS", "EstimateRepository", "SettledEstimate"]
