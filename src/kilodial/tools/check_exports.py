"""Check that every module says what it exports and means it.

``__all__`` in this package is not decoration. It is the list of names another
module is allowed to import, and it drifts the moment somebody adds a helper and
forgets, or deletes one and does not. Both directions matter:

A public name missing from ``__all__`` is a name that has no stated contract,
and it will be imported anyway because it is right there.

A name in ``__all__`` that does not exist is an import error waiting for the
first person to trust the list, and nothing else in this repository catches it,
because the modules that were going to import it never did.

Sorting is checked too, on the grounds that a sorted list is one people scan and
an unsorted one is one they append to.
"""

from __future__ import annotations

import ast
import importlib
import pkgutil
import sys
from pathlib import Path
from types import ModuleType

import click

import kilodial
from kilodial.tools import FAILED, OK

# Modules that are namespace holders and export nothing on purpose.
NO_EXPORTS = frozenset(
    {
        "kilodial.model",
        "kilodial.store",
        "kilodial.testing",
        "kilodial.cli",
        "kilodial.units",
        "kilodial.xfmr",
        "kilodial.install",
        "kilodial.sampling",
        "kilodial.programme",
        "kilodial.adjust",
        "kilodial.complaint",
        "kilodial.ingest",
        "kilodial.orders",
        "kilodial.tools",
    }
)


def module_names() -> list[str]:
    """Every module in the package, in import order."""
    found = ["kilodial"]
    for info in pkgutil.walk_packages(kilodial.__path__, "kilodial."):
        found.append(info.name)
    return sorted(found)


def public_names(module: ModuleType) -> set[str]:
    """Names a module itself defines, read off its source rather than its globals.

    Reading ``vars()`` would count everything the module imported, and a plain
    constant carries nothing that says where it came from, so an imported
    integer is indistinguishable from a defined one. The source says.
    """
    source = getattr(module, "__file__", None)
    if source is None:
        return set()
    tree = ast.parse(Path(source).read_text())
    found: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.ClassDef | ast.FunctionDef):
            found.add(node.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    found.add(target.id)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            found.add(node.target.id)
    return {name for name in found if not name.startswith("_")}


def export_order(name: str) -> tuple[int, str]:
    """The order this package writes __all__ in.

    Constants first, then classes, then functions, each alphabetical. It is the
    order isort uses and the order the modules were written in, and having the
    gate agree with the habit is the only way the habit survives.
    """
    if name.isupper():
        return (0, name)
    if name[:1].isupper():
        return (1, name)
    return (2, name)


def faults_for(name: str) -> list[str]:
    """Everything wrong with one module's declared exports."""
    module = importlib.import_module(name)
    declared = getattr(module, "__all__", None)
    if declared is None:
        if name in NO_EXPORTS:
            return []
        return [f"{name} has no __all__"]
    found: list[str] = []
    if list(declared) != sorted(declared, key=export_order):
        found.append(f"{name}: __all__ is not sorted")
    for exported in declared:
        if not hasattr(module, exported):
            found.append(f"{name}: __all__ names {exported}, which is not there")
    missing = {
        name for name in public_names(module) - set(declared) if not _is_leaf_command(module, name)
    }
    for absent in sorted(missing):
        found.append(f"{name}: {absent} is public and not in __all__")
    return found


def _is_leaf_command(module: ModuleType, name: str) -> bool:
    """A click command that is not a group is not importable API.

    The command tree is assembled by decorators, so every command in a cli
    module is a module level name that nothing else will ever import. The groups
    are different: they are wired into the tree by hand and do get imported.
    """
    value = getattr(module, name, None)
    return isinstance(value, click.Command) and not isinstance(value, click.Group)


def faults() -> list[str]:
    """Everything wrong with the whole package's declared exports."""
    found: list[str] = []
    for name in module_names():
        found.extend(faults_for(name))
    return found


def main(argv: list[str] | None = None) -> int:
    """Print the export problems and say so in the exit code."""
    problems = faults()
    for problem in problems:
        print(problem)
    if problems:
        print(f"{len(problems)} export problems")
        return FAILED
    print(f"{len(module_names())} modules, every export declared and sorted")
    return OK


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())


__all__ = [
    "NO_EXPORTS",
    "export_order",
    "faults",
    "faults_for",
    "main",
    "module_names",
    "public_names",
]
