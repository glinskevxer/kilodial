"""Storing service points and the meter sets on them.

One rule here is worth more than the rest of the module: a service point has one
meter on it at a time. It sounds obvious and it is the thing that goes wrong,
because a set gets entered from a work order without the previous one having been
closed off, and from then on every question asked about that point over a period
has two answers.

So ``set_meter`` refuses to open a set that overlaps one already on the point,
and refuses to set a meter that is already standing somewhere else. Both checks
read the whole history of the point rather than only its current set, because
backdated entries are ordinary here: a crew sets a meter on Tuesday and the work
order reaches the office on Friday.
"""

from __future__ import annotations

import sqlite3

from kilodial.errors import DuplicateError, NotFoundError, RuleError
from kilodial.install.point import MeterSet, ServicePoint
from kilodial.store.base import has_row, one_row, upper
from kilodial.store.codec import (
    meter_set_row,
    read_meter_set,
    read_service_point,
    service_point_row,
)
from kilodial.units.span import DateSpan, parse_date

POINT_COLUMNS = "code, account, address, service, voltage, rate_code, energised, disconnected"
SET_COLUMNS = (
    "point_code, meter_serial, ct_serial, vt_serial, register_multiplier, "
    "programmed_multiplier, set_on, removed_on"
)


class ServicePointRepository:
    """Service points on one book."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._conn = connection

    def add(self, point: ServicePoint) -> ServicePoint:
        if self.exists(point.code):
            raise DuplicateError("service point", point.code)
        self._conn.execute(
            f"INSERT INTO service_point ({POINT_COLUMNS}) VALUES ({', '.join('?' * 8)})",
            service_point_row(point),
        )
        return point

    def save(self, point: ServicePoint) -> ServicePoint:
        if not self.exists(point.code):
            raise NotFoundError("service point", point.code)
        row = service_point_row(point)
        self._conn.execute(
            "UPDATE service_point SET account = ?, address = ?, service = ?, voltage = ?, "
            "rate_code = ?, energised = ?, disconnected = ? WHERE code = ?",
            (*row[1:], row[0]),
        )
        return point

    def exists(self, code: str) -> bool:
        return has_row(self._conn, "service_point", "code", upper(code))

    def get(self, code: str) -> ServicePoint:
        return read_service_point(
            one_row(
                self._conn,
                POINT_COLUMNS,
                "service_point",
                "code",
                upper(code),
                "service point",
            )
        )

    def all(self) -> list[ServicePoint]:
        rows = self._conn.execute(
            f"SELECT {POINT_COLUMNS} FROM service_point ORDER BY code"
        ).fetchall()
        return [read_service_point(r) for r in rows]

    def by_account(self, account: str) -> list[ServicePoint]:
        rows = self._conn.execute(
            f"SELECT {POINT_COLUMNS} FROM service_point WHERE account = ? ORDER BY code",
            (account.strip().upper(),),
        ).fetchall()
        return [read_service_point(r) for r in rows]

    def live_on(self, day: object) -> list[ServicePoint]:
        return [p for p in self.all() if p.was_live_on(day)]

    def count(self) -> int:
        return int(self._conn.execute("SELECT COUNT(*) FROM service_point").fetchone()[0])


class InstallRepository:
    """Meter sets on one book."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._conn = connection
        self._points = ServicePointRepository(connection)

    def set_meter(self, meter_set: MeterSet) -> MeterSet:
        """Open a set, refusing anything that would double book a point."""
        if not self._points.exists(meter_set.point_code):
            raise RuleError(f"service point {meter_set.point_code} is not on the book")
        for existing in self.history(meter_set.point_code):
            if existing.span.overlaps(meter_set.span):
                raise RuleError(
                    f"{existing.meter_serial} is already set at {meter_set.point_code} "
                    f"over {existing.span}"
                )
        standing = self.current_for_meter(meter_set.meter_serial)
        if standing is not None and standing.span.overlaps(meter_set.span):
            raise RuleError(
                f"meter {meter_set.meter_serial} is already set at {standing.point_code}"
            )
        self._conn.execute(
            f"INSERT INTO meter_set ({SET_COLUMNS}) VALUES ({', '.join('?' * 8)})",
            meter_set_row(meter_set),
        )
        return meter_set

    def pull(self, point_code: str, day: object) -> MeterSet:
        """Close off whatever is standing at a point."""
        standing = self.current(point_code)
        if standing is None:
            raise RuleError(f"nothing is set at {point_code.strip().upper()}")
        pulled = standing.pulled_on(day)
        self._conn.execute(
            "UPDATE meter_set SET removed_on = ? WHERE point_code = ? AND meter_serial = ? "
            "AND set_on = ?",
            (
                parse_date(day).isoformat(),
                pulled.point_code,
                pulled.meter_serial,
                pulled.set_on.isoformat(),
            ),
        )
        return pulled

    def history(self, point_code: str) -> list[MeterSet]:
        """Every set that point has ever carried, oldest first."""
        rows = self._conn.execute(
            f"SELECT {SET_COLUMNS} FROM meter_set WHERE point_code = ? ORDER BY set_on",
            (point_code.strip().upper(),),
        ).fetchall()
        return [read_meter_set(r) for r in rows]

    def current(self, point_code: str) -> MeterSet | None:
        for candidate in self.history(point_code):
            if candidate.is_current:
                return candidate
        return None

    def on_day(self, point_code: str, day: object) -> MeterSet | None:
        """What was standing at a point on a given day."""
        for candidate in self.history(point_code):
            if candidate.was_set_on(day):
                return candidate
        return None

    def for_meter(self, serial: str) -> list[MeterSet]:
        rows = self._conn.execute(
            f"SELECT {SET_COLUMNS} FROM meter_set WHERE meter_serial = ? ORDER BY set_on",
            (serial.strip().upper(),),
        ).fetchall()
        return [read_meter_set(r) for r in rows]

    def current_for_meter(self, serial: str) -> MeterSet | None:
        for candidate in self.for_meter(serial):
            if candidate.is_current:
                return candidate
        return None

    def using_transformer(self, serial: str) -> list[MeterSet]:
        key = serial.strip().upper()
        rows = self._conn.execute(
            f"SELECT {SET_COLUMNS} FROM meter_set WHERE ct_serial = ? OR vt_serial = ? "
            "ORDER BY point_code, set_on",
            (key, key),
        ).fetchall()
        return [read_meter_set(r) for r in rows]

    def covering(self, point_code: str, span: DateSpan) -> list[MeterSet]:
        """Every set at a point that overlaps a period."""
        return [s for s in self.history(point_code) if s.span.overlaps(span)]

    def count(self) -> int:
        return int(self._conn.execute("SELECT COUNT(*) FROM meter_set").fetchone()[0])


__all__ = ["POINT_COLUMNS", "SET_COLUMNS", "InstallRepository", "ServicePointRepository"]
