"""Storing repair records, and counting them by fault.

The counting is the point. One repair is a job; a hundred repairs is the only
evidence a shop has about which types are worth stocking, and the fault
breakdown by device type is the report that decides the next purchase order.

Repairs hang off the meter rather than off the work order, because a meter gets
repaired without an order more often than anyone would like and the record still
has to exist.
"""

from __future__ import annotations

import sqlite3
from decimal import Decimal

from kilodial.errors import DuplicateError, RuleError
from kilodial.model.repair import Fault, Repair
from kilodial.store.base import has_row, member_of, one_row, or_none, upper
from kilodial.store.meters import MeterRepository
from kilodial.units.money import Money
from kilodial.units.span import parse_date

COLUMNS = (
    "reference, meter_serial, fault, repaired_on, by_whom, hours, parts, replacement_cost, note"
)


class RepairRepository:
    """Repair records on one book."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._conn = connection
        self._meters = MeterRepository(connection)

    def add(self, repair: Repair) -> Repair:
        """Record a repair against a meter that is on the book."""
        if self.exists(repair.reference):
            raise DuplicateError("repair", repair.reference)
        if not self._meters.exists(repair.meter_serial):
            raise RuleError(
                f"repair {repair.reference} names meter {repair.meter_serial}, "
                "which is not on the book"
            )
        self._conn.execute(
            f"INSERT INTO repair ({COLUMNS}) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            _row(repair),
        )
        return repair

    def exists(self, reference: str) -> bool:
        return has_row(self._conn, "repair", "reference", upper(reference))

    def get(self, reference: str) -> Repair:
        return _read(
            one_row(self._conn, COLUMNS, "repair", "reference", upper(reference), "repair")
        )

    def find(self, reference: str | None) -> Repair | None:
        """Look one up, handing back nothing rather than raising."""
        return or_none(self.get, reference)

    def all(self) -> list[Repair]:
        rows = self._conn.execute(
            f"SELECT {COLUMNS} FROM repair ORDER BY repaired_on, reference"
        ).fetchall()
        return [_read(r) for r in rows]

    def for_meter(self, serial: str) -> list[Repair]:
        rows = self._conn.execute(
            f"SELECT {COLUMNS} FROM repair WHERE meter_serial = ? ORDER BY repaired_on, reference",
            (upper(serial),),
        ).fetchall()
        return [_read(r) for r in rows]

    def by_fault(self, fault: Fault) -> list[Repair]:
        rows = self._conn.execute(
            f"SELECT {COLUMNS} FROM repair WHERE fault = ? ORDER BY repaired_on, reference",
            (fault.name,),
        ).fetchall()
        return [_read(r) for r in rows]

    def between(self, first: object, last: object) -> list[Repair]:
        start = parse_date(first)
        end = parse_date(last)
        if end < start:
            raise RuleError("a repair window cannot end before it starts")
        rows = self._conn.execute(
            f"SELECT {COLUMNS} FROM repair WHERE repaired_on BETWEEN ? AND ? "
            "ORDER BY repaired_on, reference",
            (start.isoformat(), end.isoformat()),
        ).fetchall()
        return [_read(r) for r in rows]

    def counts_by_fault(self) -> dict[Fault, int]:
        rows = self._conn.execute("SELECT fault, COUNT(*) FROM repair GROUP BY fault").fetchall()
        found = {str(r[0]): int(r[1]) for r in rows}
        return {fault: found.get(fault.name, 0) for fault in Fault}

    def counts_for_device(self, device_key: str) -> dict[Fault, int]:
        """The fault breakdown for one device type, which is the buying question."""
        serials = {m.serial for m in self._meters.by_device(device_key)}
        found = dict.fromkeys(Fault, 0)
        for repair in self.all():
            if repair.meter_serial in serials:
                found[repair.fault] += 1
        return found

    def spent_between(self, first: object, last: object) -> Money:
        """What the shop spent on repairs over a window."""
        total = Money.zero()
        for repair in self.between(first, last):
            total = total + repair.cost
        return total

    def not_worth_it(self) -> list[Repair]:
        """Repairs that cost more than the tariff share of a new meter."""
        return [r for r in self.all() if r.fault.is_a_fault and not r.was_worth_it]

    def count(self) -> int:
        return int(self._conn.execute("SELECT COUNT(*) FROM repair").fetchone()[0])


def _row(repair: Repair) -> tuple[object, ...]:
    return (
        repair.reference,
        repair.meter_serial,
        repair.fault.name,
        repair.repaired_on.isoformat(),
        repair.by,
        str(repair.hours),
        repair.parts.cents,
        repair.replacement_cost.cents,
        repair.note,
    )


def _read(row: tuple[object, ...]) -> Repair:
    return Repair(
        reference=str(row[0]),
        meter_serial=str(row[1]),
        fault=member_of(Fault, row[2], "repair fault", field="name"),
        repaired_on=parse_date(str(row[3])),
        by=str(row[4]),
        hours=Decimal(str(row[5])),
        parts=Money.from_cents(int(str(row[6]))),
        replacement_cost=Money.from_cents(int(str(row[7]))),
        note=None if row[8] is None else str(row[8]),
    )


__all__ = ["COLUMNS", "RepairRepository"]
