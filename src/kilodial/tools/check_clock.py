"""Check nothing in the package reads the clock behind the caller's back.

Every date in this package comes in as an argument. That is not stylistic: a
function that reads today's date cannot be tested for the day it goes wrong, and
the days it goes wrong are the interesting ones. A tolerance rule that behaves
differently on a leap day, an interval that lands on the thirty first, a
certificate that expires at the turn of a year, and a suite that runs on a
Tuesday in May will never see any of them.

So a call to ``date.today`` or ``datetime.now`` anywhere in the library is a
finding. There are exactly two places a clock reading belongs, both of them stamps on
something being written down as it happens, and both are named here.

The second check is about the timestamp that is allowed. A naive datetime is a
bug waiting for a shop in a different timezone, so the one call that is allowed
has to be timezone aware.
"""

from __future__ import annotations

import ast
import importlib
import sys
from pathlib import Path

from kilodial.tools import FAILED, OK
from kilodial.tools.check_exports import module_names

# Names that read the clock.
CLOCK = frozenset({"today", "now", "utcnow", "fromtimestamp"})

# The only module allowed to read it, with why.
ALLOWED = {
    "kilodial.store.book": "a migration ledger row is stamped when the migration runs",
    "kilodial.store.events": "an event log line is stamped when it is written",
}


def clock_calls(name: str) -> list[tuple[int, str]]:
    """Every call in a module that reads the clock, with its line."""
    module = importlib.import_module(name)
    source = getattr(module, "__file__", None)
    if source is None:
        return []
    tree = ast.parse(Path(source).read_text())
    found: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        call = node.func
        if isinstance(call, ast.Attribute) and call.attr in CLOCK:
            found.append((node.lineno, _shown(call)))
    return found


def _shown(call: ast.Attribute) -> str:
    owner = call.value
    if isinstance(owner, ast.Name):
        return f"{owner.id}.{call.attr}"
    if isinstance(owner, ast.Attribute):
        return f"{owner.attr}.{call.attr}"
    return call.attr


def is_aware(name: str, line: int) -> bool:
    """Whether the clock call on that line names a timezone."""
    module = importlib.import_module(name)
    source = getattr(module, "__file__", None)
    if source is None:
        return False
    text = Path(source).read_text().splitlines()
    return "UTC" in text[line - 1] or "timezone" in text[line - 1]


def faults() -> list[str]:
    """Every clock reading that is not allowed, and every naive one that is."""
    found: list[str] = []
    for name in module_names():
        for line, shown in clock_calls(name):
            where = f"{name}:{line}"
            if name not in ALLOWED:
                found.append(f"{where} calls {shown}, and dates come in as arguments")
            elif not is_aware(name, line):
                found.append(f"{where} calls {shown} without a timezone")
    return found


def allowed_lines() -> list[str]:
    """The clock readings that are allowed, with the reason, for the run's output."""
    return [f"{name}: {why}" for name, why in sorted(ALLOWED.items())]


def main(argv: list[str] | None = None) -> int:
    """Print every clock reading that should not be there."""
    problems = faults()
    for problem in problems:
        print(problem)
    if problems:
        print(f"{len(problems)} places read the clock when they should be told the date")
        return FAILED
    for line in allowed_lines():
        print(f"allowed: {line}")
    print(f"{len(module_names())} modules, none of them reads the clock unasked")
    return OK


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())


__all__ = [
    "ALLOWED",
    "CLOCK",
    "allowed_lines",
    "clock_calls",
    "faults",
    "is_aware",
    "main",
]
