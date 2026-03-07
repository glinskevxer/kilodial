"""Storing customer requested tests, open and closed.

The open list is the one that matters day to day, because every row on it is a
thirty day clock the utility is running against. It is deliberately a query
rather than a flag: a request is open when it has no closing date, and there is
no second place for that fact to be recorded wrongly.

``previous_request_on`` is not a column and comes back as None. It is derived
from the other requests on the point when it is needed, so that entering an old
request late corrects every later free window rather than none of them.

A closed request keeps the run that answered it, the charge decision and the fee.
It is a record of what the customer was told, so it is written once and not
edited. Reopening is not supported and that is on purpose; a request answered
wrongly gets a new request with a note pointing at the old one.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date

from kilodial.complaint.request import Charge, Reason, Request
from kilodial.errors import DuplicateError, RuleError, StateError
from kilodial.store.base import has_row, member_of, one_row, upper
from kilodial.units.money import Money
from kilodial.units.span import parse_date

COLUMNS = (
    "reference, point_code, requested_on, requested_by, reason, note, run_reference, "
    "charge, fee, closed_on"
)


@dataclass(frozen=True)
class Complaint:
    """A request as the book holds it, open or closed."""

    request: Request
    run_reference: str | None
    charge: Charge | None
    fee: Money | None
    closed_on: date | None

    @property
    def is_open(self) -> bool:
        return self.closed_on is None

    @property
    def reference(self) -> str:
        return self.request.reference

    def __str__(self) -> str:
        where = "open" if self.is_open else f"closed {self.closed_on}"
        return f"{self.request} {where}"


class ComplaintRepository:
    """Customer requested tests on one book."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._conn = connection

    def open_request(self, request: Request) -> Complaint:
        """Log a new request against a service point."""
        found = self._conn.execute(
            "SELECT 1 FROM service_point WHERE code = ?", (request.point_code,)
        ).fetchone()
        if found is None:
            raise RuleError(f"service point {request.point_code} is not on the book")
        if self.exists(request.reference):
            raise DuplicateError("complaint request", request.reference)
        self._conn.execute(
            f"INSERT INTO complaint_request ({COLUMNS}) "
            f"VALUES (?, ?, ?, ?, ?, ?, NULL, NULL, NULL, NULL)",
            (
                request.reference,
                request.point_code,
                request.requested_on.isoformat(),
                request.requested_by,
                request.reason.value,
                request.note,
            ),
        )
        return Complaint(request, None, None, None, None)

    def close(
        self,
        reference: str,
        *,
        run_reference: str,
        charge: Charge,
        fee: Money,
        on: object,
    ) -> Complaint:
        """Record the answer to a request, once."""
        complaint = self.get(reference)
        if not complaint.is_open:
            raise StateError(f"complaint {complaint.reference} was closed on {complaint.closed_on}")
        self._conn.execute(
            "UPDATE complaint_request SET run_reference = ?, charge = ?, fee = ?, "
            "closed_on = ? WHERE reference = ?",
            (
                run_reference.strip().upper(),
                charge.name,
                fee.cents,
                parse_date(on).isoformat(),
                complaint.reference,
            ),
        )
        return self.get(complaint.reference)

    def exists(self, reference: str) -> bool:
        return has_row(self._conn, "complaint_request", "reference", upper(reference))

    def get(self, reference: str) -> Complaint:
        return self._read(
            one_row(
                self._conn,
                COLUMNS,
                "complaint_request",
                "reference",
                upper(reference),
                "complaint request",
            )
        )

    def all(self) -> list[Complaint]:
        rows = self._conn.execute(
            f"SELECT {COLUMNS} FROM complaint_request ORDER BY requested_on, reference"
        ).fetchall()
        return [self._read(r) for r in rows]

    def open_ones(self) -> list[Complaint]:
        rows = self._conn.execute(
            f"SELECT {COLUMNS} FROM complaint_request WHERE closed_on IS NULL "
            "ORDER BY requested_on, reference"
        ).fetchall()
        return [self._read(r) for r in rows]

    def for_point(self, point_code: str) -> list[Complaint]:
        rows = self._conn.execute(
            f"SELECT {COLUMNS} FROM complaint_request WHERE point_code = ? "
            "ORDER BY requested_on, reference",
            (point_code.strip().upper(),),
        ).fetchall()
        return [self._read(r) for r in rows]

    def previous_for(self, point_code: str, before: object) -> date | None:
        """When the customer last asked, which decides the free window."""
        cutoff = parse_date(before).isoformat()
        row = self._conn.execute(
            "SELECT MAX(requested_on) FROM complaint_request WHERE point_code = ? "
            "AND requested_on < ?",
            (point_code.strip().upper(), cutoff),
        ).fetchone()
        return None if row is None or row[0] is None else parse_date(str(row[0]))

    def overdue(self, day: object) -> list[Complaint]:
        """Open requests whose thirty days have run out."""
        when = parse_date(day)
        return [c for c in self.open_ones() if c.request.due_by < when]

    def count(self) -> int:
        return int(self._conn.execute("SELECT COUNT(*) FROM complaint_request").fetchone()[0])

    @staticmethod
    def _read(row: tuple[object, ...]) -> Complaint:
        request = Request(
            reference=str(row[0]),
            point_code=str(row[1]),
            requested_on=parse_date(str(row[2])),
            requested_by=str(row[3]),
            reason=member_of(Reason, row[4], "complaint reason"),
            note=None if row[5] is None else str(row[5]),
            previous_request_on=None,
        )
        return Complaint(
            request=request,
            run_reference=None if row[6] is None else str(row[6]),
            charge=None
            if row[7] is None
            else member_of(Charge, row[7], "charge decision", field="name"),
            fee=None if row[8] is None else Money.from_cents(int(str(row[8]))),
            closed_on=None if row[9] is None else parse_date(str(row[9])),
        )


__all__ = ["COLUMNS", "Complaint", "ComplaintRepository"]
