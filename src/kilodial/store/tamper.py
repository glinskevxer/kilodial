"""Storing tamper findings.

The query the rest of the package asks is narrow: what has been confirmed at
this point at or before this day. That is what changes an adjustment, and it is
deliberately the only thing that does. A suspicion sits on the book and shows up
on a report and moves no money at all.
"""

from __future__ import annotations

import sqlite3

from kilodial.errors import DuplicateError, NotFoundError, RuleError
from kilodial.store.base import has_row, member_of, one_row, or_none, upper
from kilodial.tamper.event import Finding, Standing, TamperKind, confirmed_before
from kilodial.units.span import parse_date

COLUMNS = "reference, point_code, kind, standing, found_on, found_by, settled_on, since, evidence"


class TamperRepository:
    """Tamper findings on one book."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._conn = connection

    def add(self, finding: Finding) -> Finding:
        """Log a finding against a service point."""
        found = self._conn.execute(
            "SELECT 1 FROM service_point WHERE code = ?", (finding.point_code,)
        ).fetchone()
        if found is None:
            raise RuleError(f"service point {finding.point_code} is not on the book")
        if self.exists(finding.reference):
            raise DuplicateError("tamper finding", finding.reference)
        self._conn.execute(
            f"INSERT INTO tamper_finding ({COLUMNS}) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            _row(finding),
        )
        return finding

    def save(self, finding: Finding) -> Finding:
        """Write a finding already on the book back over itself."""
        if not self.exists(finding.reference):
            raise NotFoundError("tamper finding", finding.reference)
        row = _row(finding)
        self._conn.execute(
            "UPDATE tamper_finding SET point_code = ?, kind = ?, standing = ?, "
            "found_on = ?, found_by = ?, settled_on = ?, since = ?, evidence = ? "
            "WHERE reference = ?",
            (*row[1:], row[0]),
        )
        return finding

    def exists(self, reference: str) -> bool:
        return has_row(self._conn, "tamper_finding", "reference", upper(reference))

    def get(self, reference: str) -> Finding:
        return _read(
            one_row(
                self._conn,
                COLUMNS,
                "tamper_finding",
                "reference",
                upper(reference),
                "tamper finding",
            )
        )

    def find(self, reference: str | None) -> Finding | None:
        """Look one up, handing back nothing rather than raising."""
        return or_none(self.get, reference)

    def all(self) -> list[Finding]:
        rows = self._conn.execute(
            f"SELECT {COLUMNS} FROM tamper_finding ORDER BY found_on, reference"
        ).fetchall()
        return [_read(r) for r in rows]

    def for_point(self, point_code: str) -> list[Finding]:
        rows = self._conn.execute(
            f"SELECT {COLUMNS} FROM tamper_finding WHERE point_code = ? "
            "ORDER BY found_on, reference",
            (upper(point_code),),
        ).fetchall()
        return [_read(r) for r in rows]

    def open_ones(self) -> list[Finding]:
        rows = self._conn.execute(
            f"SELECT {COLUMNS} FROM tamper_finding WHERE standing = ? ORDER BY found_on, reference",
            (Standing.SUSPECTED.value,),
        ).fetchall()
        return [_read(r) for r in rows]

    def confirmed_at(self, point_code: str, day: object) -> list[Finding]:
        """Confirmed findings at a point at or before a day, earliest first."""
        return confirmed_before(self.for_point(point_code), day)

    def unmetered_at(self, point_code: str, day: object) -> bool:
        """Whether anything confirmed at that point stopped the meter measuring."""
        return any(f.unmeters for f in self.confirmed_at(point_code, day))

    def since_at(self, point_code: str, day: object) -> object:
        """The earliest day interference at that point is judged to have begun."""
        confirmed = self.confirmed_at(point_code, day)
        starts = [f.since for f in confirmed if f.since is not None]
        return min(starts) if starts else None

    def between(self, first: object, last: object) -> list[Finding]:
        start = parse_date(first).isoformat()
        end = parse_date(last).isoformat()
        rows = self._conn.execute(
            f"SELECT {COLUMNS} FROM tamper_finding WHERE found_on BETWEEN ? AND ? "
            "ORDER BY found_on, reference",
            (start, end),
        ).fetchall()
        return [_read(r) for r in rows]

    def count(self) -> int:
        return int(self._conn.execute("SELECT COUNT(*) FROM tamper_finding").fetchone()[0])


def _row(finding: Finding) -> tuple[object, ...]:
    return (
        finding.reference,
        finding.point_code,
        finding.kind.name,
        finding.standing.value,
        finding.found_on.isoformat(),
        finding.found_by,
        None if finding.settled_on is None else finding.settled_on.isoformat(),
        None if finding.since is None else finding.since.isoformat(),
        finding.evidence,
    )


def _read(row: tuple[object, ...]) -> Finding:
    return Finding(
        reference=str(row[0]),
        point_code=str(row[1]),
        kind=member_of(TamperKind, row[2], "tamper finding", field="name"),
        standing=member_of(Standing, row[3], "tamper standing"),
        found_on=parse_date(str(row[4])),
        found_by=str(row[5]),
        settled_on=None if row[6] is None else parse_date(str(row[6])),
        since=None if row[7] is None else parse_date(str(row[7])),
        evidence=None if row[8] is None else str(row[8]),
    )


__all__ = ["COLUMNS", "TamperRepository"]
