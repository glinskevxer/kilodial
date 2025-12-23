"""An append only log of what was done to the book.

Every other table on the book records what is true. This one records what
happened, and the difference is the whole point: a meter that is in stock today
tells you nothing about whether it was scrapped and un-scrapped twice last
month, and somebody will eventually ask.

Three decisions worth stating.

It is append only. There is no update and no delete, and the sequence is a
sqlite autoincrement so a deleted row leaves a visible gap rather than being
silently absorbed. A log that can be edited is not a log.

The actor is whatever the caller says it is, and this package makes no attempt
to authenticate it. It is a shell tool on a shop machine and pretending
otherwise would be theatre. What it does buy is a record of which of four people
entered a run when three of them disagree about it later.

It records the sentence, not the row. Storing a before and after image of every
changed record is a different and much bigger feature, and half of it would be
noise. What is here is what a person would write in a day book.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime

from kilodial.errors import RuleError
from kilodial.units.text import optional, tidy

COLUMNS = "sequence, at, actor, action, subject, detail"
DEFAULT_ACTOR = "shop"


@dataclass(frozen=True)
class Event:
    """One thing that happened."""

    sequence: int
    at: str
    actor: str
    action: str
    subject: str
    detail: str | None

    @property
    def day(self) -> str:
        """The date part of the stamp, which is what a report groups on."""
        return self.at[:10]

    def __str__(self) -> str:
        tail = "" if self.detail is None else f", {self.detail}"
        return f"{self.at} {self.actor} {self.action} {self.subject}{tail}"


class EventRepository:
    """The event log on one book."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._conn = connection

    def record(
        self,
        action: object,
        subject: object,
        *,
        detail: object = None,
        actor: object = DEFAULT_ACTOR,
        at: object = None,
    ) -> Event:
        """Append one line. Nothing here ever updates anything."""
        stamp = _stamp(at)
        row = (
            stamp,
            tidy(actor, "actor", 40),
            tidy(action, "action", 40).lower(),
            tidy(subject, "subject", 60),
            optional(detail, "detail", 240),
        )
        cursor = self._conn.execute(
            "INSERT INTO event (at, actor, action, subject, detail) VALUES (?, ?, ?, ?, ?)",
            row,
        )
        sequence = cursor.lastrowid
        if sequence is None:
            raise RuleError("the event log did not hand back a sequence number")
        return Event(int(sequence), *row)

    def all(self, *, limit: int | None = None) -> list[Event]:
        """The log, newest last, optionally the tail of it."""
        if limit is not None and limit <= 0:
            raise RuleError("a log limit has to be a positive number of lines")
        rows = self._conn.execute(f"SELECT {COLUMNS} FROM event ORDER BY sequence").fetchall()
        found = [_read(r) for r in rows]
        return found if limit is None else found[-limit:]

    def about(self, subject: str) -> list[Event]:
        """Everything that happened to one subject, oldest first."""
        rows = self._conn.execute(
            f"SELECT {COLUMNS} FROM event WHERE subject = ? ORDER BY sequence",
            (subject.strip(),),
        ).fetchall()
        return [_read(r) for r in rows]

    def by_action(self, action: str) -> list[Event]:
        rows = self._conn.execute(
            f"SELECT {COLUMNS} FROM event WHERE action = ? ORDER BY sequence",
            (action.strip().lower(),),
        ).fetchall()
        return [_read(r) for r in rows]

    def by_actor(self, actor: str) -> list[Event]:
        rows = self._conn.execute(
            f"SELECT {COLUMNS} FROM event WHERE actor = ? ORDER BY sequence",
            (" ".join(actor.split()),),
        ).fetchall()
        return [_read(r) for r in rows]

    def on_day(self, day: str) -> list[Event]:
        rows = self._conn.execute(
            f"SELECT {COLUMNS} FROM event WHERE at LIKE ? ORDER BY sequence",
            (f"{day.strip()}%",),
        ).fetchall()
        return [_read(r) for r in rows]

    def counts_by_action(self) -> dict[str, int]:
        rows = self._conn.execute(
            "SELECT action, COUNT(*) FROM event GROUP BY action ORDER BY action"
        ).fetchall()
        return {str(r[0]): int(r[1]) for r in rows}

    def gaps(self) -> list[int]:
        """Sequence numbers that are missing, which means somebody deleted a line.

        Counted from one rather than from the lowest number present. Starting at
        the lowest present would miss the case that matters most, which is
        somebody deleting the first line and leaving a log that looks whole.
        """
        rows = self._conn.execute("SELECT sequence FROM event ORDER BY sequence").fetchall()
        numbers = [int(r[0]) for r in rows]
        if not numbers:
            return []
        return [n for n in range(1, numbers[-1] + 1) if n not in set(numbers)]

    def count(self) -> int:
        return int(self._conn.execute("SELECT COUNT(*) FROM event").fetchone()[0])


def _stamp(at: object) -> str:
    if at is None:
        return datetime.now(UTC).replace(microsecond=0).isoformat()
    text = str(at).strip()
    if not text:
        raise RuleError("an event stamp cannot be blank")
    return text


def _read(row: tuple[object, ...]) -> Event:
    return Event(
        sequence=int(str(row[0])),
        at=str(row[1]),
        actor=str(row[2]),
        action=str(row[3]),
        subject=str(row[4]),
        detail=None if row[5] is None else str(row[5]),
    )


__all__ = ["COLUMNS", "DEFAULT_ACTOR", "Event", "EventRepository"]
