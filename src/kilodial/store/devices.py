"""Storing and finding device types.

Types are looked up by their key far more often than by anything else, so the
key is composed here rather than stored, and every query that takes a key splits
it back into the two columns the table is built on. Storing the composed key as
a third column would be faster and would let the two drift apart, and a book
where Halvern/R4S and (Halvern, R4S) disagree is not worth the microseconds.
"""

from __future__ import annotations

import sqlite3

from kilodial.errors import BadInputError, DuplicateError, NotFoundError
from kilodial.model.device import DeviceType
from kilodial.model.form import MeterClass, Technology
from kilodial.store.codec import device_row, read_device

COLUMNS = (
    "manufacturer, model_code, form_code, class_code, voltage, kh, technology, "
    "register_ratio, demand_capable, introduced, retired, demand_interval"
)


def split_key(key: object) -> tuple[str, str]:
    """Split ``maker/model`` into its two halves, refusing anything else."""
    if not isinstance(key, str):
        raise BadInputError(f"cannot read a device key from {type(key).__name__}")
    parts = key.split("/")
    if len(parts) != 2 or not parts[0].strip() or not parts[1].strip():
        raise BadInputError(f"{key!r} is not a device key, expected maker/model")
    return parts[0].strip(), parts[1].strip()


class DeviceRepository:
    """Device types on one book."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._conn = connection

    def add(self, device: DeviceType) -> DeviceType:
        """Put a new type on the book, refusing to overwrite one."""
        if self.exists(device.key):
            raise DuplicateError("device type", device.key)
        self._conn.execute(
            f"INSERT INTO device_type ({COLUMNS}) VALUES ({', '.join('?' * 12)})",
            device_row(device),
        )
        return device

    def replace(self, device: DeviceType) -> DeviceType:
        """Overwrite a type that is already on the book."""
        if not self.exists(device.key):
            raise NotFoundError("device type", device.key)
        row = device_row(device)
        self._conn.execute(
            "UPDATE device_type SET form_code = ?, class_code = ?, voltage = ?, kh = ?, "
            "technology = ?, register_ratio = ?, demand_capable = ?, introduced = ?, "
            "retired = ?, demand_interval = ? WHERE manufacturer = ? AND model_code = ?",
            (*row[2:], row[0], row[1]),
        )
        return device

    def exists(self, key: object) -> bool:
        maker, model = split_key(key)
        found = self._conn.execute(
            "SELECT 1 FROM device_type WHERE manufacturer = ? AND model_code = ?",
            (maker, model),
        ).fetchone()
        return found is not None

    def get(self, key: object) -> DeviceType:
        maker, model = split_key(key)
        row = self._conn.execute(
            f"SELECT {COLUMNS} FROM device_type WHERE manufacturer = ? AND model_code = ?",
            (maker, model),
        ).fetchone()
        if row is None:
            raise NotFoundError("device type", f"{maker}/{model}")
        return read_device(row)

    def find(self, key: object) -> DeviceType | None:
        """The same lookup, handing back nothing rather than raising."""
        try:
            return self.get(key)
        except NotFoundError:
            return None

    def all(self) -> list[DeviceType]:
        rows = self._conn.execute(
            f"SELECT {COLUMNS} FROM device_type ORDER BY manufacturer, model_code"
        ).fetchall()
        return [read_device(r) for r in rows]

    def by_class(self, meter_class: MeterClass) -> list[DeviceType]:
        rows = self._conn.execute(
            f"SELECT {COLUMNS} FROM device_type WHERE class_code = ? "
            "ORDER BY manufacturer, model_code",
            (meter_class.code,),
        ).fetchall()
        return [read_device(r) for r in rows]

    def by_technology(self, technology: Technology) -> list[DeviceType]:
        rows = self._conn.execute(
            f"SELECT {COLUMNS} FROM device_type WHERE technology = ? "
            "ORDER BY manufacturer, model_code",
            (technology.value,),
        ).fetchall()
        return [read_device(r) for r in rows]

    def current_on(self, day: object) -> list[DeviceType]:
        """Types the shop was still buying on a given day."""
        return [d for d in self.all() if d.was_current_on(day)]

    def count(self) -> int:
        return int(self._conn.execute("SELECT COUNT(*) FROM device_type").fetchone()[0])


__all__ = ["COLUMNS", "DeviceRepository", "split_key"]
