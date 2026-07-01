"""Check what the wheel will contain before anybody installs it.

The tests all run against the source tree, so every one of them passes on a
package that ships nothing. The things that go wrong at install time are a
narrow set and none of the rest of this suite can see them:

The type marker. A package without ``py.typed`` is one whose annotations a
consumer's type checker ignores entirely, and nothing about it looks wrong.

The console script. An entry point naming a function that has moved installs
fine and fails the first time somebody types the command.

What is shipped. Tests, the gates' own fixtures and the docs do not belong in a
wheel, and the way they get in is a packaging config that says to include
everything under the project root.

The build backend's own pin. A wheel built with whatever hatchling happened to
be current is not the wheel that was tested.
"""

from __future__ import annotations

import importlib
import sys
import tomllib
from pathlib import Path
from typing import Any

import kilodial
from kilodial.tools import FAILED, OK

PYPROJECT = Path("pyproject.toml")
MARKER = "py.typed"


def config(path: Path = PYPROJECT) -> dict[str, Any]:
    """The whole pyproject, parsed."""
    return dict(tomllib.loads(path.read_text()))


def packaged_roots(path: Path = PYPROJECT) -> list[str]:
    """The directories the wheel is built from."""
    data = config(path)
    tool = data.get("tool", {})
    wheel = tool.get("hatch", {}).get("build", {}).get("targets", {}).get("wheel", {})
    return list(wheel.get("packages", []))


def scripts(path: Path = PYPROJECT) -> dict[str, str]:
    """The console scripts the wheel declares."""
    return dict(config(path).get("project", {}).get("scripts", {}))


def marker_path() -> Path:
    """Where the type marker sits in the source tree."""
    return Path(kilodial.__file__).parent / MARKER


def resolves(target: str) -> bool:
    """Whether an entry point target names something that is there."""
    module, _, attribute = target.partition(":")
    try:
        found = importlib.import_module(module)
    except ImportError:
        return False
    return hasattr(found, attribute)


def faults(path: Path = PYPROJECT) -> list[str]:
    """Everything wrong with what the wheel would contain."""
    found: list[str] = []
    if not marker_path().exists():
        found.append(f"there is no {MARKER} beside the package, so it ships untyped")
    roots = packaged_roots(path)
    if roots != ["src/kilodial"]:
        found.append(f"the wheel is built from {roots}, not from src/kilodial alone")
    for root in roots:
        if "test" in root:
            found.append(f"the wheel would ship {root}")
    declared = scripts(path)
    if not declared:
        found.append("the wheel declares no console script")
    for name, target in sorted(declared.items()):
        if not resolves(target):
            found.append(f"the {name} script points at {target}, which is not there")
    for requirement in config(path).get("build-system", {}).get("requires", []):
        if "==" not in str(requirement):
            found.append(f"the build backend {requirement} is not pinned")
    return found


def contents() -> list[str]:
    """What sits beside the package, for the run's own output."""
    root = Path(kilodial.__file__).parent
    return sorted(p.name for p in root.iterdir() if not p.name.startswith("__"))


def main(argv: list[str] | None = None) -> int:
    """Print what is wrong with the packaging and say so in the exit code."""
    problems = faults()
    for problem in problems:
        print(problem)
    if problems:
        print(f"{len(problems)} things wrong with what the wheel would contain")
        return FAILED
    print(
        f"{len(contents())} entries under the package, {MARKER} present, "
        f"{len(scripts())} console script resolves"
    )
    return OK


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())


__all__ = [
    "MARKER",
    "PYPROJECT",
    "config",
    "contents",
    "faults",
    "main",
    "marker_path",
    "packaged_roots",
    "resolves",
    "scripts",
]
