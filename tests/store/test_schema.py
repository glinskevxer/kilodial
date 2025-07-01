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


def test_the_fourth_migration_adds_transformers_and_installations() -> None:
    joined = " ".join(MIGRATIONS[3].statements)
    assert "CREATE TABLE instrument_transformer" in joined
    assert "CREATE TABLE service_point" in joined
    assert "CREATE TABLE meter_set" in joined


def test_a_meter_set_hangs_off_its_service_point() -> None:
    joined = " ".join(MIGRATIONS[3].statements)
    assert "REFERENCES service_point (code)" in joined


def test_the_fifth_migration_adds_groups_and_plans() -> None:
    joined = " ".join(MIGRATIONS[4].statements)
    assert "CREATE TABLE sample_group" in joined
    assert "CREATE TABLE test_plan" in joined
    assert "ON DELETE CASCADE" in joined


def test_the_sixth_migration_adds_the_billed_history() -> None:
    joined = " ".join(MIGRATIONS[5].statements)
    assert "CREATE TABLE billed_month" in joined
    assert "amount      INTEGER NOT NULL" in joined
