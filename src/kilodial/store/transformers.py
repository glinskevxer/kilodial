"""Storing instrument transformers.

Transformers are tested on a different cycle from meters and by a different
crew, so their records live on their own rather than hanging off an
installation. A current transformer gets pulled out of one service and put into
another and its test history goes with it, which is only possible if the record
is keyed on the transformer.
"""

from __future__ import annotations

import sqlite3

from kilodial.errors import DuplicateError, NotFoundError
from kilodial.store.codec import read_transformer, transformer_row
from kilodial.units.span import parse_date
from kilodial.xfmr.transformer import AccuracyClass, InstrumentTransformer, TransformerKind

COLUMNS = "serial, kind, maker, marked_ratio, accuracy, rcf, phase_minutes, burden, tested_on"


class TransformerRepository:
    """Instrument transformers on one book."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._conn = connection

    def add(self, transformer: InstrumentTransformer) -> InstrumentTransformer:
        if self.exists(transformer.serial):
            raise DuplicateError("instrument transformer", transformer.serial)
        self._conn.execute(
            f"INSERT INTO instrument_transformer ({COLUMNS}) VALUES ({', '.join('?' * 9)})",
            transformer_row(transformer),
        )
        return transformer

    def save(self, transformer: InstrumentTransformer) -> InstrumentTransformer:
        if not self.exists(transformer.serial):
            raise NotFoundError("instrument transformer", transformer.serial)
        row = transformer_row(transformer)
        self._conn.execute(
            "UPDATE instrument_transformer SET kind = ?, maker = ?, marked_ratio = ?, "
            "accuracy = ?, rcf = ?, phase_minutes = ?, burden = ?, tested_on = ? "
            "WHERE serial = ?",
            (*row[1:], row[0]),
        )
        return transformer

    def exists(self, serial: str) -> bool:
        found = self._conn.execute(
            "SELECT 1 FROM instrument_transformer WHERE serial = ?",
            (serial.strip().upper(),),
        ).fetchone()
        return found is not None

    def get(self, serial: str) -> InstrumentTransformer:
        key = serial.strip().upper()
        row = self._conn.execute(
            f"SELECT {COLUMNS} FROM instrument_transformer WHERE serial = ?", (key,)
        ).fetchone()
        if row is None:
            raise NotFoundError("instrument transformer", key)
        return read_transformer(row)

    def find(self, serial: str | None) -> InstrumentTransformer | None:
        """Look one up, taking None for the set that does not have one."""
        if serial is None:
            return None
        try:
            return self.get(serial)
        except NotFoundError:
            return None

    def all(self) -> list[InstrumentTransformer]:
        rows = self._conn.execute(
            f"SELECT {COLUMNS} FROM instrument_transformer ORDER BY serial"
        ).fetchall()
        return [read_transformer(r) for r in rows]

    def by_kind(self, kind: TransformerKind) -> list[InstrumentTransformer]:
        rows = self._conn.execute(
            f"SELECT {COLUMNS} FROM instrument_transformer WHERE kind = ? ORDER BY serial",
            (kind.value,),
        ).fetchall()
        return [read_transformer(r) for r in rows]

    def by_accuracy(self, accuracy: AccuracyClass) -> list[InstrumentTransformer]:
        rows = self._conn.execute(
            f"SELECT {COLUMNS} FROM instrument_transformer WHERE accuracy = ? ORDER BY serial",
            (accuracy.code,),
        ).fetchall()
        return [read_transformer(r) for r in rows]

    def tested_before(self, day: object) -> list[InstrumentTransformer]:
        """Transformers whose last test is older than a day, oldest first."""
        rows = self._conn.execute(
            f"SELECT {COLUMNS} FROM instrument_transformer WHERE tested_on < ? "
            "ORDER BY tested_on, serial",
            (parse_date(day).isoformat(),),
        ).fetchall()
        return [read_transformer(r) for r in rows]

    def count(self) -> int:
        return int(self._conn.execute("SELECT COUNT(*) FROM instrument_transformer").fetchone()[0])


__all__ = ["COLUMNS", "TransformerRepository"]
