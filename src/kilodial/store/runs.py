"""Storing bench runs and the points that belong to them.

A run and its points go in together or not at all, which is why the write is
wrapped in a savepoint rather than a transaction. Half a run on the book is
worse than no run: the sequence checks would read it as a meter that was never
light load tested, and that is a finding rather than a gap. A savepoint rather
than BEGIN because the command layer already holds a transaction by the time it
gets here, and sqlite will not nest one of those.

Points keep their position column so that the order the technician ran them
survives. Nothing computes off the order, and that is exactly why it would have
been dropped by now if it were not written down.
"""

from __future__ import annotations

import sqlite3

from kilodial.errors import DuplicateError, NotFoundError, RuleError
from kilodial.model.run import BenchPoint, BenchRun, RunKind
from kilodial.store.codec import point_row, read_point, read_run, run_row
from kilodial.units.span import parse_date

RUN_COLUMNS = (
    "reference, meter_serial, bench_code, standard_serial, kind, tested_on, technician, note"
)
POINT_COLUMNS = (
    "run_reference, position, kind, amperes, volts, pf_value, pf_sense, registration, crept"
)


class RunRepository:
    """Bench runs on one book."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._conn = connection

    def add(self, run: BenchRun, *, check_references: bool = True) -> BenchRun:
        """Write a run and its points inside one transaction."""
        if self.exists(run.reference):
            raise DuplicateError("bench run", run.reference)
        if check_references:
            self._check_references(run)
        self._conn.execute("SAVEPOINT add_run")
        try:
            self._conn.execute(
                f"INSERT INTO bench_run ({RUN_COLUMNS}) VALUES ({', '.join('?' * 8)})",
                run_row(run),
            )
            for position, point in enumerate(run.points, start=1):
                self._conn.execute(
                    f"INSERT INTO bench_point ({POINT_COLUMNS}) VALUES ({', '.join('?' * 9)})",
                    point_row(run.reference, position, point),
                )
        except BaseException:
            self._conn.execute("ROLLBACK TO add_run")
            self._conn.execute("RELEASE add_run")
            raise
        self._conn.execute("RELEASE add_run")
        return run

    def _check_references(self, run: BenchRun) -> None:
        missing: list[str] = []
        for table, column, value in (
            ("meter", "serial", run.meter_serial),
            ("bench", "code", run.bench_code),
            ("reference_standard", "serial", run.standard_serial),
        ):
            found = self._conn.execute(
                f"SELECT 1 FROM {table} WHERE {column} = ?", (value,)
            ).fetchone()
            if found is None:
                missing.append(f"{table.replace('_', ' ')} {value}")
        if missing:
            raise RuleError(
                f"run {run.reference} names {' and '.join(missing)}, which is not on the book"
            )

    def exists(self, reference: str) -> bool:
        found = self._conn.execute(
            "SELECT 1 FROM bench_run WHERE reference = ?", (reference.strip().upper(),)
        ).fetchone()
        return found is not None

    def get(self, reference: str) -> BenchRun:
        key = reference.strip().upper()
        row = self._conn.execute(
            f"SELECT {RUN_COLUMNS} FROM bench_run WHERE reference = ?", (key,)
        ).fetchone()
        if row is None:
            raise NotFoundError("bench run", key)
        return read_run(row, self._points(key))

    def find(self, reference: str) -> BenchRun | None:
        try:
            return self.get(reference)
        except NotFoundError:
            return None

    def _points(self, reference: str) -> list[BenchPoint]:
        rows = self._conn.execute(
            f"SELECT {POINT_COLUMNS} FROM bench_point WHERE run_reference = ? ORDER BY position",
            (reference,),
        ).fetchall()
        return [read_point(r) for r in rows]

    def _hydrate(self, rows: list[tuple[object, ...]]) -> list[BenchRun]:
        return [read_run(r, self._points(str(r[0]))) for r in rows]

    def for_meter(self, serial: str) -> list[BenchRun]:
        """Every run on one meter, oldest first."""
        rows = self._conn.execute(
            f"SELECT {RUN_COLUMNS} FROM bench_run WHERE meter_serial = ? "
            "ORDER BY tested_on, reference",
            (serial.strip().upper(),),
        ).fetchall()
        return self._hydrate(rows)

    def latest_for(self, serial: str, kind: RunKind | None = None) -> BenchRun | None:
        """The most recent run on a meter, optionally of one kind only."""
        runs = self.for_meter(serial)
        if kind is not None:
            runs = [r for r in runs if r.kind is kind]
        return runs[-1] if runs else None

    def on_day(self, day: object) -> list[BenchRun]:
        rows = self._conn.execute(
            f"SELECT {RUN_COLUMNS} FROM bench_run WHERE tested_on = ? ORDER BY reference",
            (parse_date(day).isoformat(),),
        ).fetchall()
        return self._hydrate(rows)

    def between(self, first: object, last: object) -> list[BenchRun]:
        start = parse_date(first)
        end = parse_date(last)
        if end < start:
            raise RuleError("a run window cannot end before it starts")
        rows = self._conn.execute(
            f"SELECT {RUN_COLUMNS} FROM bench_run WHERE tested_on BETWEEN ? AND ? "
            "ORDER BY tested_on, reference",
            (start.isoformat(), end.isoformat()),
        ).fetchall()
        return self._hydrate(rows)

    def by_kind(self, kind: RunKind) -> list[BenchRun]:
        rows = self._conn.execute(
            f"SELECT {RUN_COLUMNS} FROM bench_run WHERE kind = ? ORDER BY tested_on, reference",
            (kind.value,),
        ).fetchall()
        return self._hydrate(rows)

    def on_bench(self, code: str) -> list[BenchRun]:
        rows = self._conn.execute(
            f"SELECT {RUN_COLUMNS} FROM bench_run WHERE bench_code = ? "
            "ORDER BY tested_on, reference",
            (code.strip().upper(),),
        ).fetchall()
        return self._hydrate(rows)

    def delete(self, reference: str) -> None:
        """Remove a run and, through the cascade, its points."""
        key = reference.strip().upper()
        if not self.exists(key):
            raise NotFoundError("bench run", key)
        self._conn.execute("DELETE FROM bench_run WHERE reference = ?", (key,))

    def all(self) -> list[BenchRun]:
        rows = self._conn.execute(
            f"SELECT {RUN_COLUMNS} FROM bench_run ORDER BY tested_on, reference"
        ).fetchall()
        return self._hydrate(rows)

    def count(self) -> int:
        return int(self._conn.execute("SELECT COUNT(*) FROM bench_run").fetchone()[0])


__all__ = ["POINT_COLUMNS", "RUN_COLUMNS", "RunRepository"]
