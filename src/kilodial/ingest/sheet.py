"""A CSV reader that says which line it choked on.

Every file this package imports comes off somebody else's system: a bench
export, a billing extract, a roster from the field. All of them are broadly
right and occasionally wrong in a way that matters, and the only thing that
makes them workable is an error that names the line number and the column.

So the reader is a thin thing over the standard library with three habits:

Headers are matched case insensitively and with spaces and underscores treated
the same, because three systems spell "meter serial" three ways and none of them
is going to change.

Missing required columns are reported all at once. A file with four missing
columns should not need four runs to find out.

A row that fails validation does not stop the read. The failures are collected
with their line numbers and handed back, so an operator gets the whole list and
can fix the file once.
"""

from __future__ import annotations

import csv
from collections.abc import Iterator
from dataclasses import dataclass
from io import StringIO
from pathlib import Path

from kilodial.errors import BadInputError


def normalise(name: str) -> str:
    """A column name reduced to what three systems agree on."""
    return " ".join(name.strip().lower().replace("_", " ").split())


@dataclass(frozen=True)
class Row:
    """One data row, with the line it came from."""

    line: int
    values: dict[str, str]

    def get(self, column: str, default: str | None = None) -> str | None:
        """A column's value, or a default when it is blank or absent."""
        found = self.values.get(normalise(column))
        if found is None or not found.strip():
            return default
        return found.strip()

    def need(self, column: str) -> str:
        """A column's value, refusing to carry on without it."""
        found = self.get(column)
        if found is None:
            raise BadInputError(f"line {self.line}: {column} is empty")
        return found

    def __str__(self) -> str:
        return f"line {self.line}"


@dataclass(frozen=True)
class Sheet:
    """A whole file, read and checked for the columns it was promised."""

    columns: tuple[str, ...]
    rows: tuple[Row, ...]

    def __len__(self) -> int:
        return len(self.rows)

    def __iter__(self) -> Iterator[Row]:
        return iter(self.rows)

    def has(self, column: str) -> bool:
        return normalise(column) in self.columns


def read_text(text: str, *, required: list[str] | None = None) -> Sheet:
    """Read a sheet out of a string, checking the columns it must carry."""
    reader = csv.reader(StringIO(text))
    try:
        header = next(reader)
    except StopIteration:
        raise BadInputError("the file is empty") from None
    columns = tuple(normalise(name) for name in header)
    if len(set(columns)) != len(columns):
        raise BadInputError("the file has the same column twice")
    missing = [c for c in (required or []) if normalise(c) not in columns]
    if missing:
        raise BadInputError(f"the file is missing {', '.join(sorted(missing))}")
    rows: list[Row] = []
    for line, values in enumerate(reader, start=2):
        if not any(v.strip() for v in values):
            continue
        if len(values) != len(columns):
            raise BadInputError(f"line {line}: {len(values)} values against {len(columns)} columns")
        rows.append(Row(line, dict(zip(columns, values, strict=True))))
    return Sheet(columns, tuple(rows))


def read_file(path: str | Path, *, required: list[str] | None = None) -> Sheet:
    """Read a sheet off disk."""
    target = Path(path)
    if not target.exists():
        raise BadInputError(f"there is no file at {target}")
    return read_text(target.read_text(), required=required)


@dataclass(frozen=True)
class Outcome:
    """What an import did, and everything it could not do."""

    taken: int
    skipped: tuple[tuple[int, str], ...]

    @property
    def clean(self) -> bool:
        return not self.skipped

    def show(self) -> str:
        return f"{self.taken} rows taken, {len(self.skipped)} left"

    def __str__(self) -> str:
        return self.show()


__all__ = ["Outcome", "Row", "Sheet", "normalise", "read_file", "read_text"]
