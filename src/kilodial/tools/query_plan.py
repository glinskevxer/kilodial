"""Check the queries this package actually runs still use an index.

An index that stops being used does not break anything. The query returns the
same rows, every test passes, and the book gets slower in a way nobody notices
until it has two hundred thousand runs on it and the annual filing takes nine
minutes. By then the change that did it is a year back.

So the hot queries are listed here with what they should hit, and sqlite is
asked what it would do with each of them. A query that says SEARCH is using an
index. A query that says SCAN is reading the whole table, and on the tables
listed below that is a regression whoever caused it should be told about while
they still remember.

Some scans are correct and they are listed as such. Counting every meter is a
scan and always will be, and pretending otherwise by adding an index would make
the book bigger for nothing.
"""

from __future__ import annotations

import sqlite3
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from kilodial.store.book import open_migrated
from kilodial.tools import FAILED, OK


@dataclass(frozen=True)
class Query:
    """One query the package runs, and what it should do."""

    name: str
    sql: str
    parameters: tuple[object, ...]
    wants_index: bool

    def plan(self, connection: sqlite3.Connection) -> list[str]:
        rows = connection.execute(f"EXPLAIN QUERY PLAN {self.sql}", self.parameters).fetchall()
        return [str(r[3]) for r in rows]


# The queries that run once per row of a report, plus the ones that run on every
# command. Anything not here is either rare or already a scan on purpose.
QUERIES: tuple[Query, ...] = (
    Query(
        "runs for one meter",
        "SELECT reference FROM bench_run WHERE meter_serial = ? ORDER BY tested_on",
        ("84-119302",),
        True,
    ),
    Query(
        "points of one run",
        "SELECT kind FROM bench_point WHERE run_reference = ? ORDER BY position",
        ("TR-1",),
        True,
    ),
    Query(
        "runs in a window",
        "SELECT reference FROM bench_run WHERE tested_on BETWEEN ? AND ?",
        ("2025-01-01", "2025-12-31"),
        True,
    ),
    Query(
        "sets at one point",
        "SELECT meter_serial FROM meter_set WHERE point_code = ? ORDER BY set_on",
        ("SP-1042",),
        True,
    ),
    Query(
        "sets for one meter",
        "SELECT point_code FROM meter_set WHERE meter_serial = ? ORDER BY set_on",
        ("84-119302",),
        True,
    ),
    Query(
        "billed history for one point",
        "SELECT amount FROM billed_month WHERE point_code = ? ORDER BY first_day",
        ("SP-1042",),
        True,
    ),
    Query(
        "meters of one type",
        "SELECT serial FROM meter WHERE device_key = ?",
        ("Halvern/R4S",),
        True,
    ),
    Query(
        "live work orders",
        "SELECT reference FROM work_order WHERE state IN ('OPEN', 'ASSIGNED')",
        (),
        True,
    ),
    Query(
        "open complaints",
        "SELECT reference FROM complaint_request WHERE closed_on IS NULL",
        (),
        True,
    ),
    Query(
        "tamper findings at one point",
        "SELECT reference FROM tamper_finding WHERE point_code = ? ORDER BY found_on",
        ("SP-1042",),
        True,
    ),
    Query(
        "repairs for one meter",
        "SELECT reference FROM repair WHERE meter_serial = ? ORDER BY repaired_on",
        ("84-119302",),
        True,
    ),
    Query(
        "the event log about one subject",
        "SELECT sequence FROM event WHERE subject = ? ORDER BY sequence",
        ("meter 84-119302",),
        True,
    ),
    Query(
        "every meter",
        "SELECT COUNT(*) FROM meter",
        (),
        False,
    ),
)


def faults() -> list[str]:
    """Every hot query that is not doing what it should."""
    found: list[str] = []
    with tempfile.TemporaryDirectory() as where:
        book = open_migrated(Path(where) / "plan.sqlite3", create=True)
        try:
            for query in QUERIES:
                steps = query.plan(book.connection)
                scanning = any(step.startswith("SCAN") for step in steps)
                if query.wants_index and scanning:
                    found.append(f"{query.name} scans: {'; '.join(steps)}")
                if not query.wants_index and not scanning:
                    found.append(
                        f"{query.name} was expected to scan and does not: {'; '.join(steps)}"
                    )
        finally:
            book.close()
    return found


def plans() -> dict[str, list[str]]:
    """What sqlite says it would do with each query, for a person to read."""
    with tempfile.TemporaryDirectory() as where:
        book = open_migrated(Path(where) / "plan.sqlite3", create=True)
        try:
            return {query.name: query.plan(book.connection) for query in QUERIES}
        finally:
            book.close()


def main(argv: list[str] | None = None) -> int:
    """Print any query that stopped using its index and say so in the exit code."""
    problems = faults()
    for problem in problems:
        print(problem)
    if problems:
        print(f"{len(problems)} queries are not using the indexes they should")
        return FAILED
    indexed = sum(1 for q in QUERIES if q.wants_index)
    print(f"{indexed} of {len(QUERIES)} hot queries use an index, as intended")
    return OK


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())


__all__ = ["QUERIES", "Query", "faults", "main", "plans"]
