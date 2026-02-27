from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest

from kilodial.store.book import Book, open_migrated
from kilodial.store.bulk import CHUNK, chunked, insert_many, statement


@pytest.fixture
def book(tmp_path: Path) -> Iterator[Book]:
    opened = open_migrated(tmp_path / "shop.sqlite3", create=True)
    yield opened
    opened.close()


def rows(count: int, start: int = 0) -> list[tuple[object, ...]]:
    return [
        (f"84-{index:06d}", "Halvern/R4S", "stock", "2015-01-01", "utility", None, None)
        for index in range(start, start + count)
    ]


COLUMNS = ["serial", "device_key", "state", "acquired", "owner", "seal", "retired_on"]


def test_chunking() -> None:
    assert [len(b) for b in chunked(rows(5), 2)] == [2, 2, 1]
    assert [len(b) for b in chunked(rows(4), 2)] == [2, 2]
    assert list(chunked([], 2)) == []
    assert CHUNK > 1


def test_a_daft_chunk_size() -> None:
    with pytest.raises(ValueError, match="positive"):
        list(chunked(rows(2), 0))


def test_the_statement() -> None:
    assert statement("meter", ["a", "b"]) == "INSERT INTO meter (a, b) VALUES (?, ?)"


def test_inserting_a_batch(book: Book) -> None:
    written = insert_many(book.connection, "meter", COLUMNS, rows(10))
    assert written == 10
    assert book.connection.execute("SELECT COUNT(*) FROM meter").fetchone()[0] == 10


def test_inserting_more_than_one_chunk(book: Book) -> None:
    written = insert_many(book.connection, "meter", COLUMNS, rows(1200))
    assert written == 1200
    assert book.connection.execute("SELECT COUNT(*) FROM meter").fetchone()[0] == 1200


def test_inserting_nothing(book: Book) -> None:
    assert insert_many(book.connection, "meter", COLUMNS, []) == 0


def test_a_failing_batch_reports_the_row_that_broke(book: Book) -> None:
    bad = rows(3) + [rows(1)[0]]
    with pytest.raises(sqlite3.IntegrityError, match="UNIQUE"):
        insert_many(book.connection, "meter", COLUMNS, bad, size=10)


def test_the_good_rows_of_a_failing_batch_are_still_written(book: Book) -> None:
    bad = rows(3) + [rows(1)[0]]
    with pytest.raises(sqlite3.IntegrityError):
        insert_many(book.connection, "meter", COLUMNS, bad, size=10)
    assert book.connection.execute("SELECT COUNT(*) FROM meter").fetchone()[0] == 3


def test_a_small_chunk_size_still_writes_everything(book: Book) -> None:
    assert insert_many(book.connection, "meter", COLUMNS, rows(7), size=2) == 7
    assert book.connection.execute("SELECT COUNT(*) FROM meter").fetchone()[0] == 7
