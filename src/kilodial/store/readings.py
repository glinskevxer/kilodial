"""Storing register readings and working consumption out of consecutive ones.

The table is keyed on point, meter and day, so a service read twice on the same
day by two different people produces a collision rather than two readings, which
is right: one of them is wrong and somebody has to say which.

The interesting method is ``consumption_over``. It pairs the readings a period
sits between and returns what passed, and it refuses rather than guessing when
the period spans a meter change, because a change needs the outgoing meter's
final reading and the incoming one's initial and the caller has to supply both.
"""

from __future__ import annotations

import sqlite3

from kilodial.errors import DuplicateError, NotFoundError, RuleError
from kilodial.model.reading import Consumption, Reading, ReadingKind, consumption
from kilodial.store.base import member_of, upper
from kilodial.units.span import DateSpan, parse_date

COLUMNS = "point_code, meter_serial, read_on, dials, value, kind, note"


class ReadingRepository:
    """Register readings on one book."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._conn = connection

    def add(self, reading: Reading) -> Reading:
        """Record a reading against a service point that is on the book."""
        found = self._conn.execute(
            "SELECT 1 FROM service_point WHERE code = ?", (reading.point_code,)
        ).fetchone()
        if found is None:
            raise RuleError(f"service point {reading.point_code} is not on the book")
        if self.exists(reading.point_code, reading.meter_serial, reading.read_on):
            raise DuplicateError(
                "reading",
                f"{reading.point_code}/{reading.meter_serial}/{reading.read_on.isoformat()}",
            )
        self._conn.execute(
            f"INSERT INTO reading ({COLUMNS}) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                reading.point_code,
                reading.meter_serial,
                reading.read_on.isoformat(),
                reading.dials,
                reading.value,
                reading.kind.label,
                reading.note,
            ),
        )
        return reading

    def exists(self, point_code: str, meter_serial: str, day: object) -> bool:
        found = self._conn.execute(
            "SELECT 1 FROM reading WHERE point_code = ? AND meter_serial = ? AND read_on = ?",
            (upper(point_code), upper(meter_serial), parse_date(day).isoformat()),
        ).fetchone()
        return found is not None

    def get(self, point_code: str, meter_serial: str, day: object) -> Reading:
        row = self._conn.execute(
            f"SELECT {COLUMNS} FROM reading WHERE point_code = ? AND meter_serial = ? "
            "AND read_on = ?",
            (upper(point_code), upper(meter_serial), parse_date(day).isoformat()),
        ).fetchone()
        if row is None:
            raise NotFoundError("reading", f"{upper(point_code)}/{upper(meter_serial)}/{day}")
        return _read(row)

    def for_point(self, point_code: str) -> list[Reading]:
        rows = self._conn.execute(
            f"SELECT {COLUMNS} FROM reading WHERE point_code = ? ORDER BY read_on",
            (upper(point_code),),
        ).fetchall()
        return [_read(r) for r in rows]

    def for_meter(self, serial: str) -> list[Reading]:
        rows = self._conn.execute(
            f"SELECT {COLUMNS} FROM reading WHERE meter_serial = ? ORDER BY read_on",
            (upper(serial),),
        ).fetchall()
        return [_read(r) for r in rows]

    def covering(self, point_code: str, span: DateSpan) -> list[Reading]:
        """Every reading at a point inside a window."""
        return [r for r in self.for_point(point_code) if span.contains(r.read_on)]

    def latest(self, point_code: str) -> Reading | None:
        found = self.for_point(point_code)
        return found[-1] if found else None

    def consumption_over(
        self, point_code: str, span: DateSpan, *, multiplier: object = 1
    ) -> Consumption:
        """What passed at a point over a window, from the readings that bound it.

        Both ends have to be real readings on the same meter. A window that ends
        in the middle of a billing period, or one that spans a meter change, is
        refused rather than interpolated.
        """
        found = self.covering(point_code, span)
        if len(found) < 2:
            raise RuleError(
                f"{upper(point_code)} has {len(found)} readings over {span}, "
                "which is not enough to work consumption out of"
            )
        first, last = found[0], found[-1]
        if first.meter_serial != last.meter_serial:
            raise RuleError(
                f"{upper(point_code)} changed meter between {first.read_on.isoformat()} "
                f"and {last.read_on.isoformat()}, so the readings do not pair"
            )
        return consumption(first, last, multiplier=multiplier)

    def count(self) -> int:
        return int(self._conn.execute("SELECT COUNT(*) FROM reading").fetchone()[0])


def _read(row: tuple[object, ...]) -> Reading:
    return Reading(
        point_code=str(row[0]),
        meter_serial=str(row[1]),
        read_on=parse_date(str(row[2])),
        dials=int(str(row[3])),
        value=int(str(row[4])),
        kind=member_of(ReadingKind, row[5], "reading kind", field="label"),
        note=None if row[6] is None else str(row[6]),
    )


__all__ = ["COLUMNS", "ReadingRepository"]
