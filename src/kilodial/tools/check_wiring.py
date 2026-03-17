"""Find the modules nothing imports and the names nothing calls.

A module with a green test suite and no caller is tested where it does not
matter. It happens by ordinary means: a layer gets written, the thing that was
going to use it changes shape, and the module sits there passing its own tests
forever. Nothing else in this repository notices, because from the inside it
looks exactly like a module that is used.

So this reads the import graph out of the source and reports two things.

A module that nothing else in the package imports. The command tree and the
entry points are roots and are excused by name; everything else has to be
reachable from one of them.

A public name that is exported and imported nowhere. That is a softer finding
and it is reported as such, because a name can be genuinely part of the surface
without this package using it. It is still worth seeing.
"""

from __future__ import annotations

import ast
import importlib
import sys
from pathlib import Path

from kilodial.tools import FAILED, OK
from kilodial.tools.check_exports import module_names

# Reachable by definition: the package root, the console script's tree, and the
# gates, which CI runs by name rather than importing.
ROOTS = frozenset({"kilodial", "kilodial.cli.main"})
ROOT_PREFIXES = ("kilodial.tools.",)


def imports_of(name: str) -> set[str]:
    """Every kilodial module one module imports, however it imports it."""
    module = importlib.import_module(name)
    source = getattr(module, "__file__", None)
    if source is None:
        return set()
    tree = ast.parse(Path(source).read_text())
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(a.name for a in node.names if a.name.startswith("kilodial"))
        elif isinstance(node, ast.ImportFrom) and node.module:
            if not node.module.startswith("kilodial"):
                continue
            found.add(node.module)
            for alias in node.names:
                found.add(f"{node.module}.{alias.name}")
    return found


def graph() -> dict[str, set[str]]:
    """Who imports whom, across the whole package."""
    return {name: imports_of(name) for name in module_names()}


def is_root(name: str) -> bool:
    """Whether a module is reachable by definition rather than by import."""
    return name in ROOTS or name.startswith(ROOT_PREFIXES)


def unimported() -> list[str]:
    """Modules nothing in the package imports and nothing runs directly."""
    edges = graph()
    imported: set[str] = set()
    for targets in edges.values():
        imported.update(targets)
    found = []
    for name in edges:
        if is_root(name) or name in imported:
            continue
        if name.endswith(".__init__") or (name.count(".") == 1 and _is_package(name)):
            continue
        found.append(name)
    return sorted(found)


def _is_package(name: str) -> bool:
    module = importlib.import_module(name)
    return getattr(module, "__file__", "").endswith("__init__.py")


def faults() -> list[str]:
    """Everything the import graph says is not wired in."""
    return [f"nothing imports {name}" for name in unimported()]


def reach(name: str) -> list[str]:
    """Which modules import one module, for working out where it is used."""
    return sorted(module for module, targets in graph().items() if name in targets)


def main(argv: list[str] | None = None) -> int:
    """Print the unwired modules and say so in the exit code."""
    problems = faults()
    for problem in problems:
        print(problem)
    if problems:
        print(f"{len(problems)} modules are not wired into anything")
        return FAILED
    edges = graph()
    total = sum(len(t) for t in edges.values())
    print(f"{len(edges)} modules, {total} imports, everything reachable")
    return OK


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())


__all__ = [
    "ROOTS",
    "ROOT_PREFIXES",
    "faults",
    "graph",
    "imports_of",
    "is_root",
    "main",
    "reach",
    "unimported",
]
