"""Storing and moving meters.

The repository is where a state change becomes durable, and it is deliberately
the only place that happens. The model knows which moves are legal and the
repository knows how to write one down, and keeping those apart means a caller
cannot get a meter into the field by writing a row.

There is no foreign key from a meter to its device type in the schema. That is
not an oversight to be tidied away: the shop takes delivery of meters before the
type is on the book often enough that a hard constraint would stop the receiving
clerk working. The check lives here instead, where it can be relaxed on purpose.
"""

from __future__ import annotations

import sqlite3

from kilodial.errors import DuplicateError, NotFoundError, RuleError
from kilodial.model.meter import BENCHABLE, Meter, MeterState, normalise_serial
from kilodial.store.base import has_row, one_row, or_none
from kilodial.store.codec import meter_row, read_meter
from kilodial.store.devices import DeviceRepository

COLUMNS = "serial, device_key, state, acquired, owner, seal, retired_on"


class MeterRepository:
    """Meters on one book."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._conn = connection
        self._devices = DeviceRepository(connection)

    def add(self, meter: Meter, *, require_device: bool = True) -> Meter:
        """Book a meter in.

        ``require_device`` is on by default and off for the receiving path,
        which is allowed to take delivery of a type the shop has not catalogued
        yet.
        """
        if self.exists(meter.serial):
            raise DuplicateError("meter", meter.serial)
        if require_device and not self._devices.exists(meter.device_key):
            raise RuleError(
                f"meter {meter.serial} names device type {meter.device_key}, "
                "which is not on the book"
            )
        self._conn.execute(
            f"INSERT INTO meter ({COLUMNS}) VALUES (?, ?, ?, ?, ?, ?, ?)",
            meter_row(meter),
        )
        return meter

    def save(self, meter: Meter) -> Meter:
        """Write a meter that is already on the book back over itself."""
        if not self.exists(meter.serial):
            raise NotFoundError("meter", meter.serial)
        row = meter_row(meter)
        self._conn.execute(
            "UPDATE meter SET device_key = ?, state = ?, acquired = ?, owner = ?, "
            "seal = ?, retired_on = ? WHERE serial = ?",
            (*row[1:], row[0]),
        )
        return meter

    def exists(self, serial: object) -> bool:
        return has_row(self._conn, "meter", "serial", normalise_serial(serial))

    def get(self, serial: object) -> Meter:
        return read_meter(
            one_row(
                self._conn,
                COLUMNS,
                "meter",
                "serial",
                normalise_serial(serial),
                "meter",
            )
        )

    def find(self, serial: object) -> Meter | None:
        """The same lookup, handing back nothing rather than raising."""
        return or_none(self.get, str(serial))

    def move(self, serial: object, state: MeterState, *, on: object = None) -> Meter:
        """Move a meter and write the move down, or refuse it."""
        moved = self.get(serial).moved_to(state, on=on)
        return self.save(moved)

    def reseal(self, serial: object, seal: object) -> Meter:
        return self.save(self.get(serial).resealed(seal))

    def all(self) -> list[Meter]:
        rows = self._conn.execute(f"SELECT {COLUMNS} FROM meter ORDER BY serial").fetchall()
        return [read_meter(r) for r in rows]

    def by_state(self, state: MeterState) -> list[Meter]:
        rows = self._conn.execute(
            f"SELECT {COLUMNS} FROM meter WHERE state = ? ORDER BY serial", (state.value,)
        ).fetchall()
        return [read_meter(r) for r in rows]

    def by_device(self, device_key: str) -> list[Meter]:
        rows = self._conn.execute(
            f"SELECT {COLUMNS} FROM meter WHERE device_key = ? ORDER BY serial", (device_key,)
        ).fetchall()
        return [read_meter(r) for r in rows]

    def in_shop(self) -> list[Meter]:
        """Every meter physically in the building and available to a bench."""
        marks = ", ".join("?" * len(BENCHABLE))
        rows = self._conn.execute(
            f"SELECT {COLUMNS} FROM meter WHERE state IN ({marks}) ORDER BY serial",
            tuple(sorted(s.value for s in BENCHABLE)),
        ).fetchall()
        return [read_meter(r) for r in rows]

    def counts_by_state(self) -> dict[MeterState, int]:
        rows = self._conn.execute("SELECT state, COUNT(*) FROM meter GROUP BY state").fetchall()
        found = {str(r[0]): int(r[1]) for r in rows}
        return {state: found.get(state.value, 0) for state in MeterState}

    def count(self) -> int:
        return int(self._conn.execute("SELECT COUNT(*) FROM meter").fetchone()[0])


__all__ = ["COLUMNS", "MeterRepository"]
