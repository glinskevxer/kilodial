"""Check every module has a test file, and that the file is not a stub.

Coverage says which lines ran. It does not say which module has tests of its
own, and the difference matters: a module can sit at ninety percent because
something else exercises it in passing, with nothing anywhere that says what it
is supposed to do. The first person to change it has no statement of intent to
work from.

So this maps each module to the test file that should carry its own tests, and
checks two things: that the file is there, and that it has more than a token
number of tests in it. The second check is the one with judgement in it, and the
threshold is deliberately low. It is there to catch a file created to satisfy
the first check, not to argue about how many tests a module deserves.

Namespace modules are exempt, because a package's ``__init__`` that only
re-exports has nothing of its own to test.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

from kilodial.tools import FAILED, OK
from kilodial.tools.check_exports import NO_EXPORTS, module_names

SOURCE = Path("src/kilodial")
TESTS = Path("tests")

# A test file with fewer than this many tests in it is a placeholder.
FEWEST_TESTS = 3

# Modules whose tests live somewhere else, with where.
ELSEWHERE = {
    "kilodial.cli.context": "tests/cli/test_main.py",
    "kilodial.cli.doctor": "tests/cli/test_doctor.py",
    "kilodial.cli.estimate": "tests/cli/test_estimate.py",
    "kilodial.cli.groups": "tests/cli/test_groups.py",
    "kilodial.cli.installs": "tests/cli/test_installs.py",
    "kilodial.model.form": "tests/model/test_form.py",
    "kilodial.programme.roster": "tests/programme/test_roster.py",
}


def test_path_for(name: str) -> Path:
    """Where a module's own tests should live."""
    if name in ELSEWHERE:
        return Path(ELSEWHERE[name])
    parts = name.split(".")[1:]
    if not parts:
        return TESTS / "test_errors.py"
    leaf = f"test_{parts[-1]}.py"
    return TESTS.joinpath(*parts[:-1], leaf)


def test_count(path: Path) -> int:
    """How many test functions a file carries."""
    if not path.exists():
        return 0
    tree = ast.parse(path.read_text())
    return sum(
        1
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name.startswith("test_")
    )


def faults() -> list[str]:
    """Every module without tests of its own."""
    found: list[str] = []
    for name in module_names():
        if name in NO_EXPORTS or name == "kilodial":
            continue
        path = test_path_for(name)
        if not path.exists():
            found.append(f"{name} has no tests of its own, expected {path}")
            continue
        count = test_count(path)
        if count < FEWEST_TESTS:
            found.append(f"{path} carries {count} tests, which is not a test file")
    return found


def counts() -> dict[str, int]:
    """How many tests each module's file carries, for a person to read."""
    return {
        name: test_count(test_path_for(name))
        for name in module_names()
        if name not in NO_EXPORTS and name != "kilodial"
    }


def main(argv: list[str] | None = None) -> int:
    """Print the modules with no tests of their own and say so in the exit code."""
    problems = faults()
    for problem in problems:
        print(problem)
    if problems:
        print(f"{len(problems)} modules have no tests of their own")
        return FAILED
    found = counts()
    print(f"{len(found)} modules, {sum(found.values())} tests written against them")
    return OK


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())


__all__ = [
    "ELSEWHERE",
    "FEWEST_TESTS",
    "SOURCE",
    "TESTS",
    "counts",
    "faults",
    "main",
    "test_count",
    "test_path_for",
]
