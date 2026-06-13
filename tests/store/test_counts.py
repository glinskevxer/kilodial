from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from kilodial.store.book import Book, open_migrated
from kilodial.store.counts import (
    CHILDREN,
    TABLES,
    counts,
    labels,
    statement,
    tables,
)
from kilodial.store.dump import table_names
from kilodial.tools.smoke import stand_up


@pytest.fixture
def book(tmp_path: Path) -> Iterator[Book]:
    opened = open_migrated(tmp_path / "shop.sqlite3", create=True)
    yield opened
    opened.close()


def test_every_table_on_the_book_is_counted_or_excused(book: Book) -> None:
    on_book = set(table_names(book.connection)) | {"schema_migration"}
    assert set(tables()) | set(CHILDREN) == on_book
    assert not set(tables()) & set(CHILDREN)


def test_the_excused_tables_say_why() -> None:
    assert "bench_point" in CHILDREN
    assert all(why for why in CHILDREN.values())


def test_the_labels_are_the_shops_words() -> None:
    assert "groups" in labels()
    assert "sample_group" not in labels()
    assert "runs" in labels()
    assert len(labels()) == len(TABLES)


def test_an_empty_book_counts_zero_everywhere(book: Book) -> None:
    found = counts(book.connection)
    assert set(found) == set(labels())
    assert all(count == 0 for count in found.values())


def test_the_counts_follow_the_rows(book: Book) -> None:
    from kilodial.store.shop import Shop

    stand_up(Shop(book))
    found = counts(book.connection)
    assert found["meters"] == 1
    assert found["billed months"] == 6
    assert found["runs"] == 0


def test_the_order_is_the_order_the_labels_are_listed(book: Book) -> None:
    assert list(counts(book.connection)) == labels()


def test_it_really_is_one_statement() -> None:
    assert statement().count("SELECT") == len(TABLES)
    assert ";" not in statement()
    assert statement().count("UNION ALL") == len(TABLES) - 1


def test_no_label_or_table_is_listed_twice() -> None:
    assert len(set(labels())) == len(labels())
    assert len(set(tables())) == len(tables())
