"""Storing benches and the standards behind them.

The one query worth reading twice is ``standard_for``. A run records both a
bench and a standard, and it has to, because a bench's standard gets swapped
when one goes away for recertification. Resolving the standard through the bench
at report time would quietly attribute every historic run to whatever standard
is on the bench today, which is exactly the fact a hearing would want.
"""

from __future__ import annotations

import sqlite3

from kilodial.errors import DuplicateError, NotFoundError, RuleError
from kilodial.model.bench import Bench, ReferenceStandard
from kilodial.store.base import has_row, one_row, or_none, upper
from kilodial.store.codec import bench_row, read_bench, read_standard, standard_row
from kilodial.units.span import parse_date

STANDARD_COLUMNS = (
    "serial, maker, model_code, certificate, certified_on, certificate_due, "
    "uncertainty, traceable_to"
)
BENCH_COLUMNS = (
    "code, name, positions, standard_serial, max_amperes, max_volts, polyphase, installed, removed"
)


class StandardRepository:
    """Reference standards on one book."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._conn = connection

    def add(self, standard: ReferenceStandard) -> ReferenceStandard:
        if self.exists(standard.serial):
            raise DuplicateError("reference standard", standard.serial)
        self._conn.execute(
            f"INSERT INTO reference_standard ({STANDARD_COLUMNS}) VALUES ({', '.join('?' * 8)})",
            standard_row(standard),
        )
        return standard

    def save(self, standard: ReferenceStandard) -> ReferenceStandard:
        if not self.exists(standard.serial):
            raise NotFoundError("reference standard", standard.serial)
        row = standard_row(standard)
        self._conn.execute(
            "UPDATE reference_standard SET maker = ?, model_code = ?, certificate = ?, "
            "certified_on = ?, certificate_due = ?, uncertainty = ?, traceable_to = ? "
            "WHERE serial = ?",
            (*row[1:], row[0]),
        )
        return standard

    def exists(self, serial: str) -> bool:
        return has_row(self._conn, "reference_standard", "serial", upper(serial))

    def get(self, serial: str) -> ReferenceStandard:
        return read_standard(
            one_row(
                self._conn,
                STANDARD_COLUMNS,
                "reference_standard",
                "serial",
                upper(serial),
                "reference standard",
            )
        )

    def find(self, serial: str | None) -> ReferenceStandard | None:
        """Look one up, handing back nothing rather than raising."""
        return or_none(self.get, serial)

    def all(self) -> list[ReferenceStandard]:
        rows = self._conn.execute(
            f"SELECT {STANDARD_COLUMNS} FROM reference_standard ORDER BY serial"
        ).fetchall()
        return [read_standard(r) for r in rows]

    def valid_on(self, day: object) -> list[ReferenceStandard]:
        when = parse_date(day).isoformat()
        rows = self._conn.execute(
            f"SELECT {STANDARD_COLUMNS} FROM reference_standard "
            "WHERE certified_on <= ? AND certificate_due >= ? ORDER BY serial",
            (when, when),
        ).fetchall()
        return [read_standard(r) for r in rows]

    def due_within(self, day: object, days: int) -> list[ReferenceStandard]:
        """Standards whose certificate runs out inside the next so many days."""
        if days < 0:
            raise RuleError("a recertification window cannot look backwards")
        return [s for s in self.all() if 0 <= s.days_left_on(day) <= days]

    def expired_on(self, day: object) -> list[ReferenceStandard]:
        return [s for s in self.all() if s.days_left_on(day) < 0]

    def count(self) -> int:
        return int(self._conn.execute("SELECT COUNT(*) FROM reference_standard").fetchone()[0])


class BenchRepository:
    """Benches on one book."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._conn = connection
        self._standards = StandardRepository(connection)

    def add(self, bench: Bench) -> Bench:
        if self.exists(bench.code):
            raise DuplicateError("bench", bench.code)
        if not self._standards.exists(bench.standard_serial):
            raise RuleError(
                f"bench {bench.code} names standard {bench.standard_serial}, "
                "which is not on the book"
            )
        self._conn.execute(
            f"INSERT INTO bench ({BENCH_COLUMNS}) VALUES ({', '.join('?' * 9)})",
            bench_row(bench),
        )
        return bench

    def save(self, bench: Bench) -> Bench:
        if not self.exists(bench.code):
            raise NotFoundError("bench", bench.code)
        row = bench_row(bench)
        self._conn.execute(
            "UPDATE bench SET name = ?, positions = ?, standard_serial = ?, "
            "max_amperes = ?, max_volts = ?, polyphase = ?, installed = ?, removed = ? "
            "WHERE code = ?",
            (*row[1:], row[0]),
        )
        return bench

    def exists(self, code: str) -> bool:
        return has_row(self._conn, "bench", "code", upper(code))

    def get(self, code: str) -> Bench:
        return read_bench(one_row(self._conn, BENCH_COLUMNS, "bench", "code", upper(code), "bench"))

    def find(self, code: str | None) -> Bench | None:
        """Look one up, handing back nothing rather than raising."""
        return or_none(self.get, code)

    def all(self) -> list[Bench]:
        rows = self._conn.execute(f"SELECT {BENCH_COLUMNS} FROM bench ORDER BY code").fetchall()
        return [read_bench(r) for r in rows]

    def available_on(self, day: object) -> list[Bench]:
        return [b for b in self.all() if b.is_available_on(day)]

    def standard_for(self, code: str) -> ReferenceStandard:
        """The standard sitting on that bench right now, not historically."""
        return self._standards.get(self.get(code).standard_serial)

    def using(self, standard_serial: str) -> list[Bench]:
        rows = self._conn.execute(
            f"SELECT {BENCH_COLUMNS} FROM bench WHERE standard_serial = ? ORDER BY code",
            (standard_serial.strip().upper(),),
        ).fetchall()
        return [read_bench(r) for r in rows]

    def count(self) -> int:
        return int(self._conn.execute("SELECT COUNT(*) FROM bench").fetchone()[0])


__all__ = ["BENCH_COLUMNS", "STANDARD_COLUMNS", "BenchRepository", "StandardRepository"]
