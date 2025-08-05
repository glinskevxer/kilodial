"""Check that the things that need explaining have an explanation.

Not everything needs a docstring and a gate that demands one everywhere gets
satisfied with "Returns the serial." on ``serial()``, which is worse than
nothing. So this one asks for three specific things:

Every module has one, because a module is where the reason for the whole file
goes and there is nowhere else to put it.

Every public class has one, because a class is a decision about how something is
modelled and the decision is never obvious from the field names.

Every module level public function has one, whatever its length, because a
module level function is part of the package's surface and somebody will call it
without reading it.

Methods are exempt, and that is the choice that keeps this gate useful rather
than merely obeyed. A repository's ``exists`` and ``get`` are the same six
methods on fourteen classes, and requiring a sentence on each of them buys a
hundred lines of "Return whether it exists" and teaches nobody anything. The
class docstring says what the class is for; the methods that do something
surprising get a docstring because they are surprising, not because a gate asked.
"""

from __future__ import annotations

import ast
import importlib
import sys
from pathlib import Path

from kilodial.tools import FAILED, OK
from kilodial.tools.check_exports import module_names

# A function shorter than this explains itself.
SHORT_ENOUGH = 4


def _length(node: ast.FunctionDef | ast.ClassDef) -> int:
    end = getattr(node, "end_lineno", node.lineno)
    return (end or node.lineno) - node.lineno + 1


def faults_for(name: str) -> list[str]:
    """Everything one module leaves unexplained."""
    module = importlib.import_module(name)
    source = getattr(module, "__file__", None)
    if source is None:
        return [f"{name} has no source"]
    text = Path(source).read_text()
    tree = ast.parse(text)
    found: list[str] = []
    if not ast.get_docstring(tree):
        found.append(f"{name} has no module docstring")
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            if not node.name.startswith("_") and not ast.get_docstring(node):
                found.append(f"{name}: class {node.name} has no docstring")
        elif isinstance(node, ast.FunctionDef):
            if node.name.startswith("_") or _is_command(node):
                continue
            if not ast.get_docstring(node):
                found.append(
                    f"{name}: {node.name} at line {node.lineno} runs "
                    f"{_length(node)} lines with no docstring"
                )
    return found


def _is_command(node: ast.FunctionDef) -> bool:
    """A click command callback carries its help text as its docstring already."""
    return any(
        isinstance(d, ast.Call)
        and isinstance(d.func, ast.Attribute)
        and d.func.attr in ("command", "group")
        for d in node.decorator_list
    )


def faults() -> list[str]:
    """Everything the whole package leaves unexplained."""
    found: list[str] = []
    for name in module_names():
        found.extend(faults_for(name))
    return found


def counts() -> tuple[int, int]:
    """How many modules were read and how many docstrings they carry."""
    modules = module_names()
    written = 0
    for name in modules:
        module = importlib.import_module(name)
        source = getattr(module, "__file__", None)
        if source is None:
            continue
        tree = ast.parse(Path(source).read_text())
        written += sum(
            1
            for node in ast.walk(tree)
            if isinstance(node, ast.ClassDef | ast.FunctionDef | ast.Module)
            and ast.get_docstring(node)
        )
    return (len(modules), written)


def main(argv: list[str] | None = None) -> int:
    """Print what wants explaining and say so in the exit code."""
    problems = faults()
    for problem in problems:
        print(problem)
    if problems:
        print(f"{len(problems)} things want explaining")
        return FAILED
    modules, written = counts()
    print(f"{modules} modules carrying {written} docstrings, nothing unexplained")
    return OK


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())


__all__ = ["SHORT_ENOUGH", "counts", "faults", "faults_for", "main"]
