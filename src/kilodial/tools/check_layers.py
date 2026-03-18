"""Check the package still layers the way it was built to.

This codebase has a direction to it. The units know nothing about the model, the
model knows nothing about storage, storage knows nothing about the command line,
and the gates sit outside all of it. That is not a preference: it is what makes
the domain testable without a database and what stops a rule about tolerance
bands ending up in a repository.

Layering rots quietly. Somebody needs a lookup in a model method, imports a
repository, and nothing complains, because the import works and the tests pass.
By the time it is noticed there are six of them.

So the layers are written down and every import is checked against them. A
module may import from its own layer or from any layer below it, and nothing
else. Where a package spans two layers, the exceptions are named individually,
because a package that needs an exception is usually one that wants splitting
and naming the exception is how that stays visible.
"""

from __future__ import annotations

import sys
from pathlib import Path

from kilodial.tools import FAILED, OK
from kilodial.tools.check_exports import module_names
from kilodial.tools.check_wiring import graph

# Lowest first. A module may import from its own rank or anything below it.
LAYERS: tuple[tuple[str, ...], ...] = (
    ("kilodial.errors", "kilodial.units"),
    ("kilodial.model", "kilodial.xfmr"),
    (
        "kilodial.testing",
        "kilodial.install",
        "kilodial.sampling",
        "kilodial.tamper",
        "kilodial.orders.order",
        "kilodial.complaint.request",
        "kilodial.adjust.rules",
        "kilodial.adjust.period",
        "kilodial.adjust.compute",
        "kilodial.estimate.basis",
        "kilodial.ingest.sheet",
        "kilodial.report.document",
        "kilodial.report.layout",
    ),
    ("kilodial.store",),
    (
        "kilodial.programme",
        "kilodial.adjust.service",
        "kilodial.complaint.service",
        "kilodial.estimate.service",
        "kilodial.orders.planner",
        "kilodial.ingest",
        "kilodial.report",
    ),
    ("kilodial.cli",),
    ("kilodial.tools",),
)

# Where the layering would be bent, with why. Empty, and the intention is that
# it stays that way: the last entry in it was the report document reaching up
# into the command line for its table layout, and the fix was to move the layout
# down rather than to write the exception down.
EXCEPTIONS: dict[str, set[str]] = {}

DOCS = Path("docs/layers.md")


def rank_of(name: str) -> int:
    """Which layer a module sits in, deepest prefix wins."""
    best = (-1, -1)
    for rank, prefixes in enumerate(LAYERS):
        for prefix in prefixes:
            matches = name == prefix or name.startswith(f"{prefix}.")
            if matches and len(prefix) > best[1]:
                best = (rank, len(prefix))
    return best[0]


def module_only(name: str) -> str:
    """Trim an imported name back to the module it came from.

    An ``from x.y import z`` records both ``x.y`` and ``x.y.z``, and the second
    is not a module. Trimming by rank would not catch it, because the trimmed and
    untrimmed names sit in the same layer, so the module list decides.
    """
    known = set(module_names())
    while name and name not in known and "." in name:
        name = name.rsplit(".", 1)[0]
    return name


def faults() -> list[str]:
    """Every import that points at a higher layer than its own."""
    found: list[str] = []
    for source, targets in sorted(graph().items()):
        here = rank_of(source)
        if here < 0:
            continue
        allowed = EXCEPTIONS.get(source, set())
        for raw in sorted(targets):
            target = module_only(raw)
            if target in allowed or target == source:
                continue
            there = rank_of(target)
            if there > here:
                found.append(f"{source} (layer {here}) imports {target} (layer {there})")
    return sorted(set(found))


def table() -> list[str]:
    """The layer map as markdown, for the docs."""
    lines = [
        "# kilodial layers",
        "",
        "Generated from the import graph. Do not edit by hand.",
        "Rebuild with: python -m kilodial.tools.check_layers --write",
        "",
        "A module may import from its own layer or any layer below it.",
        "",
    ]
    for rank, prefixes in enumerate(LAYERS):
        lines.append(f"## Layer {rank}")
        lines.append("")
        for prefix in sorted(prefixes):
            lines.append(f"- `{prefix}`")
        lines.append("")
    if EXCEPTIONS:
        lines.append("## Exceptions")
        lines.append("")
        for source, targets in sorted(EXCEPTIONS.items()):
            for target in sorted(targets):
                lines.append(f"- `{source}` imports `{target}`")
        lines.append("")
    return lines


def write(path: Path = DOCS) -> Path:
    """Write the layer map out."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(table()) + "\n")
    return path


def main(argv: list[str] | None = None) -> int:
    """Check the layering, and write the map when asked."""
    if argv is not None and "--write" in argv:
        print(f"wrote {write()}")
        return OK
    problems = faults()
    for problem in problems:
        print(problem)
    if problems:
        print(f"{len(problems)} imports point the wrong way")
        return FAILED
    print(f"{len(LAYERS)} layers, every import points down or sideways")
    return OK


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main(sys.argv[1:]))


__all__ = [
    "DOCS",
    "EXCEPTIONS",
    "LAYERS",
    "faults",
    "main",
    "module_only",
    "rank_of",
    "table",
    "write",
]
