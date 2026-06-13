"""Check that CI actually runs the gates this repository has.

Adding a gate and forgetting to wire it into the workflow is the failure mode
this catches, and it is a quiet one: the gate exists, it is tested, it passes
locally, and it has never once run on a pull request. Nobody notices until it
would have caught something.

So the check is the other way round from the usual one. It does not verify that
the workflow is valid yaml, which the runner will say soon enough. It reads the
tools package, works out which modules are gates, and asserts that each one
appears somewhere in the workflow file.

The matrix is checked too, because a Python version this package claims to
support and does not test on is a claim nobody has evidence for.
"""

from __future__ import annotations

import pkgutil
import sys
import tomllib
from pathlib import Path

import kilodial.tools
from kilodial.tools import FAILED, OK

WORKFLOW = Path(".github/workflows/ci.yml")
PYPROJECT = Path("pyproject.toml")

# Modules in the tools package that CI does not run as a step of their own.
# ``gates`` runs the others and is for a person about to push; ``coverage_gate``
# runs in the coverage job after pytest has written its report.
RUN_ELSEWHERE = frozenset({"gates"})


def gate_names() -> list[str]:
    """Every module in the tools package that is a gate."""
    found = []
    for info in pkgutil.iter_modules(kilodial.tools.__path__):
        if info.name.startswith("_"):
            continue
        found.append(info.name)
    return sorted(found)


def supported_versions(path: Path = PYPROJECT) -> list[str]:
    """The Python versions the project says it supports, oldest first."""
    data = tomllib.loads(path.read_text())
    floor = str(data["project"]["requires-python"]).lstrip(">=").strip()
    major, minor = (int(part) for part in floor.split(".")[:2])
    return [f"{major}.{minor}", f"{major}.{minor + 1}"]


def faults(workflow: Path = WORKFLOW, pyproject: Path = PYPROJECT) -> list[str]:
    """Everything the workflow does not run that it should."""
    if not workflow.exists():
        return [f"there is no workflow at {workflow}"]
    text = workflow.read_text()
    found: list[str] = []
    for name in gate_names():
        if name in RUN_ELSEWHERE:
            continue
        wanted = f"kilodial.tools.{name}"
        if wanted not in text:
            found.append(f"the workflow never runs {wanted}")
    for version in supported_versions(pyproject):
        if f'"{version}"' not in text:
            found.append(f"the workflow never tests on python {version}")
    for step in ("ruff check", "ruff format --check", "mypy", "pytest"):
        if step not in text:
            found.append(f"the workflow never runs {step}")
    if "python -m build" not in text:
        found.append("the workflow never builds a wheel")
    return found


def main(argv: list[str] | None = None) -> int:
    """Print what CI is not running and say so in the exit code."""
    problems = faults()
    for problem in problems:
        print(problem)
    if problems:
        print(f"{len(problems)} things CI does not run")
        return FAILED
    gates = gate_names()
    print(f"the workflow runs all {len(gates)} gates on {supported_versions()}")
    return OK


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())


__all__ = [
    "PYPROJECT",
    "RUN_ELSEWHERE",
    "WORKFLOW",
    "faults",
    "gate_names",
    "main",
    "supported_versions",
]
