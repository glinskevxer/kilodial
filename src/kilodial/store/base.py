"""The three things every repository was writing out for itself.

Nothing here is clever. It exists because the same twelve lines appeared in ten
files and two of the copies had already drifted: one enum reader raised
BadInputError where the rest raised ConfigError, so a corrupted book reported
itself as a caller mistake.

``member_of`` is the important one. A value that comes back off the book and is
not a member of the enum it is supposed to be is a corrupted book, not bad
input, and the error class is the difference between "fix your command" and
"your database has a row nobody wrote".
"""

from __future__ import annotations

import enum
import sqlite3
from collections.abc import Callable
from typing import Any, TypeVar

from kilodial.errors import ConfigError, NotFoundError

_E = TypeVar("_E", bound=enum.Enum)
_T = TypeVar("_T")


FIELDS = ("value", "name", "code", "label")


def member_of(cls: type[_E], value: object, what: str, *, field: str = "value") -> _E:
    """Read an enum member out of a stored value.

    Which attribute the column stores has to be passed in rather than guessed.
    Some of these enums carry a tuple as their value and a separate short code,
    some store their name, and a reader that tried all three would match the
    wrong member on the day two enums overlap.
    """
    if field not in FIELDS:
        raise ConfigError(f"an enum column is stored by {FIELDS}, not by {field!r}")
    for member in cls:
        if getattr(member, field, None) == value:
            return member
    raise ConfigError(f"the book holds {value!r}, which is not a {what}")


def upper(value: str) -> str:
    """A key as the book stores it: trimmed and upper cased."""
    return value.strip().upper()


def or_none(getter: Callable[[str], _T], key: str | None) -> _T | None:
    """Run a lookup that raises, and hand back nothing instead.

    Every repository wants both shapes and the raising one is the primary,
    because a caller that has not thought about the missing case should be made
    to. This is the escape hatch for the callers that have.
    """
    if key is None:
        return None
    try:
        return getter(key)
    except NotFoundError:
        return None


def has_row(connection: sqlite3.Connection, table: str, column: str, value: str) -> bool:
    """Whether a table holds a row with that key, which every repository asks."""
    found = connection.execute(f"SELECT 1 FROM {table} WHERE {column} = ?", (value,)).fetchone()
    return found is not None


def one_row(
    connection: sqlite3.Connection,
    columns: str,
    table: str,
    column: str,
    value: str,
    kind: str,
) -> tuple[Any, ...]:
    """One row by key, raising the standard not found error when there is none.

    The ``kind`` is what the error calls the record, and it is passed in rather
    than derived from the table name because the two are not always the same
    word: the table is ``sample_group`` and the thing a person is looking for is
    a sampling group.
    """
    row = connection.execute(
        f"SELECT {columns} FROM {table} WHERE {column} = ?", (value,)
    ).fetchone()
    if row is None:
        raise NotFoundError(kind, value)
    return tuple(row)


__all__ = ["FIELDS", "has_row", "member_of", "one_row", "or_none", "upper"]
