"""Check the migration list against a book built from it.

Three things go wrong with a numbered migration list and none of them is caught
by the tests of the code that uses the tables:

A migration gets edited after it has shipped. Nothing here can prove that did
not happen, but the checks below catch the usual symptom, which is a list whose
numbering no longer runs from one without gaps.

Two statements get packed into one string. sqlite runs only the first and the
second is silently lost, so the table exists and one of its indexes does not.

The schema the migrations build stops matching what the repositories select
from. That is the expensive one, and the only honest way to check it is to
build a book from the migrations and ask sqlite what is in it.
"""

from __future__ import annotations

import sqlite3
import sys
import tempfile
from pathlib import Path

from kilodial.store.book import open_migrated
from kilodial.store.schema import MIGRATIONS, check_migrations, latest_number
from kilodial.tools import FAILED, OK

# Every table the package expects to be there once the book is up to date.
EXPECTED_TABLES = frozenset(
    {
        "schema_migration",
        "device_type",
        "meter",
        "reference_standard",
        "bench",
        "bench_run",
        "bench_point",
        "instrument_transformer",
        "service_point",
        "meter_set",
        "sample_group",
        "test_plan",
        "billed_month",
        "complaint_request",
    }
)


def tables_of(connection: sqlite3.Connection) -> set[str]:
    rows = connection.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
    ).fetchall()
    return {str(r[0]) for r in rows}


def indexes_of(connection: sqlite3.Connection) -> set[str]:
    rows = connection.execute(
        "SELECT name FROM sqlite_master WHERE type = 'index' AND name NOT LIKE 'sqlite_%'"
    ).fetchall()
    return {str(r[0]) for r in rows}


def faults() -> list[str]:
    """Everything wrong with the migration list and the book it builds."""
    found = list(check_migrations())
    with tempfile.TemporaryDirectory() as where:
        book = open_migrated(Path(where) / "check.sqlite3", create=True)
        try:
            if book.version != latest_number():
                found.append(
                    f"a fresh book came out at migration {book.version} and the code "
                    f"is at {latest_number()}"
                )
            if book.pending():
                found.append(f"a fresh book still has migrations pending: {book.pending()}")
            tables = tables_of(book.connection)
            for missing in sorted(EXPECTED_TABLES - tables):
                found.append(f"table {missing} is not built by any migration")
            for extra in sorted(tables - EXPECTED_TABLES):
                found.append(f"table {extra} is built but not expected")
            if len(indexes_of(book.connection)) < len(MIGRATIONS):
                found.append("the book has fewer indexes than it has migrations")
            found.extend(book.check())
        finally:
            book.close()
    return found


def main(argv: list[str] | None = None) -> int:
    """Print what is wrong and say so in the exit code."""
    problems = faults()
    for problem in problems:
        print(problem)
    if problems:
        print(f"{len(problems)} problems with the migration list")
        return FAILED
    print(f"{len(MIGRATIONS)} migrations build {len(EXPECTED_TABLES)} tables, all present")
    return OK


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
