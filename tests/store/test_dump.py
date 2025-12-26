from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest

from kilodial.errors import ConfigError, RuleError
from kilodial.store.book import Book, open_migrated
from kilodial.store.dump import (
    FORMAT,
    check,
    columns_of,
    counts,
    dump,
    read_table,
    restore,
    table_names,
    to_json,
)
from kilodial.store.shop import Shop, open_shop
from kilodial.tools.smoke import stand_up


@pytest.fixture
def shop(tmp_path: Path) -> Iterator[Shop]:
    opened = open_shop(tmp_path / "shop.sqlite3", create=True)
    stand_up(opened)
    yield opened
    opened.close()


@pytest.fixture
def empty(tmp_path: Path) -> Iterator[Book]:
    book = open_migrated(tmp_path / "empty.sqlite3", create=True)
    yield book
    book.close()


def test_every_table_is_dumped(shop: Shop) -> None:
    names = table_names(shop.book.connection)
    assert "meter" in names
    assert "schema_migration" not in names
    assert "sqlite_sequence" not in names
    assert names == sorted(names)


def test_a_table_comes_back_with_its_columns(shop: Shop) -> None:
    table = read_table(shop.book.connection, "meter")
    assert "serial" in table.columns
    assert len(table) == 1
    assert table.dicts()[0]["serial"] == "84-119302"


def test_columns_of(shop: Shop) -> None:
    assert columns_of(shop.book.connection, "bench")[0] == "code"


def test_the_dump_carries_its_version(shop: Shop) -> None:
    payload = dump(shop.book)
    assert payload["format"] == FORMAT
    assert payload["version"] == shop.book.version
    assert payload["tables"]["meter"]["rows"][0][0] == "84-119302"


def test_the_counts(shop: Shop) -> None:
    found = counts(dump(shop.book))
    assert found["meter"] == 1
    assert found["billed_month"] == 6
    assert found["bench_run"] == 0


def test_two_dumps_of_one_book_are_identical(shop: Shop) -> None:
    assert to_json(shop.book) == to_json(shop.book)
    assert json.loads(to_json(shop.book))["version"] == shop.book.version


def test_a_round_trip(shop: Shop, empty: Book) -> None:
    payload = dump(shop.book)
    loaded = restore(empty, payload)
    assert loaded["meter"] == 1
    assert dump(empty) == payload


def test_a_round_trip_through_json(shop: Shop, empty: Book) -> None:
    restore(empty, json.loads(to_json(shop.book)))
    assert to_json(empty) == to_json(shop.book)


def test_restoring_into_a_book_that_is_not_empty(shop: Shop) -> None:
    with pytest.raises(RuleError, match="is not empty"):
        restore(shop.book, dump(shop.book))


def test_a_dump_from_another_migration(shop: Shop, empty: Book) -> None:
    payload = dump(shop.book)
    payload["version"] = 1
    with pytest.raises(RuleError, match="from migration 1"):
        restore(empty, payload)


@pytest.mark.parametrize("field", ["format", "application", "version", "tables"])
def test_a_dump_missing_a_field(shop: Shop, field: str) -> None:
    payload = dump(shop.book)
    del payload[field]
    with pytest.raises(ConfigError, match=f"a {field} and this one does not"):
        check(payload)


def test_a_dump_that_is_not_one() -> None:
    with pytest.raises(ConfigError, match="not whatever that is"):
        check("a book, honest")


def test_a_dump_from_another_format(shop: Shop) -> None:
    payload = dump(shop.book)
    payload["format"] = 99
    with pytest.raises(ConfigError, match="format 99"):
        check(payload)


def test_a_dump_from_another_application(shop: Shop) -> None:
    payload = dump(shop.book)
    payload["application"] = 1
    with pytest.raises(ConfigError, match="not from a kilodial book"):
        check(payload)


def test_a_dump_whose_tables_are_not_tables(shop: Shop) -> None:
    payload = dump(shop.book)
    payload["tables"] = ["meter"]
    with pytest.raises(ConfigError, match="keyed by table name"):
        check(payload)


def test_a_restored_book_works(shop: Shop, empty: Book, tmp_path: Path) -> None:
    restore(empty, dump(shop.book))
    restored = Shop(empty)
    assert restored.summary()["meters"] == 1
    assert restored.audit() == []
    assert restored.devices.get("Halvern/R4S").key == "Halvern/R4S"


def test_a_restore_still_checks_foreign_keys(shop: Shop, empty: Book) -> None:
    payload = dump(shop.book)
    payload["tables"]["service_point"]["rows"] = []
    with pytest.raises(Exception, match="FOREIGN KEY"):
        restore(empty, payload)
    assert empty.connection.execute("SELECT COUNT(*) FROM meter_set").fetchone()[0] == 0
