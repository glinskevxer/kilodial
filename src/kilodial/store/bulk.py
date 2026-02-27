"""Inserting many rows at once, because the loop was the slow part.

Restoring a book of any size ran one INSERT per row through Python, and on a
book with a hundred thousand readings on it that is a hundred thousand round
trips into sqlite for no reason. ``executemany`` does the same work in one call
and the difference on a real book is minutes.

The chunking is not about sqlite. It is about not building a list of a million
tuples in memory to hand over in one go, which is the shape a restore from a
very large export takes.

There is one behaviour worth knowing about and it is why this is a module rather
than a one liner: ``executemany`` reports the row that failed by number and not
by content, so a batch that hits a constraint tells you very little. The retry
here falls back to one row at a time on failure, which is slow and only happens
on the failing chunk, and produces the error naming the row that actually broke.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable, Iterator
from typing import Any

CHUNK = 500


def chunked(rows: Iterable[tuple[Any, ...]], size: int = CHUNK) -> Iterator[list[tuple[Any, ...]]]:
    """Break an iterable of rows into lists of at most ``size``."""
    if size <= 0:
        raise ValueError("a chunk size has to be positive")
    batch: list[tuple[Any, ...]] = []
    for row in rows:
        batch.append(row)
        if len(batch) >= size:
            yield batch
            batch = []
    if batch:
        yield batch


def statement(table: str, columns: list[str]) -> str:
    """The insert one of these batches runs."""
    marks = ", ".join("?" * len(columns))
    return f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({marks})"


def insert_many(
    connection: sqlite3.Connection,
    table: str,
    columns: list[str],
    rows: Iterable[tuple[Any, ...]],
    *,
    size: int = CHUNK,
) -> int:
    """Insert rows in batches, falling back to one at a time on a failure.

    The fallback is what makes an error usable. A chunk of five hundred rows
    that violates a constraint reports the constraint and nothing about which
    row, so the chunk is replayed row by row and the error comes from the insert
    that actually failed, with its values in the traceback.
    """
    sql = statement(table, columns)
    written = 0
    for batch in chunked(rows, size):
        try:
            connection.executemany(sql, batch)
        except sqlite3.Error:
            for row in batch:
                connection.execute(sql, row)
        written += len(batch)
    return written


__all__ = ["CHUNK", "chunked", "insert_many", "statement"]
