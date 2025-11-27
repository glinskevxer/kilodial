-- kilodial schema, built from the migrations. Do not edit by hand.
-- Rebuild with: python -m kilodial.tools.schema_dump
-- Migrations applied: 12 (latest 12)

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
        );

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
        );

CREATE TABLE bench_run (
            reference        TEXT PRIMARY KEY,
            meter_serial     TEXT NOT NULL,
            bench_code       TEXT NOT NULL,
            standard_serial  TEXT NOT NULL,
            kind             TEXT NOT NULL,
            tested_on        TEXT NOT NULL,
            technician       TEXT NOT NULL,
            note             TEXT
        , demand_seconds TEXT, badge TEXT);

CREATE TABLE billed_month (
            point_code  TEXT NOT NULL,
            first_day   TEXT NOT NULL,
            last_day    TEXT NOT NULL,
            amount      INTEGER NOT NULL,
            kwh         TEXT,
            PRIMARY KEY (point_code, first_day),
            FOREIGN KEY (point_code) REFERENCES service_point (code) ON DELETE CASCADE
        );

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
        );

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
            retired         TEXT, demand_interval TEXT,
            PRIMARY KEY (manufacturer, model_code)
        );

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
        );

CREATE TABLE meter (
            serial      TEXT PRIMARY KEY,
            device_key  TEXT NOT NULL,
            state       TEXT NOT NULL,
            acquired    TEXT NOT NULL,
            owner       TEXT NOT NULL,
            seal        TEXT,
            retired_on  TEXT
        );

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
        );

CREATE TABLE reference_standard (
            serial           TEXT PRIMARY KEY,
            maker            TEXT NOT NULL,
            model_code       TEXT NOT NULL,
            certificate      TEXT NOT NULL,
            certified_on     TEXT NOT NULL,
            certificate_due  TEXT NOT NULL,
            uncertainty      TEXT NOT NULL,
            traceable_to     TEXT NOT NULL
        );

CREATE TABLE repair (
            reference         TEXT PRIMARY KEY,
            meter_serial      TEXT NOT NULL,
            fault             TEXT NOT NULL,
            repaired_on       TEXT NOT NULL,
            by_whom           TEXT NOT NULL,
            hours             TEXT NOT NULL,
            parts             INTEGER NOT NULL,
            replacement_cost  INTEGER NOT NULL,
            note              TEXT
        );

CREATE TABLE sample_group (
            code           TEXT PRIMARY KEY,
            name           TEXT NOT NULL,
            device_keys    TEXT NOT NULL DEFAULT '',
            class_code     TEXT,
            technology     TEXT,
            form_codes     TEXT NOT NULL DEFAULT '',
            acquired_from  TEXT,
            acquired_to    TEXT
        );

CREATE TABLE schema_migration (
    number      INTEGER PRIMARY KEY,
    name        TEXT NOT NULL,
    applied_at  TEXT NOT NULL
);

CREATE TABLE service_point (
            code          TEXT PRIMARY KEY,
            account       TEXT NOT NULL,
            address       TEXT NOT NULL,
            service       TEXT NOT NULL,
            voltage       TEXT NOT NULL,
            rate_code     TEXT NOT NULL,
            energised     TEXT NOT NULL,
            disconnected  TEXT
        );

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
        );

CREATE TABLE technician (
            badge            TEXT PRIMARY KEY,
            name             TEXT NOT NULL,
            grade            TEXT NOT NULL,
            certified_on     TEXT NOT NULL,
            certificate_due  TEXT NOT NULL,
            note             TEXT
        );

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
        );

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
        );

CREATE INDEX bench_by_standard ON bench (standard_serial);

CREATE INDEX billed_by_point ON billed_month (point_code, first_day);

CREATE INDEX complaint_by_point ON complaint_request (point_code, requested_on);

CREATE INDEX complaint_open ON complaint_request (closed_on);

CREATE INDEX device_by_demand ON device_type (demand_capable);

CREATE INDEX meter_by_device ON meter (device_key);

CREATE INDEX meter_by_state ON meter (state);

CREATE INDEX order_by_meter ON work_order (meter_serial, raised_on);

CREATE INDEX order_live ON work_order (state, raised_on);

CREATE INDEX plan_by_group ON test_plan (group_code, decided_on);

CREATE INDEX point_by_account ON service_point (account);

CREATE UNIQUE INDEX point_by_kind ON bench_point (run_reference, kind);

CREATE INDEX repair_by_fault ON repair (fault);

CREATE INDEX repair_by_meter ON repair (meter_serial, repaired_on);

CREATE INDEX run_by_badge ON bench_run (badge);

CREATE INDEX run_by_day ON bench_run (tested_on);

CREATE INDEX run_by_meter ON bench_run (meter_serial, tested_on);

CREATE INDEX set_by_meter ON meter_set (meter_serial, set_on);

CREATE INDEX tamper_by_point ON tamper_finding (point_code, found_on);

CREATE INDEX tamper_open ON tamper_finding (standing);

CREATE INDEX technician_by_grade ON technician (grade);

CREATE INDEX transformer_by_kind ON instrument_transformer (kind);
