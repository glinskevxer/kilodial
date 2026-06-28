"""Migrate a book forward from every earlier point and check nothing is lost.

The migration list is append only and the reason is that somewhere there is a
book that has already run part of it. That claim is only worth anything if it is
tested, and the way to test it is to build a book at each earlier version, put
rows in it, and run the rest of the list over the top.

It is the one test in this suite that exercises the migrations as migrations
rather than as a way of getting a table to write to.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from kilodial.store.book import LEDGER, Book, connect, open_book
from kilodial.store.schema import APPLICATION_ID, MIGRATIONS, latest_number


def book_at(path: Path, version: int) -> sqlite3.Connection:
    """A book with only the first ``version`` migrations run on it."""
    conn = connect(path)
    conn.execute(LEDGER)
    conn.execute(f"PRAGMA application_id = {APPLICATION_ID}")
    for migration in MIGRATIONS[:version]:
        for statement in migration.statements:
            conn.execute(statement)
        conn.execute(
            "INSERT INTO schema_migration (number, name, applied_at) VALUES (?, ?, ?)",
            (migration.number, migration.name, "2019-01-01T00:00:00+00:00"),
        )
    conn.commit()
    return conn


@pytest.fixture
def where(tmp_path: Path) -> Path:
    return tmp_path


@pytest.mark.parametrize("version", range(1, len(MIGRATIONS)))
def test_a_book_at_an_earlier_migration_comes_all_the_way_forward(
    where: Path, version: int
) -> None:
    path = where / f"at{version}.sqlite3"
    conn = book_at(path, version)
    conn.close()
    with open_book(path) as book:
        assert book.version == version
        ran = book.migrate()
        assert ran == [m.number for m in MIGRATIONS[version:]]
        assert book.version == latest_number()
        assert book.check() == []


def test_rows_written_before_an_upgrade_survive_it(where: Path) -> None:
    path = where / "old.sqlite3"
    conn = book_at(path, 1)
    conn.execute(
        "INSERT INTO meter (serial, device_key, state, acquired, owner) "
        "VALUES ('84-119302', 'Halvern/R4S', 'stock', '2015-01-01', 'utility')"
    )
    conn.commit()
    conn.close()
    with open_book(path) as book:
        book.migrate()
        row = book.connection.execute(
            "SELECT serial, owner FROM meter WHERE serial = '84-119302'"
        ).fetchone()
        assert row == ("84-119302", "utility")


def test_a_column_added_later_is_null_on_an_old_row(where: Path) -> None:
    path = where / "old.sqlite3"
    conn = book_at(path, 1)
    conn.execute(
        "INSERT INTO device_type (manufacturer, model_code, form_code, class_code, "
        "voltage, kh, technology, introduced) VALUES ('Halvern', 'R4S', '2S', "
        "'CL200', '240', '7.2', 'induction', '2004-05-01')"
    )
    conn.commit()
    conn.close()
    with open_book(path) as book:
        book.migrate()
        row = book.connection.execute(
            "SELECT demand_interval FROM device_type WHERE model_code = 'R4S'"
        ).fetchone()
        assert row[0] is None


def test_the_ledger_records_every_step_of_an_upgrade(where: Path) -> None:
    path = where / "old.sqlite3"
    book_at(path, 3).close()
    with open_book(path) as book:
        book.migrate()
        applied = book.applied()
        assert [a.number for a in applied] == [m.number for m in MIGRATIONS]
        assert applied[0].applied_at == "2019-01-01T00:00:00+00:00"
        assert applied[-1].applied_at != applied[0].applied_at


def test_an_upgrade_is_idempotent(where: Path) -> None:
    path = where / "old.sqlite3"
    book_at(path, 5).close()
    with open_book(path) as book:
        first = book.migrate()
        assert book.migrate() == []
        assert len(first) == len(MIGRATIONS) - 5


def test_a_book_already_up_to_date_runs_nothing(where: Path) -> None:
    path = where / "current.sqlite3"
    book_at(path, len(MIGRATIONS)).close()
    with open_book(path) as book:
        assert book.pending() == []
        assert book.migrate() == []


def test_every_migration_can_be_the_last_one_run(where: Path) -> None:
    for version in range(1, len(MIGRATIONS) + 1):
        path = where / f"stop{version}.sqlite3"
        conn = book_at(path, version)
        found = conn.execute("SELECT COUNT(*) FROM sqlite_master WHERE type = 'table'").fetchone()[
            0
        ]
        conn.close()
        assert found > 0
        with open_book(path) as book:
            assert book.version == version


def test_a_partly_migrated_book_reports_the_gap(where: Path) -> None:
    path = where / "half.sqlite3"
    book_at(path, 2).close()
    with open_book(path) as book:
        faults = book.check()
        assert any("is at migration 2" in f for f in faults)


def test_the_first_migration_alone_is_a_usable_book(where: Path) -> None:
    path = where / "first.sqlite3"
    conn = book_at(path, 1)
    tables = {
        str(r[0])
        for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
    }
    conn.close()
    assert "device_type" in tables
    assert "meter" in tables
    assert "bench_run" not in tables


def test_the_upgraded_book_is_a_shop(where: Path) -> None:
    from kilodial.store.shop import Shop

    path = where / "old.sqlite3"
    book_at(path, 4).close()
    with open_book(path) as opened:
        opened.migrate()
        shop = Shop(opened)
        assert shop.summary()["meters"] == 0
        assert shop.audit() == []


def test_the_book_fixture_type_is_what_it_says(where: Path) -> None:
    path = where / "typed.sqlite3"
    book_at(path, 1).close()
    with open_book(path) as book:
        assert isinstance(book, Book)
