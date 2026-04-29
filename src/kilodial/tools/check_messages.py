"""Check the error messages read the way this package's error messages read.

Every message a person sees from this tool comes out of a raise. They were
written one at a time over a long stretch and they drift, which shows up as a
tool that sounds like four different programs depending on which command you
happen to run.

The house style is short and it is not arbitrary:

Lower case at the start. The message is appended to nothing and prefixed by
nothing, so a capital reads as the beginning of a sentence that never finishes.

No full stop at the end. Same reason from the other side.

There was a third check and it is worth saying why it is not here. It asked that
every message name a record, on the grounds that "the standard was out of
certificate" is less useful than naming which standard. Run against the package
it produced a hundred and forty seven findings, and reading them showed the rule
was wrong rather than the messages: most of them describe a rule being broken
rather than a record breaking it, and "a rolling demand register averages two or
more subintervals" has nothing to name. Satisfying the check would have meant an
exemption list longer than the check, which is the shape of a rule that has
stopped being a rule.

So what is left is the two checks that are objective. Style rules that need a
hundred exceptions are opinions, and opinions do not belong in CI.
"""

from __future__ import annotations

import ast
import importlib
import sys
from pathlib import Path

from kilodial.tools import FAILED, OK
from kilodial.tools.check_exports import module_names


def messages_in(name: str) -> list[tuple[int, str, bool]]:
    """Every literal error message a module raises, with whether it interpolates."""
    module = importlib.import_module(name)
    source = getattr(module, "__file__", None)
    if source is None:
        return []
    tree = ast.parse(Path(source).read_text())
    found: list[tuple[int, str, bool]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Raise) or node.exc is None:
            continue
        call = node.exc
        if not isinstance(call, ast.Call) or not call.args:
            continue
        first = call.args[0]
        if isinstance(first, ast.Constant) and isinstance(first.value, str):
            found.append((node.lineno, first.value, False))
        elif isinstance(first, ast.JoinedStr):
            text = "".join(
                part.value
                for part in first.values
                if isinstance(part, ast.Constant) and isinstance(part.value, str)
            )
            found.append((node.lineno, text, True))
    return found


def faults_for(name: str) -> list[str]:
    """Everything off style about one module's messages."""
    module = importlib.import_module(name)
    where = Path(getattr(module, "__file__", name)).name
    found: list[str] = []
    for line, text, _ in messages_in(name):
        stripped = text.strip()
        if not stripped:
            continue
        if stripped[0].isupper() and not stripped.split()[0].isupper():
            found.append(f"{where}:{line} starts with a capital: {stripped!r}")
        if stripped.endswith("."):
            found.append(f"{where}:{line} ends in a full stop: {stripped!r}")
    return found


def faults() -> list[str]:
    """Everything off style across the package."""
    found: list[str] = []
    for name in module_names():
        found.extend(faults_for(name))
    return found


def counts() -> int:
    """How many raised messages the package carries."""
    return sum(len(messages_in(name)) for name in module_names())


def main(argv: list[str] | None = None) -> int:
    """Print the messages that read wrong and say so in the exit code."""
    problems = faults()
    for problem in problems:
        print(problem)
    if problems:
        print(f"{len(problems)} messages do not read the way the rest do")
        return FAILED
    print(f"{counts()} raised messages, all of them in the house style")
    return OK


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())


__all__ = ["counts", "faults", "faults_for", "main", "messages_in"]
