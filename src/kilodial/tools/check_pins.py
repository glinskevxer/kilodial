"""Check the dependencies are pinned exactly and the constraints agree.

A range in a dependency specifier is a promise that every future release inside
it will work, and nobody making that promise has tested it. This package pins
exactly, and the point of the check is that an exact pin is easy to relax by
accident when somebody is bumping a version.

The constraints file is the closure: the direct pins plus everything they pull
in. It exists because a build in six months should install what a build today
installs, and a patch release of a transitive dependency is exactly the thing
that breaks a CI run nobody changed.

Two checks. Every specifier in pyproject is an ``==``, and every direct pin
appears in the constraints file at the same version. The constraints file is
allowed to carry more than the direct pins, because that is what a closure is.
"""

from __future__ import annotations

import re
import sys
import tomllib
from pathlib import Path

from kilodial.tools import FAILED, OK

PYPROJECT = Path("pyproject.toml")
CONSTRAINTS = Path("constraints.txt")

SPECIFIER = re.compile(r"^([A-Za-z0-9._-]+)\s*(==|>=|<=|~=|>|<|!=)?\s*(.*)$")


def direct(path: Path = PYPROJECT) -> dict[str, tuple[str, str]]:
    """Every dependency pyproject names, as name to operator and version."""
    data = tomllib.loads(path.read_text())
    project = data["project"]
    named = list(project.get("dependencies", []))
    for extra in project.get("optional-dependencies", {}).values():
        named.extend(extra)
    found: dict[str, tuple[str, str]] = {}
    for line in named:
        match = SPECIFIER.match(line.strip())
        if match is None:
            continue
        name, operator, version = match.groups()
        found[_normal(name)] = (operator or "", version)
    return found


def pinned(path: Path = CONSTRAINTS) -> dict[str, str]:
    """Every version the constraints file pins."""
    if not path.exists():
        return {}
    found: dict[str, str] = {}
    for line in path.read_text().splitlines():
        text = line.split("#", 1)[0].strip()
        if not text or "==" not in text:
            continue
        name, version = text.split("==", 1)
        found[_normal(name)] = version.strip()
    return found


def _normal(name: str) -> str:
    """Package names compare with dashes and underscores treated the same."""
    return name.strip().lower().replace("_", "-")


def faults(pyproject: Path = PYPROJECT, constraints: Path = CONSTRAINTS) -> list[str]:
    """Every dependency that is not pinned or does not agree."""
    found: list[str] = []
    if not constraints.exists():
        return [f"there is no constraints file at {constraints}"]
    closure = pinned(constraints)
    for name, (operator, version) in sorted(direct(pyproject).items()):
        if operator != "==":
            found.append(f"{name} is specified as {operator or 'a bare name'}, not ==")
            continue
        if name not in closure:
            found.append(f"{name} is pinned at {version} and is not in {constraints}")
        elif closure[name] != version:
            found.append(f"{name} is {version} in {pyproject} and {closure[name]} in {constraints}")
    return found


def build_requires(path: Path = PYPROJECT) -> list[str]:
    """The build system's own requirements, which are pinned the same way."""
    data = tomllib.loads(path.read_text())
    return list(data.get("build-system", {}).get("requires", []))


def main(argv: list[str] | None = None) -> int:
    """Print every dependency that is not pinned and say so in the exit code."""
    problems = faults()
    for requirement in build_requires():
        if "==" not in requirement:
            problems.append(f"the build requirement {requirement} is not pinned")
    for problem in problems:
        print(problem)
    if problems:
        print(f"{len(problems)} dependencies are not pinned the way they should be")
        return FAILED
    print(f"{len(direct())} direct dependencies pinned exactly, {len(pinned())} in the closure")
    return OK


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())


__all__ = [
    "CONSTRAINTS",
    "PYPROJECT",
    "SPECIFIER",
    "build_requires",
    "direct",
    "faults",
    "main",
    "pinned",
]
