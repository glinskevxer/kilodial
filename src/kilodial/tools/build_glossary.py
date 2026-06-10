"""Write the domain's vocabulary out of the code that defines it.

A meter shop has a vocabulary and half of it means something specific here that
it does not mean elsewhere. A run is not a program run. A group is a population,
not a set of people. As left is a state of a record and not a description of
where a meter is. Somebody arriving at this codebase has to learn twenty of
these before anything else reads properly.

The glossary is generated from the classes rather than written beside them,
because a hand written one describes what the code did when somebody last looked
at it. Each entry is a class, the package it lives in, and the first line of its
docstring, which the docstring gate already guarantees exists.

Enum members are included with their own labels, because half the vocabulary is
in them: void and suspect are the words that matter about a verdict, and neither
of them is a class.
"""

from __future__ import annotations

import argparse
import ast
import importlib
import inspect
import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from kilodial.tools import FAILED, OK
from kilodial.tools.check_exports import module_names

DEFAULT_PATH = Path("docs/glossary.md")

# The packages whose vocabulary is the domain's. The store and the command line
# name mechanisms rather than things a meter reader would recognise.
DOMAIN = (
    "kilodial.model",
    "kilodial.units",
    "kilodial.xfmr",
    "kilodial.install",
    "kilodial.testing",
    "kilodial.sampling",
    "kilodial.programme",
    "kilodial.adjust",
    "kilodial.complaint",
    "kilodial.tamper",
    "kilodial.orders",
    "kilodial.estimate",
)


@dataclass(frozen=True)
class Term:
    """One word in the vocabulary, and where it is defined."""

    name: str
    module: str
    summary: str
    members: tuple[str, ...]

    @property
    def area(self) -> str:
        """The package the term belongs to, which is how the glossary groups."""
        return self.module.split(".")[1]

    def lines(self) -> list[str]:
        out = [f"### {self.name}", "", self.summary, ""]
        if self.members:
            out.append("Values: " + ", ".join(f"`{m}`" for m in self.members))
            out.append("")
        out.append(f"Defined in `{self.module}`.")
        out.append("")
        return out


def is_domain(name: str) -> bool:
    """Whether a module carries domain vocabulary."""
    return any(name == p or name.startswith(f"{p}.") for p in DOMAIN)


def members_of(value: type) -> tuple[str, ...]:
    """An enum's member labels, or nothing when it is not an enum."""
    if not (inspect.isclass(value) and issubclass(value, Enum)):
        return ()
    found = []
    for member in value:
        label = getattr(member, "label", None) or getattr(member, "code", None)
        found.append(str(label) if label is not None else str(member.value))
    return tuple(found)


def terms() -> list[Term]:
    """Every public class in the domain packages, alphabetically."""
    found: list[Term] = []
    for name in module_names():
        if not is_domain(name):
            continue
        module = importlib.import_module(name)
        source = getattr(module, "__file__", None)
        if source is None:
            continue
        tree = ast.parse(Path(source).read_text())
        for node in tree.body:
            if not isinstance(node, ast.ClassDef) or node.name.startswith("_"):
                continue
            summary = (ast.get_docstring(node) or "").strip().splitlines()
            value = getattr(module, node.name, None)
            found.append(
                Term(
                    name=node.name,
                    module=name,
                    summary=summary[0] if summary else "",
                    members=members_of(value) if isinstance(value, type) else (),
                )
            )
    return sorted(found, key=lambda t: (t.area, t.name))


def build() -> str:
    """The glossary as markdown."""
    lines = [
        "# kilodial glossary",
        "",
        "Generated from the classes that define these things.",
        "Rebuild with: python -m kilodial.tools.build_glossary",
        "",
    ]
    area = ""
    for term in terms():
        if term.area != area:
            area = term.area
            lines.extend([f"## {area}", ""])
        lines.extend(term.lines())
    return "\n".join(lines).rstrip() + "\n"


def write(path: Path = DEFAULT_PATH) -> Path:
    """Write the glossary out."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(build())
    return path


def differences(path: Path = DEFAULT_PATH) -> list[str]:
    """How the glossary on disk differs from the code."""
    if not path.exists():
        return [f"there is no glossary at {path}"]
    on_disk = path.read_text().splitlines()
    wanted = build().splitlines()
    if on_disk == wanted:
        return []
    found = [f"{path} is {len(on_disk)} lines and the code makes {len(wanted)}"]
    for index, (was, now) in enumerate(zip(on_disk, wanted, strict=False), start=1):
        if was != now:
            found.append(f"line {index}: {was!r} should be {now!r}")
            break
    return found


def main(argv: list[str] | None = None) -> int:
    """Write the glossary, or check it and fail when it has gone stale."""
    parser = argparse.ArgumentParser(description="build or check the glossary")
    parser.add_argument("--path", type=Path, default=DEFAULT_PATH)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    if not args.check:
        written = write(args.path)
        print(f"wrote {written} with {len(terms())} terms")
        return OK
    problems = differences(args.path)
    for problem in problems:
        print(problem)
    if problems:
        print("run python -m kilodial.tools.build_glossary to bring it up to date")
        return FAILED
    print(f"{args.path} matches the {len(terms())} terms in the code")
    return OK


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())


__all__ = [
    "DEFAULT_PATH",
    "DOMAIN",
    "Term",
    "build",
    "differences",
    "is_domain",
    "main",
    "members_of",
    "terms",
    "write",
]
