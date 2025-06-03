"""Storing sampling groups and the decisions taken on them.

Group membership is not stored. It is recomputed from the criteria every time,
against the meters and device types on the book, which is the only way a
population stays honest as meters are scrapped and set.

Decisions are stored, one row per sample, and the group's current interval is
replayed from them rather than kept in a column. That costs a query and it means
the interval and the history cannot disagree, which they will otherwise do the
first time somebody corrects a decision that was entered wrong.
"""

from __future__ import annotations

import sqlite3

from kilodial.errors import DuplicateError, NotFoundError, RuleError
from kilodial.model.device import DeviceType
from kilodial.model.meter import Meter
from kilodial.sampling.decision import Decision, interval_after
from kilodial.sampling.group import Group
from kilodial.sampling.plan import INTERVAL_LADDER
from kilodial.store.codec import group_row, plan_row, read_group, read_plan
from kilodial.store.devices import DeviceRepository
from kilodial.store.meters import MeterRepository
from kilodial.units.span import parse_date

GROUP_COLUMNS = (
    "code, name, device_keys, class_code, technology, form_codes, acquired_from, acquired_to"
)
PLAN_COLUMNS = (
    "group_code, decided_on, interval_months, population, tested, mean, deviation, "
    "failures, passed, note"
)


class GroupRepository:
    """Sampling groups on one book."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._conn = connection
        self._meters = MeterRepository(connection)
        self._devices = DeviceRepository(connection)

    def add(self, group: Group) -> Group:
        if self.exists(group.code):
            raise DuplicateError("sampling group", group.code)
        self._conn.execute(
            f"INSERT INTO sample_group ({GROUP_COLUMNS}) VALUES ({', '.join('?' * 8)})",
            group_row(group),
        )
        return group

    def save(self, group: Group) -> Group:
        if not self.exists(group.code):
            raise NotFoundError("sampling group", group.code)
        row = group_row(group)
        self._conn.execute(
            "UPDATE sample_group SET name = ?, device_keys = ?, class_code = ?, "
            "technology = ?, form_codes = ?, acquired_from = ?, acquired_to = ? "
            "WHERE code = ?",
            (*row[1:], row[0]),
        )
        return group

    def exists(self, code: str) -> bool:
        found = self._conn.execute(
            "SELECT 1 FROM sample_group WHERE code = ?", (code.strip().upper(),)
        ).fetchone()
        return found is not None

    def get(self, code: str) -> Group:
        wanted = code.strip().upper()
        row = self._conn.execute(
            f"SELECT {GROUP_COLUMNS} FROM sample_group WHERE code = ?", (wanted,)
        ).fetchone()
        if row is None:
            raise NotFoundError("sampling group", wanted)
        return read_group(row)

    def all(self) -> list[Group]:
        rows = self._conn.execute(
            f"SELECT {GROUP_COLUMNS} FROM sample_group ORDER BY code"
        ).fetchall()
        return [read_group(r) for r in rows]

    def delete(self, code: str) -> None:
        wanted = code.strip().upper()
        if not self.exists(wanted):
            raise NotFoundError("sampling group", wanted)
        self._conn.execute("DELETE FROM sample_group WHERE code = ?", (wanted,))

    def members(self, code: str) -> list[Meter]:
        """The meters in a group right now, worked out from the criteria."""
        group = self.get(code)
        devices: dict[str, DeviceType] = {}
        if group.needs_device():
            devices = {d.key: d for d in self._devices.all()}
        found = []
        for meter in self._meters.all():
            device = devices.get(meter.device_key)
            if group.needs_device() and device is None:
                continue
            if group.takes(meter, device):
                found.append(meter)
        return found

    def population(self, code: str) -> int:
        return len(self.members(code))

    def group_for(self, serial: str) -> list[Group]:
        """Every group a meter falls into, which should usually be one."""
        meter = self._meters.get(serial)
        device = self._devices.find(meter.device_key)
        found = []
        for group in self.all():
            if group.needs_device() and device is None:
                continue
            if group.takes(meter, device):
                found.append(group)
        return found

    def count(self) -> int:
        return int(self._conn.execute("SELECT COUNT(*) FROM sample_group").fetchone()[0])


class PlanRepository:
    """Sample decisions on one book."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._conn = connection
        self._groups = GroupRepository(connection)

    def record(self, decision: Decision) -> Decision:
        if not self._groups.exists(decision.group_code):
            raise RuleError(f"sampling group {decision.group_code} is not on the book")
        existing = self._conn.execute(
            "SELECT 1 FROM test_plan WHERE group_code = ? AND decided_on = ?",
            (decision.group_code, decision.decided_on.isoformat()),
        ).fetchone()
        if existing is not None:
            raise DuplicateError(
                "sample decision", f"{decision.group_code}/{decision.decided_on.isoformat()}"
            )
        self._conn.execute(
            f"INSERT INTO test_plan ({PLAN_COLUMNS}) VALUES ({', '.join('?' * 10)})",
            plan_row(decision),
        )
        return decision

    def history(self, group_code: str) -> list[Decision]:
        """Every decision on a group, oldest first, with intervals replayed."""
        rows = self._conn.execute(
            f"SELECT {PLAN_COLUMNS} FROM test_plan WHERE group_code = ? ORDER BY decided_on",
            (group_code.strip().upper(),),
        ).fetchall()
        found: list[Decision] = []
        months = INTERVAL_LADDER[0]
        for row in rows:
            decision = read_plan(row, months)
            found.append(decision)
            months = interval_after([decision], start=months)
        return found

    def latest(self, group_code: str) -> Decision | None:
        history = self.history(group_code)
        return history[-1] if history else None

    def interval(self, group_code: str) -> int:
        """The interval a group is on now, replayed from its decisions."""
        return interval_after(self.history(group_code))

    def next_due(self, group_code: str) -> str | None:
        latest = self.latest(group_code)
        if latest is None:
            return None
        due = latest.next_due()
        return None if due is None else due.isoformat()

    def due_by(self, day: object) -> list[str]:
        """Groups whose next sample falls on or before a day, plus any never done."""
        wanted = parse_date(day).isoformat()
        due = []
        for group in self._groups.all():
            when = self.next_due(group.code)
            if when is None or when <= wanted:
                due.append(group.code)
        return due

    def count(self) -> int:
        return int(self._conn.execute("SELECT COUNT(*) FROM test_plan").fetchone()[0])


__all__ = ["GROUP_COLUMNS", "PLAN_COLUMNS", "GroupRepository", "PlanRepository"]
