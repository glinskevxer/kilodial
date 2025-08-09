"""Write the schema out, and check the written copy still matches the code.

The migrations are the truth and they are unreadable as a description of the
book: seven numbered steps, each a list of statements, several of them altering
what an earlier one built. Nobody trying to write a query reads them.

So the schema is also kept as one flat file, built by running every migration
into a temporary book and asking sqlite what came out. In ``--check`` mode the
same thing is built and compared against the file on disk, which is what CI
runs. A schema change that does not update the file fails the build, and the
diff in the review is the schema change itself, which is exactly what a reviewer
wants to look at.
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
import tempfile
from pathlib import Path

from kilodial.store.book import open_migrated
from kilodial.store.schema import MIGRATIONS, latest_number
from kilodial.tools import FAILED, OK

DEFAULT_PATH = Path("docs/schema.sql")
HEADER = """-- kilodial schema, built from the migrations. Do not edit by hand.
-- Rebuild with: python -m kilodial.tools.schema_dump
-- Migrations applied: {count} (latest {latest})
"""


def statements_of(connection: sqlite3.Connection) -> list[str]:
    """Every CREATE the book carries, tables first and then indexes."""
    rows = connection.execute(
        "SELECT type, name, sql FROM sqlite_master WHERE sql IS NOT NULL "
        "AND name NOT LIKE 'sqlite_%' ORDER BY type DESC, name"
    ).fetchall()
    return [f"{str(r[2]).strip()};" for r in rows]


def build() -> str:
    """The whole schema as text, built from the migrations."""
    with tempfile.TemporaryDirectory() as where:
        book = open_migrated(Path(where) / "schema.sqlite3", create=True)
        try:
            body = "\n\n".join(statements_of(book.connection))
        finally:
            book.close()
    header = HEADER.format(count=len(MIGRATIONS), latest=latest_number())
    return f"{header}\n{body}\n"


def write(path: Path = DEFAULT_PATH) -> Path:
    """Write the schema out, creating the directory if it is not there."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(build())
    return path


def differences(path: Path = DEFAULT_PATH) -> list[str]:
    """How the file on disk differs from what the migrations build."""
    if not path.exists():
        return [f"there is no schema dump at {path}"]
    on_disk = path.read_text().splitlines()
    wanted = build().splitlines()
    if on_disk == wanted:
        return []
    found = [f"{path} is {len(on_disk)} lines and the migrations build {len(wanted)}"]
    for index, (was, now) in enumerate(zip(on_disk, wanted, strict=False), start=1):
        if was != now:
            found.append(f"line {index}: {was!r} should be {now!r}")
            break
    return found


def main(argv: list[str] | None = None) -> int:
    """Write the dump, or check it and fail when it has gone stale."""
    parser = argparse.ArgumentParser(description="dump or check the schema")
    parser.add_argument("--path", type=Path, default=DEFAULT_PATH)
    parser.add_argument("--check", action="store_true", help="compare rather than write")
    args = parser.parse_args(argv)
    if not args.check:
        written = write(args.path)
        print(f"wrote {written} from {len(MIGRATIONS)} migrations")
        return OK
    problems = differences(args.path)
    for problem in problems:
        print(problem)
    if problems:
        print("run python -m kilodial.tools.schema_dump to bring it up to date")
        return FAILED
    print(f"{args.path} matches the migrations")
    return OK


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())


__all__ = ["DEFAULT_PATH", "HEADER", "build", "differences", "main", "statements_of", "write"]
