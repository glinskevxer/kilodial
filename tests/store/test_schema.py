from __future__ import annotations

from kilodial.store.schema import MIGRATIONS, check_migrations, latest_number


def test_the_migration_list_is_structurally_sound() -> None:
    assert check_migrations() == []


def test_migrations_are_numbered_from_one_with_no_gaps() -> None:
    assert [m.number for m in MIGRATIONS] == list(range(1, len(MIGRATIONS) + 1))
    assert latest_number() == len(MIGRATIONS)


def test_every_migration_is_named() -> None:
    for m in MIGRATIONS:
        assert m.name.strip()
        assert m.statements


def test_no_statement_packs_two_together() -> None:
    for m in MIGRATIONS:
        for statement in m.statements:
            assert ";" not in statement.strip().rstrip(";")


def test_the_first_migration_creates_the_device_and_meter_tables() -> None:
    first = MIGRATIONS[0]
    joined = " ".join(first.statements)
    assert "CREATE TABLE device_type" in joined
    assert "CREATE TABLE meter" in joined


def test_points_cascade_from_their_run() -> None:
    joined = " ".join(MIGRATIONS[2].statements)
    assert "ON DELETE CASCADE" in joined
    assert "CREATE UNIQUE INDEX point_by_kind" in joined
