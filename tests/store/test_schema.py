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


def test_the_seventh_migration_adds_customer_requests() -> None:
    joined = " ".join(MIGRATIONS[6].statements)
    assert "CREATE TABLE complaint_request" in joined
    assert "complaint_open" in joined


def test_the_eighth_migration_adds_work_orders() -> None:
    joined = " ".join(MIGRATIONS[7].statements)
    assert "CREATE TABLE work_order" in joined
    assert "order_live" in joined


def test_the_ninth_migration_alters_rather_than_creates() -> None:
    joined = " ".join(MIGRATIONS[8].statements)
    assert "ALTER TABLE device_type ADD COLUMN demand_interval" in joined
    assert "ALTER TABLE bench_run ADD COLUMN demand_seconds" in joined
    assert "CREATE TABLE" not in joined


def test_the_tenth_migration_adds_technicians() -> None:
    joined = " ".join(MIGRATIONS[9].statements)
    assert "CREATE TABLE technician" in joined
    assert "ALTER TABLE bench_run ADD COLUMN badge" in joined


def test_the_eleventh_migration_adds_tamper_findings() -> None:
    joined = " ".join(MIGRATIONS[10].statements)
    assert "CREATE TABLE tamper_finding" in joined
    assert "tamper_open" in joined


def test_the_twelfth_migration_adds_repairs() -> None:
    joined = " ".join(MIGRATIONS[11].statements)
    assert "CREATE TABLE repair" in joined
    assert "repair_by_fault" in joined


def test_the_thirteenth_migration_links_orders_to_repairs() -> None:
    joined = " ".join(MIGRATIONS[12].statements)
    assert "ALTER TABLE work_order ADD COLUMN repair_reference" in joined


def test_the_fourteenth_migration_adds_the_event_log() -> None:
    joined = " ".join(MIGRATIONS[13].statements)
    assert "CREATE TABLE event" in joined
    assert "AUTOINCREMENT" in joined


def test_the_fifteenth_migration_adds_readings() -> None:
    joined = " ".join(MIGRATIONS[14].statements)
    assert "CREATE TABLE reading" in joined
    assert "reading_by_meter" in joined


def test_the_sixteenth_migration_adds_settled_estimates() -> None:
    joined = " ".join(MIGRATIONS[15].statements)
    assert "CREATE TABLE estimate" in joined
    assert "settled_by" in joined
