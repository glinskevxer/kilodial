"""The schema, as numbered migrations rather than one create script.

A shop book outlives the code that wrote it. The oldest one in this utility was
opened in 2019 and it is still the book, so every schema change since has been a
numbered step that runs forward on the file that is already there. The list
below is the whole history and it is append only: a migration that has shipped
is never edited, because somewhere there is a book that already ran it.

Each migration is one or more complete statements. They are executed one at a
time inside a single transaction with the ledger row, which matters more than it
looks: sqlite's executescript issues a COMMIT before it starts, so a migration
applied that way lands outside the transaction that records it, and a crash in
the middle leaves a book whose ledger disagrees with its tables.
"""

from __future__ import annotations

from dataclasses import dataclass

APPLICATION_ID = 0x4B44_4C31


@dataclass(frozen=True)
class Migration:
    """One numbered step, with the statements it runs."""

    number: int
    name: str
    statements: tuple[str, ...]


def _m(number: int, name: str, *statements: str) -> Migration:
    return Migration(number, name, tuple(statements))


MIGRATIONS: tuple[Migration, ...] = (
    _m(
        1,
        "device types and meters",
        """
        CREATE TABLE device_type (
            manufacturer    TEXT    NOT NULL,
            model_code      TEXT    NOT NULL,
            form_code       TEXT    NOT NULL,
            class_code      TEXT    NOT NULL,
            voltage         TEXT    NOT NULL,
            kh              TEXT    NOT NULL,
            technology      TEXT    NOT NULL,
            register_ratio  TEXT,
            demand_capable  INTEGER NOT NULL DEFAULT 0,
            introduced      TEXT    NOT NULL,
            retired         TEXT,
            PRIMARY KEY (manufacturer, model_code)
        )
        """,
        """
        CREATE TABLE meter (
            serial      TEXT PRIMARY KEY,
            device_key  TEXT NOT NULL,
            state       TEXT NOT NULL,
            acquired    TEXT NOT NULL,
            owner       TEXT NOT NULL,
            seal        TEXT,
            retired_on  TEXT
        )
        """,
        "CREATE INDEX meter_by_device ON meter (device_key)",
        "CREATE INDEX meter_by_state ON meter (state)",
    ),
    _m(
        2,
        "benches and reference standards",
        """
        CREATE TABLE reference_standard (
            serial           TEXT PRIMARY KEY,
            maker            TEXT NOT NULL,
            model_code       TEXT NOT NULL,
            certificate      TEXT NOT NULL,
            certified_on     TEXT NOT NULL,
            certificate_due  TEXT NOT NULL,
            uncertainty      TEXT NOT NULL,
            traceable_to     TEXT NOT NULL
        )
        """,
        """
        CREATE TABLE bench (
            code             TEXT PRIMARY KEY,
            name             TEXT NOT NULL,
            positions        INTEGER NOT NULL,
            standard_serial  TEXT NOT NULL,
            max_amperes      TEXT NOT NULL,
            max_volts        TEXT NOT NULL,
            polyphase        INTEGER NOT NULL DEFAULT 0,
            installed        TEXT NOT NULL,
            removed          TEXT
        )
        """,
        "CREATE INDEX bench_by_standard ON bench (standard_serial)",
    ),
    _m(
        3,
        "bench runs and their points",
        """
        CREATE TABLE bench_run (
            reference        TEXT PRIMARY KEY,
            meter_serial     TEXT NOT NULL,
            bench_code       TEXT NOT NULL,
            standard_serial  TEXT NOT NULL,
            kind             TEXT NOT NULL,
            tested_on        TEXT NOT NULL,
            technician       TEXT NOT NULL,
            note             TEXT
        )
        """,
        """
        CREATE TABLE bench_point (
            run_reference  TEXT    NOT NULL,
            position       INTEGER NOT NULL,
            kind           TEXT    NOT NULL,
            amperes        TEXT    NOT NULL,
            volts          TEXT    NOT NULL,
            pf_value       TEXT    NOT NULL,
            pf_sense       TEXT    NOT NULL,
            registration   TEXT,
            crept          INTEGER,
            PRIMARY KEY (run_reference, position),
            FOREIGN KEY (run_reference) REFERENCES bench_run (reference) ON DELETE CASCADE
        )
        """,
        "CREATE INDEX run_by_meter ON bench_run (meter_serial, tested_on)",
        "CREATE INDEX run_by_day ON bench_run (tested_on)",
        "CREATE UNIQUE INDEX point_by_kind ON bench_point (run_reference, kind)",
    ),
    _m(
        4,
        "instrument transformers and installations",
        """
        CREATE TABLE instrument_transformer (
            serial         TEXT PRIMARY KEY,
            kind           TEXT NOT NULL,
            maker          TEXT NOT NULL,
            marked_ratio   TEXT NOT NULL,
            accuracy       TEXT NOT NULL,
            rcf            TEXT NOT NULL,
            phase_minutes  TEXT NOT NULL,
            burden         TEXT NOT NULL,
            tested_on      TEXT NOT NULL
        )
        """,
        """
        CREATE TABLE service_point (
            code          TEXT PRIMARY KEY,
            account       TEXT NOT NULL,
            address       TEXT NOT NULL,
            service       TEXT NOT NULL,
            voltage       TEXT NOT NULL,
            rate_code     TEXT NOT NULL,
            energised     TEXT NOT NULL,
            disconnected  TEXT
        )
        """,
        """
        CREATE TABLE meter_set (
            point_code             TEXT NOT NULL,
            meter_serial           TEXT NOT NULL,
            ct_serial              TEXT,
            vt_serial              TEXT,
            register_multiplier    TEXT NOT NULL,
            programmed_multiplier  TEXT NOT NULL,
            set_on                 TEXT NOT NULL,
            removed_on             TEXT,
            PRIMARY KEY (point_code, meter_serial, set_on),
            FOREIGN KEY (point_code) REFERENCES service_point (code)
        )
        """,
        "CREATE INDEX transformer_by_kind ON instrument_transformer (kind)",
        "CREATE INDEX set_by_meter ON meter_set (meter_serial, set_on)",
        "CREATE INDEX point_by_account ON service_point (account)",
    ),
    _m(
        5,
        "sampling groups and their test plans",
        """
        CREATE TABLE sample_group (
            code           TEXT PRIMARY KEY,
            name           TEXT NOT NULL,
            device_keys    TEXT NOT NULL DEFAULT '',
            class_code     TEXT,
            technology     TEXT,
            form_codes     TEXT NOT NULL DEFAULT '',
            acquired_from  TEXT,
            acquired_to    TEXT
        )
        """,
        """
        CREATE TABLE test_plan (
            group_code       TEXT NOT NULL,
            decided_on       TEXT NOT NULL,
            interval_months  INTEGER NOT NULL,
            population       INTEGER NOT NULL,
            tested           INTEGER NOT NULL,
            mean             TEXT NOT NULL,
            deviation        TEXT NOT NULL,
            failures         INTEGER NOT NULL,
            passed           INTEGER NOT NULL,
            note             TEXT,
            PRIMARY KEY (group_code, decided_on),
            FOREIGN KEY (group_code) REFERENCES sample_group (code) ON DELETE CASCADE
        )
        """,
        "CREATE INDEX plan_by_group ON test_plan (group_code, decided_on)",
    ),
    _m(
        6,
        "billed history",
        """
        CREATE TABLE billed_month (
            point_code  TEXT NOT NULL,
            first_day   TEXT NOT NULL,
            last_day    TEXT NOT NULL,
            amount      INTEGER NOT NULL,
            kwh         TEXT,
            PRIMARY KEY (point_code, first_day),
            FOREIGN KEY (point_code) REFERENCES service_point (code) ON DELETE CASCADE
        )
        """,
        "CREATE INDEX billed_by_point ON billed_month (point_code, first_day)",
    ),
    _m(
        7,
        "customer requested tests",
        """
        CREATE TABLE complaint_request (
            reference      TEXT PRIMARY KEY,
            point_code     TEXT NOT NULL,
            requested_on   TEXT NOT NULL,
            requested_by   TEXT NOT NULL,
            reason         TEXT NOT NULL,
            note           TEXT,
            run_reference  TEXT,
            charge         TEXT,
            fee            INTEGER,
            closed_on      TEXT,
            FOREIGN KEY (point_code) REFERENCES service_point (code)
        )
        """,
        "CREATE INDEX complaint_by_point ON complaint_request (point_code, requested_on)",
        "CREATE INDEX complaint_open ON complaint_request (closed_on)",
    ),
    _m(
        8,
        "shop work orders",
        """
        CREATE TABLE work_order (
            reference      TEXT PRIMARY KEY,
            kind           TEXT NOT NULL,
            meter_serial   TEXT NOT NULL,
            point_code     TEXT,
            priority       TEXT NOT NULL,
            raised_on      TEXT NOT NULL,
            state          TEXT NOT NULL,
            assigned_to    TEXT,
            closed_on      TEXT,
            run_reference  TEXT,
            disposition    TEXT,
            note           TEXT
        )
        """,
        "CREATE INDEX order_by_meter ON work_order (meter_serial, raised_on)",
        "CREATE INDEX order_live ON work_order (state, raised_on)",
    ),
    _m(
        9,
        "demand programming and interval checks",
        "ALTER TABLE device_type ADD COLUMN demand_interval TEXT",
        "ALTER TABLE bench_run ADD COLUMN demand_seconds TEXT",
        "CREATE INDEX device_by_demand ON device_type (demand_capable)",
    ),
    _m(
        10,
        "technicians and who signed a run",
        """
        CREATE TABLE technician (
            badge            TEXT PRIMARY KEY,
            name             TEXT NOT NULL,
            grade            TEXT NOT NULL,
            certified_on     TEXT NOT NULL,
            certificate_due  TEXT NOT NULL,
            note             TEXT
        )
        """,
        "ALTER TABLE bench_run ADD COLUMN badge TEXT",
        "CREATE INDEX run_by_badge ON bench_run (badge)",
        "CREATE INDEX technician_by_grade ON technician (grade)",
    ),
    _m(
        11,
        "tamper findings",
        """
        CREATE TABLE tamper_finding (
            reference   TEXT PRIMARY KEY,
            point_code  TEXT NOT NULL,
            kind        TEXT NOT NULL,
            standing    TEXT NOT NULL,
            found_on    TEXT NOT NULL,
            found_by    TEXT NOT NULL,
            settled_on  TEXT,
            since       TEXT,
            evidence    TEXT,
            FOREIGN KEY (point_code) REFERENCES service_point (code)
        )
        """,
        "CREATE INDEX tamper_by_point ON tamper_finding (point_code, found_on)",
        "CREATE INDEX tamper_open ON tamper_finding (standing)",
    ),
)


def latest_number() -> int:
    """The number the book is brought up to."""
    return MIGRATIONS[-1].number


def check_migrations() -> list[str]:
    """Everything structurally wrong with the migration list."""
    faults: list[str] = []
    seen: set[int] = set()
    for index, migration in enumerate(MIGRATIONS, start=1):
        if migration.number != index:
            faults.append(f"migration {migration.number} sits at position {index}")
        if migration.number in seen:
            faults.append(f"migration {migration.number} appears twice")
        seen.add(migration.number)
        if not migration.name.strip():
            faults.append(f"migration {migration.number} has no name")
        if not migration.statements:
            faults.append(f"migration {migration.number} runs nothing")
        for statement in migration.statements:
            if not statement.strip():
                faults.append(f"migration {migration.number} has a blank statement")
            if ";" in statement.strip().rstrip(";"):
                faults.append(
                    f"migration {migration.number} packs more than one statement "
                    "into a single string"
                )
    return faults


__all__ = ["APPLICATION_ID", "MIGRATIONS", "Migration", "check_migrations", "latest_number"]
