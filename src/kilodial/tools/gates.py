"""Run every gate in one go, the way CI does, from one command.

CI lists the gates one per step and that is right for CI: a failing step names
itself in the run summary and nobody has to read a log to find out which check
broke. It is wrong for a person about to push, who wants one command and one
answer.

So this runs them all, prints each one's own output under its name, and reports
at the end. It runs all of them even after one fails, because the whole point of
running them before pushing is to find out everything that is wrong rather than
the first thing.

It does not run ruff, mypy or pytest. Those have their own runners that are
better than anything here would be, and the shell line that runs all three is in
the readme.
"""

from __future__ import annotations

import io
import sys
from contextlib import redirect_stdout
from dataclasses import dataclass

from kilodial.tools import (
    FAILED,
    OK,
    build_docs,
    build_glossary,
    check_clock,
    check_docstrings,
    check_exports,
    check_help,
    check_layers,
    check_messages,
    check_migrations,
    check_tests,
    check_wiring,
    check_workflow,
    query_plan,
    schema_dump,
    smoke,
)

# Every gate, with the arguments CI gives it. Ordered cheapest first, so a broken
# migration list is reported before anything spends time walking the imports.
GATES: tuple[tuple[str, object, list[str]], ...] = (
    ("migrations", check_migrations, []),
    ("exports", check_exports, []),
    ("docstrings", check_docstrings, []),
    ("messages", check_messages, []),
    ("clock", check_clock, []),
    ("wiring", check_wiring, []),
    ("layers", check_layers, []),
    ("tests", check_tests, []),
    ("help", check_help, []),
    ("workflow", check_workflow, []),
    ("query plan", query_plan, []),
    ("schema", schema_dump, ["--check"]),
    ("commands", build_docs, ["--check"]),
    ("glossary", build_glossary, ["--check"]),
    ("smoke", smoke, ["--quiet"]),
)


@dataclass(frozen=True)
class Result:
    """One gate's outcome and whatever it printed."""

    name: str
    code: int
    output: str

    @property
    def passed(self) -> bool:
        return self.code == OK

    def __str__(self) -> str:
        return f"{'ok  ' if self.passed else 'FAIL'} {self.name}"


def run_one(name: str, module: object, argv: list[str]) -> Result:
    """Run one gate with its output captured."""
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        code = int(module.main(argv))  # type: ignore[attr-defined]
    return Result(name, code, buffer.getvalue())


def run_all() -> list[Result]:
    """Run every gate, whatever any of them says."""
    return [run_one(name, module, argv) for name, module, argv in GATES]


def main(argv: list[str] | None = None) -> int:
    """Run the gates, print each one, and report at the end."""
    quiet = argv is not None and "--quiet" in argv
    results = run_all()
    for result in results:
        print(result)
        if not quiet or not result.passed:
            for line in result.output.splitlines():
                print(f"     {line}")
    failed = [r for r in results if not r.passed]
    if failed:
        print(f"{len(failed)} of {len(results)} gates failed: {', '.join(r.name for r in failed)}")
        return FAILED
    print(f"all {len(results)} gates pass")
    return OK


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main(sys.argv[1:]))


__all__ = ["GATES", "Result", "main", "run_all", "run_one"]
