"""Counting every table in one query rather than fifteen.

``Shop.summary`` asked each repository for its own count, which meant fifteen
round trips into sqlite for a number that goes on one screen. That was fine
until the shop report started calling it and the doctor started calling the shop
report.

One UNION ALL does the same work in one statement. The table names come from a
fixed list rather than off sqlite_master, because the labels are the shop's
words and not the table names: ``sample_group`` is a group and ``bench_run`` is
a run, and a summary that says sample_group is a summary written for whoever
wrote the schema.
"""

from __future__ import annotations

import sqlite3

# The label the shop uses, against the table it counts. Order is the order the
# summary prints in, which runs roughly from the catalogue outwards.
TABLES: tuple[tuple[str, str], ...] = (
    ("device types", "device_type"),
    ("meters", "meter"),
    ("standards", "reference_standard"),
    ("benches", "bench"),
    ("runs", "bench_run"),
    ("transformers", "instrument_transformer"),
    ("service points", "service_point"),
    ("meter sets", "meter_set"),
    ("groups", "sample_group"),
    ("sample decisions", "test_plan"),
    ("billed months", "billed_month"),
    ("complaints", "complaint_request"),
    ("work orders", "work_order"),
    ("technicians", "technician"),
    ("tamper findings", "tamper_finding"),
    ("repairs", "repair"),
    ("events", "event"),
    ("readings", "reading"),
    ("estimates", "estimate"),
)


# Tables the summary does not count, with why. A child table's count is the
# parent's count times however many points a run happened to have, which is not
# a number anybody wants on a summary screen.
CHILDREN: dict[str, str] = {
    "bench_point": "the points of a run are counted with the run",
    "schema_migration": "the ledger is the book's own bookkeeping",
}


def statement() -> str:
    """The one query that counts everything."""
    parts = [f"SELECT '{label}' AS label, COUNT(*) AS rows FROM {table}" for label, table in TABLES]
    return " UNION ALL ".join(parts)


def counts(connection: sqlite3.Connection) -> dict[str, int]:
    """Every table's row count, in the order the labels are listed."""
    rows = connection.execute(statement()).fetchall()
    found = {str(r[0]): int(r[1]) for r in rows}
    return {label: found.get(label, 0) for label, _ in TABLES}


def labels() -> list[str]:
    """The labels a summary prints, in order."""
    return [label for label, _ in TABLES]


def tables() -> list[str]:
    """The tables a summary counts."""
    return [table for _, table in TABLES]


__all__ = ["CHILDREN", "TABLES", "counts", "labels", "statement", "tables"]
