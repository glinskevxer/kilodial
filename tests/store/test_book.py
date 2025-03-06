from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest

from kilodial.errors import ConfigError
from kilodial.store.book import Book, open_book, open_migrated
from kilodial.store.schema import APPLICATION_ID, MIGRATIONS, latest_number


@pytest.fixture
def book(tmp_path: Path) -> Iterator[Book]:
    opened = open_migrated(tmp_path / "shop.sqlite3", create=True)
    yield opened
    opened.close()


def test_a_new_book_starts_empty(tmp_path: Path) -> None:
    with open_book(tmp_path / "shop.sqlite3", create=True) as fresh:
        assert fresh.version == 0
        assert fresh.pending() == [m.number for m in MIGRATIONS]


def test_migrating_runs_everything_once(tmp_path: Path) -> None:
    with open_book(tmp_path / "shop.sqlite3", create=True) as fresh:
        ran = fresh.migrate()
        assert ran == [m.number for m in MIGRATIONS]
        assert fresh.migrate() == []
        assert fresh.version == latest_number()
        assert fresh.pending() == []


def test_the_ledger_records_what_ran(book: Book) -> None:
    rows = book.applied()
    assert [r.number for r in rows] == [m.number for m in MIGRATIONS]
    assert rows[0].name == MIGRATIONS[0].name
    assert rows[0].applied_at.endswith("+00:00")


def test_a_migrated_book_checks_out(book: Book) -> None:
    assert book.check() == []
    assert str(book).endswith(f"at migration {latest_number()}")


def test_an_unmigrated_book_reports_the_gap(tmp_path: Path) -> None:
    with open_book(tmp_path / "shop.sqlite3", create=True) as fresh:
        faults = fresh.check()
        assert any("is at migration 0" in f for f in faults)


def test_opening_something_that_is_not_there(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="no book at"):
        open_book(tmp_path / "missing.sqlite3")


def test_opening_somebody_elses_database(tmp_path: Path) -> None:
    other = tmp_path / "other.sqlite3"
    conn = sqlite3.connect(str(other))
    conn.execute("PRAGMA application_id = 12345")
    conn.commit()
    conn.close()
    with pytest.raises(ConfigError, match="not a kilodial book"):
        open_book(other)


def test_the_application_id_is_stamped(book: Book) -> None:
    got = book.connection.execute("PRAGMA application_id").fetchone()[0]
    assert int(got) == APPLICATION_ID


def test_foreign_keys_are_on(book: Book) -> None:
    assert book.connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1


def insert_and_fail(book: Book) -> None:
    with book.transaction() as conn:
        conn.execute(
            "INSERT INTO meter (serial, device_key, state, acquired, owner) "
            "VALUES ('X1099', 'a/b', 'stock', '2025-01-01', 'utility')"
        )
        raise RuntimeError("no")


def test_a_transaction_rolls_back_on_a_raise(book: Book) -> None:
    with pytest.raises(RuntimeError):
        insert_and_fail(book)
    assert book.connection.execute("SELECT COUNT(*) FROM meter").fetchone()[0] == 0


def test_a_transaction_commits_on_the_way_out(book: Book) -> None:
    with book.transaction() as conn:
        conn.execute(
            "INSERT INTO meter (serial, device_key, state, acquired, owner) "
            "VALUES ('X1099', 'a/b', 'stock', '2025-01-01', 'utility')"
        )
    assert book.connection.execute("SELECT COUNT(*) FROM meter").fetchone()[0] == 1


def test_a_broken_foreign_key_is_reported(book: Book) -> None:
    book.connection.execute("PRAGMA foreign_keys = OFF")
    book.connection.execute(
        "INSERT INTO bench_point (run_reference, position, kind, amperes, volts, "
        "pf_value, pf_sense) VALUES ('nope', 1, 'FL', '30', '240', '1', 'unity')"
    )
    faults = book.check()
    assert any("break a foreign key" in f for f in faults)


def test_open_migrated_is_open_plus_migrate(tmp_path: Path) -> None:
    path = tmp_path / "shop.sqlite3"
    with open_migrated(path, create=True) as first:
        assert first.version == latest_number()
    with open_migrated(path) as again:
        assert again.check() == []
