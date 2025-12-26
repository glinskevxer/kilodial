"""Opening the book, bringing it up to date, and holding a transaction.

One sqlite file per shop. The file carries an application id so that pointing
the tool at somebody else's database fails loudly instead of migrating it, and a
ledger table so that an interrupted upgrade can be told apart from a book that
was never upgraded.

Two decisions worth the words:

Foreign keys are switched on per connection, because sqlite defaults them off
and a book that has been read once without them has already let an orphan
through. It is set on every connection this module hands out, not once at
creation.

Each migration runs statement by statement inside one explicit transaction that
also writes its ledger row. executescript would be shorter and it commits before
it runs, which puts the ledger row outside the transaction protecting it.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from types import TracebackType

from kilodial.errors import ConfigError
from kilodial.store.schema import APPLICATION_ID, MIGRATIONS, latest_number

LEDGER = """
CREATE TABLE IF NOT EXISTS schema_migration (
    number      INTEGER PRIMARY KEY,
    name        TEXT NOT NULL,
    applied_at  TEXT NOT NULL
)
"""


@dataclass(frozen=True)
class Applied:
    """One row of the ledger."""

    number: int
    name: str
    applied_at: str


class Book:
    """A shop book, open."""

    def __init__(self, path: str | Path, connection: sqlite3.Connection) -> None:
        self.path = Path(path)
        self._connection = connection

    @property
    def connection(self) -> sqlite3.Connection:
        return self._connection

    def close(self) -> None:
        self._connection.close()

    def __enter__(self) -> Book:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        """Run a block inside one transaction, rolling back on anything raised."""
        conn = self._connection
        conn.execute("BEGIN")
        try:
            yield conn
        except BaseException:
            conn.rollback()
            raise
        else:
            try:
                conn.commit()
            except BaseException:
                # A commit can fail on its own. Deferred foreign keys are checked
                # here rather than per statement, so a load that looked fine all
                # the way through raises at this point, and without this rollback
                # the transaction stays open and the rows stay visible.
                conn.rollback()
                raise

    def applied(self) -> list[Applied]:
        """The ledger, oldest first."""
        rows = self._connection.execute(
            "SELECT number, name, applied_at FROM schema_migration ORDER BY number"
        ).fetchall()
        return [Applied(int(r[0]), str(r[1]), str(r[2])) for r in rows]

    @property
    def version(self) -> int:
        """The highest migration this book has run."""
        row = self._connection.execute("SELECT MAX(number) FROM schema_migration").fetchone()
        return 0 if row is None or row[0] is None else int(row[0])

    def pending(self) -> list[int]:
        done = {a.number for a in self.applied()}
        return [m.number for m in MIGRATIONS if m.number not in done]

    def migrate(self) -> list[int]:
        """Run every migration this book has not run, and say which."""
        done = {a.number for a in self.applied()}
        ran: list[int] = []
        for migration in MIGRATIONS:
            if migration.number in done:
                continue
            with self.transaction() as conn:
                for statement in migration.statements:
                    conn.execute(statement)
                conn.execute(
                    "INSERT INTO schema_migration (number, name, applied_at) VALUES (?, ?, ?)",
                    (migration.number, migration.name, _stamp()),
                )
            ran.append(migration.number)
        return ran

    def check(self) -> list[str]:
        """Everything wrong with the book as it stands."""
        faults: list[str] = []
        got = self._connection.execute("PRAGMA application_id").fetchone()[0]
        if int(got) != APPLICATION_ID:
            faults.append(f"application id is {got}, not a kilodial book")
        if self.pending():
            faults.append(
                f"the book is at migration {self.version} and the code is at {latest_number()}"
            )
        broken = self._connection.execute("PRAGMA foreign_key_check").fetchall()
        if broken:
            faults.append(f"{len(broken)} rows break a foreign key")
        integrity = self._connection.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            faults.append(f"sqlite reports {integrity}")
        return faults

    def __str__(self) -> str:
        return f"{self.path} at migration {self.version}"


def _stamp() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def connect(path: str | Path) -> sqlite3.Connection:
    """Open a connection with the pragmas this package relies on."""
    conn = sqlite3.connect(str(path), isolation_level=None)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    return conn


def open_book(path: str | Path, *, create: bool = False) -> Book:
    """Open an existing book, or create one when asked.

    Opening refuses a file that is not a kilodial book. That check is worth
    having because sqlite will happily open anything and the first migration
    would otherwise scatter our tables through somebody else's database.
    """
    target = Path(path)
    exists = target.exists()
    if not exists and not create:
        raise ConfigError(f"there is no book at {target}")
    conn = connect(target)
    try:
        conn.execute(LEDGER)
        stored = int(conn.execute("PRAGMA application_id").fetchone()[0])
        if stored == 0 and (create or not exists):
            conn.execute(f"PRAGMA application_id = {APPLICATION_ID}")
        elif stored != APPLICATION_ID:
            raise ConfigError(f"{target} is not a kilodial book")
    except BaseException:
        conn.close()
        raise
    return Book(target, conn)


def open_migrated(path: str | Path, *, create: bool = False) -> Book:
    """Open a book and bring it up to date in one step."""
    book = open_book(path, create=create)
    try:
        book.migrate()
    except BaseException:
        book.close()
        raise
    return book


__all__ = ["LEDGER", "Applied", "Book", "connect", "open_book", "open_migrated"]
