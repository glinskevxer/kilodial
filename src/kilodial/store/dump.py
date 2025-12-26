"""Writing a whole book out as json, and reading one back in.

sqlite files copy perfectly well and this is not a substitute for that. What it
is for is the two things a file copy cannot do: hand a book to somebody whose
tools are not sqlite, and see in a diff what changed between two of them.

The dump is generic. It reads the table list off the book rather than naming the
tables, so a migration that adds a table does not need a line here, and a dump
taken today can be read by a version of this code that has more tables than it
does. That genericism is deliberate and it has one cost worth stating: the dump
carries no schema, so restoring it needs a book already migrated to the same
version. It refuses rather than guessing when the versions differ, because a
restore that silently drops a column is worse than no restore.

Loading defers foreign keys to the commit, so the tables can go in in
alphabetical order without a dependency sort. The constraints are still checked;
they are checked once, against the whole book.

Rows go out in primary key order where there is one and in rowid order where
there is not, so two dumps of the same book compare equal line for line.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from typing import Any

from kilodial.errors import ConfigError, RuleError
from kilodial.store.book import Book
from kilodial.store.schema import APPLICATION_ID

FORMAT = 1
# The migration ledger is not dumped. Its version is carried on the dump itself,
# and its rows carry the day each migration ran on the book it ran on, which is
# a fact about that file rather than about the shop.
SKIP = frozenset({"sqlite_sequence", "schema_migration"})


@dataclass(frozen=True)
class Table:
    """One table's contents, as columns and rows."""

    name: str
    columns: tuple[str, ...]
    rows: tuple[tuple[Any, ...], ...]

    def __len__(self) -> int:
        return len(self.rows)

    def dicts(self) -> list[dict[str, Any]]:
        return [dict(zip(self.columns, row, strict=True)) for row in self.rows]


def table_names(connection: sqlite3.Connection) -> list[str]:
    """Every table on the book worth dumping, in name order."""
    rows = connection.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' "
        "ORDER BY name"
    ).fetchall()
    return [str(r[0]) for r in rows if str(r[0]) not in SKIP]


def columns_of(connection: sqlite3.Connection, table: str) -> list[str]:
    """A table's column names, in the order the table declares them."""
    rows = connection.execute(f"PRAGMA table_info({table})").fetchall()
    return [str(r[1]) for r in rows]


def read_table(connection: sqlite3.Connection, name: str) -> Table:
    """One table, rows in a stable order."""
    columns = columns_of(connection, name)
    order = ", ".join(columns)
    rows = connection.execute(f"SELECT {order} FROM {name} ORDER BY {order}").fetchall()
    return Table(name, tuple(columns), tuple(tuple(r) for r in rows))


def dump(book: Book) -> dict[str, Any]:
    """The whole book as a plain dictionary."""
    connection = book.connection
    tables = {}
    for name in table_names(connection):
        table = read_table(connection, name)
        tables[name] = {"columns": list(table.columns), "rows": [list(r) for r in table.rows]}
    return {
        "format": FORMAT,
        "application": APPLICATION_ID,
        "version": book.version,
        "tables": tables,
    }


def to_json(book: Book) -> str:
    """The dump as json, sorted so two dumps compare cleanly."""
    return json.dumps(dump(book), indent=2, sort_keys=True) + "\n"


def counts(payload: dict[str, Any]) -> dict[str, int]:
    """How many rows each table in a dump carries."""
    return {name: len(body["rows"]) for name, body in payload["tables"].items()}


def check(payload: object) -> dict[str, Any]:
    """Read a dump, refusing anything that is not one."""
    if not isinstance(payload, dict):
        raise ConfigError("a book dump is an object, not whatever that is")
    for field in ("format", "application", "version", "tables"):
        if field not in payload:
            raise ConfigError(f"a book dump has a {field} and this one does not")
    if payload["format"] != FORMAT:
        raise ConfigError(f"this dump is format {payload['format']} and this code reads {FORMAT}")
    if payload["application"] != APPLICATION_ID:
        raise ConfigError("that dump is not from a kilodial book")
    if not isinstance(payload["tables"], dict):
        raise ConfigError("the tables in a dump are an object keyed by table name")
    return payload


def restore(book: Book, payload: object) -> dict[str, int]:
    """Load a dump into an empty book at the same migration.

    The book has to be empty. Merging two books is a real thing somebody will
    want one day and it is not this: deciding what happens when both sides have
    a meter 84-119302 is a policy question, and answering it silently inside a
    restore would be the wrong place.
    """
    found = check(payload)
    if book.version != found["version"]:
        raise RuleError(
            f"the dump is from migration {found['version']} and this book is at {book.version}"
        )
    connection = book.connection
    for name in table_names(connection):
        if connection.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0]:
            raise RuleError(f"table {name} is not empty, so there is nothing to restore into")
    loaded: dict[str, int] = {}
    with book.transaction():
        # Tables go in alphabetically, which is not foreign key order, so the
        # constraints are deferred to the commit. That checks them once against
        # the finished book rather than row by row against a half loaded one,
        # which is both correct and the only way to load in any fixed order.
        connection.execute("PRAGMA defer_foreign_keys = ON")
        for name, body in sorted(found["tables"].items()):
            columns = list(body["columns"])
            marks = ", ".join("?" * len(columns))
            statement = f"INSERT INTO {name} ({', '.join(columns)}) VALUES ({marks})"
            for row in body["rows"]:
                connection.execute(statement, tuple(row))
            loaded[name] = len(body["rows"])
    return loaded


__all__ = [
    "FORMAT",
    "SKIP",
    "Table",
    "check",
    "columns_of",
    "counts",
    "dump",
    "read_table",
    "restore",
    "table_names",
    "to_json",
]
