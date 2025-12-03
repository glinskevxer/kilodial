"""Storing work orders.

The queries here are the shop's day: what is live, what is late, and what is on
one meter. Everything else is a report.

An order is not allowed to name a meter that is not on the book, and that check
is here rather than as a foreign key for the same reason it is on meters: a
receiving order gets raised before the asset record exists, and a hard
constraint would make the receiving clerk's job impossible. Every other kind is
checked.
"""

from __future__ import annotations

import sqlite3

from kilodial.errors import DuplicateError, NotFoundError, RuleError
from kilodial.orders.order import (
    Disposition,
    OrderKind,
    OrderState,
    Priority,
    WorkOrder,
)
from kilodial.store.base import member_of
from kilodial.store.meters import MeterRepository
from kilodial.units.span import parse_date

COLUMNS = (
    "reference, kind, meter_serial, point_code, priority, raised_on, state, "
    "assigned_to, closed_on, run_reference, disposition, note, repair_reference"
)


class OrderRepository:
    """Work orders on one book."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._conn = connection
        self._meters = MeterRepository(connection)

    def add(self, order: WorkOrder) -> WorkOrder:
        """Put a new order on the book."""
        if self.exists(order.reference):
            raise DuplicateError("work order", order.reference)
        if order.kind is not OrderKind.RECEIVE and not self._meters.exists(order.meter_serial):
            raise RuleError(
                f"work order {order.reference} names meter {order.meter_serial}, "
                "which is not on the book"
            )
        self._conn.execute(
            f"INSERT INTO work_order ({COLUMNS}) VALUES ({', '.join('?' * 13)})",
            _row(order),
        )
        return order

    def save(self, order: WorkOrder) -> WorkOrder:
        """Write an order that is already on the book back over itself."""
        if not self.exists(order.reference):
            raise NotFoundError("work order", order.reference)
        row = _row(order)
        self._conn.execute(
            "UPDATE work_order SET kind = ?, meter_serial = ?, point_code = ?, "
            "priority = ?, raised_on = ?, state = ?, assigned_to = ?, closed_on = ?, "
            "run_reference = ?, disposition = ?, note = ?, repair_reference = ? "
            "WHERE reference = ?",
            (*row[1:], row[0]),
        )
        return order

    def exists(self, reference: str) -> bool:
        found = self._conn.execute(
            "SELECT 1 FROM work_order WHERE reference = ?", (reference.strip().upper(),)
        ).fetchone()
        return found is not None

    def get(self, reference: str) -> WorkOrder:
        wanted = reference.strip().upper()
        row = self._conn.execute(
            f"SELECT {COLUMNS} FROM work_order WHERE reference = ?", (wanted,)
        ).fetchone()
        if row is None:
            raise NotFoundError("work order", wanted)
        return _read(row)

    def all(self) -> list[WorkOrder]:
        rows = self._conn.execute(
            f"SELECT {COLUMNS} FROM work_order ORDER BY raised_on, reference"
        ).fetchall()
        return [_read(r) for r in rows]

    def live(self) -> list[WorkOrder]:
        """Everything still to be done, oldest first."""
        rows = self._conn.execute(
            f"SELECT {COLUMNS} FROM work_order WHERE state IN ('OPEN', 'ASSIGNED') "
            "ORDER BY raised_on, reference"
        ).fetchall()
        return [_read(r) for r in rows]

    def late_on(self, day: object) -> list[WorkOrder]:
        """Live orders past their due date, latest due date last."""
        when = parse_date(day)
        found = [o for o in self.live() if o.is_late_on(when)]
        return sorted(found, key=lambda o: (o.due_on, o.reference))

    def for_meter(self, serial: str) -> list[WorkOrder]:
        rows = self._conn.execute(
            f"SELECT {COLUMNS} FROM work_order WHERE meter_serial = ? "
            "ORDER BY raised_on, reference",
            (serial.strip().upper(),),
        ).fetchall()
        return [_read(r) for r in rows]

    def by_kind(self, kind: OrderKind) -> list[WorkOrder]:
        rows = self._conn.execute(
            f"SELECT {COLUMNS} FROM work_order WHERE kind = ? ORDER BY raised_on, reference",
            (kind.name,),
        ).fetchall()
        return [_read(r) for r in rows]

    def assigned_to(self, technician: str) -> list[WorkOrder]:
        rows = self._conn.execute(
            f"SELECT {COLUMNS} FROM work_order WHERE assigned_to = ? ORDER BY raised_on, reference",
            (" ".join(technician.split()),),
        ).fetchall()
        return [_read(r) for r in rows]

    def counts_by_state(self) -> dict[OrderState, int]:
        rows = self._conn.execute(
            "SELECT state, COUNT(*) FROM work_order GROUP BY state"
        ).fetchall()
        found = {str(r[0]): int(r[1]) for r in rows}
        return {state: found.get(state.name, 0) for state in OrderState}

    def count(self) -> int:
        return int(self._conn.execute("SELECT COUNT(*) FROM work_order").fetchone()[0])


def _row(order: WorkOrder) -> tuple[object, ...]:
    return (
        order.reference,
        order.kind.name,
        order.meter_serial,
        order.point_code,
        order.priority.name,
        order.raised_on.isoformat(),
        order.state.name,
        order.assigned_to,
        None if order.closed_on is None else order.closed_on.isoformat(),
        order.run_reference,
        None if order.disposition is None else order.disposition.name,
        order.note,
        order.repair_reference,
    )


def _read(row: tuple[object, ...]) -> WorkOrder:
    return WorkOrder(
        reference=str(row[0]),
        kind=member_of(OrderKind, row[1], "work order kind", field="name"),
        meter_serial=str(row[2]),
        point_code=None if row[3] is None else str(row[3]),
        priority=member_of(Priority, row[4], "work order priority", field="name"),
        raised_on=parse_date(str(row[5])),
        state=member_of(OrderState, row[6], "work order state", field="name"),
        assigned_to=None if row[7] is None else str(row[7]),
        closed_on=None if row[8] is None else parse_date(str(row[8])),
        run_reference=None if row[9] is None else str(row[9]),
        disposition=None
        if row[10] is None
        else member_of(Disposition, row[10], "repair disposition", field="name"),
        note=None if row[11] is None else str(row[11]),
        repair_reference=None if len(row) < 13 or row[12] is None else str(row[12]),
    )


__all__ = ["COLUMNS", "OrderRepository"]
