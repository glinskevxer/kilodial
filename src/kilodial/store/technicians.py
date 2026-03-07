"""Storing technicians and their certifications.

The register is small and it is asked one question over and over: was this badge
certified on this day. That query runs once per run every time a report is
built, so the repository keeps it cheap and the callers keep it honest by asking
about a day rather than about today.

A certification is replaced rather than extended when somebody recertifies. The
old window is not kept, and that is a real limitation: a run from before the
last recertification cannot be checked against the window that was in force at
the time. Keeping a history is the right fix and it is not free, so it waits
until somebody needs it.
"""

from __future__ import annotations

import sqlite3

from kilodial.errors import DuplicateError, NotFoundError, RuleError
from kilodial.model.technician import Grade, Technician
from kilodial.store.base import has_row, one_row, or_none, upper
from kilodial.store.codec import read_technician, technician_row
from kilodial.units.span import parse_date

COLUMNS = "badge, name, grade, certified_on, certificate_due, note"


class TechnicianRepository:
    """Technicians on one book."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._conn = connection

    def add(self, technician: Technician) -> Technician:
        """Put a technician on the register."""
        if self.exists(technician.badge):
            raise DuplicateError("technician", technician.badge)
        self._conn.execute(
            f"INSERT INTO technician ({COLUMNS}) VALUES (?, ?, ?, ?, ?, ?)",
            technician_row(technician),
        )
        return technician

    def save(self, technician: Technician) -> Technician:
        """Write a technician already on the register back over themselves."""
        if not self.exists(technician.badge):
            raise NotFoundError("technician", technician.badge)
        row = technician_row(technician)
        self._conn.execute(
            "UPDATE technician SET name = ?, grade = ?, certified_on = ?, "
            "certificate_due = ?, note = ? WHERE badge = ?",
            (*row[1:], row[0]),
        )
        return technician

    def exists(self, badge: str) -> bool:
        return has_row(self._conn, "technician", "badge", upper(badge))

    def get(self, badge: str) -> Technician:
        return read_technician(
            one_row(self._conn, COLUMNS, "technician", "badge", upper(badge), "technician")
        )

    def find(self, badge: str | None) -> Technician | None:
        """Look one up, taking None for a run that names nobody."""
        return or_none(self.get, badge)

    def all(self) -> list[Technician]:
        rows = self._conn.execute(f"SELECT {COLUMNS} FROM technician ORDER BY badge").fetchall()
        return [read_technician(r) for r in rows]

    def certified_on(self, day: object) -> list[Technician]:
        when = parse_date(day).isoformat()
        rows = self._conn.execute(
            f"SELECT {COLUMNS} FROM technician WHERE certified_on <= ? "
            "AND certificate_due >= ? ORDER BY badge",
            (when, when),
        ).fetchall()
        return [read_technician(r) for r in rows]

    def by_grade(self, grade: Grade) -> list[Technician]:
        rows = self._conn.execute(
            f"SELECT {COLUMNS} FROM technician WHERE grade = ? ORDER BY badge",
            (grade.name,),
        ).fetchall()
        return [read_technician(r) for r in rows]

    def due_within(self, day: object, days: int) -> list[Technician]:
        """Certifications running out inside the next so many days."""
        if days < 0:
            raise RuleError("a recertification window cannot look backwards")
        return [t for t in self.all() if 0 <= t.days_left_on(day) <= days]

    def lapsed_on(self, day: object) -> list[Technician]:
        return [t for t in self.all() if t.days_left_on(day) < 0]

    def count(self) -> int:
        return int(self._conn.execute("SELECT COUNT(*) FROM technician").fetchone()[0])


__all__ = ["COLUMNS", "TechnicianRepository"]
