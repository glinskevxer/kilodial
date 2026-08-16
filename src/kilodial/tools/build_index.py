"""Write the index of the generated documentation.

Four files under docs are generated from the code and one more is a schema dump.
Each of them says at its top how to rebuild it, which is fine once you have
opened it and no use at all when you are standing outside the directory
wondering what is in there.

So this writes the index, from the same list the other tools are registered
under. A generated document added without a line here fails the check, which is
the point: the index is only worth having if it cannot go stale.

It is the smallest tool in the package and the last one written, which is about
right for an index.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

from kilodial import __version__
from kilodial.tools import FAILED, OK

DEFAULT_PATH = Path("docs/README.md")


@dataclass(frozen=True)
class Document:
    """One generated document, what is in it, and how to rebuild it."""

    path: str
    title: str
    holds: str
    tool: str

    @property
    def command(self) -> str:
        return f"python -m kilodial.tools.{self.tool}"

    def lines(self) -> list[str]:
        return [
            f"### [{self.title}]({Path(self.path).name})",
            "",
            self.holds,
            "",
            f"    {self.command}",
            "",
        ]


DOCUMENTS: tuple[Document, ...] = (
    Document(
        "docs/commands.md",
        "Command reference",
        "Every command in the tree, its arguments and its options, read off the "
        "command tree itself.",
        "build_docs",
    ),
    Document(
        "docs/schema.sql",
        "Schema",
        "The whole book as one flat file, built by running every migration into "
        "an empty database and asking sqlite what came out.",
        "schema_dump",
    ),
    Document(
        "docs/glossary.md",
        "Glossary",
        "The domain's vocabulary, taken from the classes that define it. Start "
        "here if a word in the code does not mean what it means elsewhere.",
        "build_glossary",
    ),
    Document(
        "docs/layers.md",
        "Layers",
        "Which package may import which, and the direction the whole thing points in.",
        "check_layers --write",
    ),
)


def missing() -> list[str]:
    """Documents the index names that are not on disk."""
    return [d.path for d in DOCUMENTS if not Path(d.path).exists()]


def unlisted() -> list[str]:
    """Files under docs that the index does not name."""
    known = {d.path for d in DOCUMENTS} | {str(DEFAULT_PATH)}
    root = Path("docs")
    if not root.exists():
        return []
    return sorted(str(p) for p in root.iterdir() if str(p) not in known)


def build() -> str:
    """The index as markdown."""
    lines = [
        "# kilodial documentation",
        "",
        f"Generated for kilodial {__version__}. Do not edit by hand.",
        "Rebuild with: python -m kilodial.tools.build_index",
        "",
        "Everything in this directory is generated from the code, so nothing in "
        "it can describe a version of this package that never existed.",
        "",
        "## Documents",
        "",
    ]
    for document in DOCUMENTS:
        lines.extend(document.lines())
    lines.extend(
        [
            "## Rebuilding all of them",
            "",
            "    python -m kilodial.tools.gates",
            "",
            "checks every one of these is current, along with the rest of the "
            "gates. It does not rewrite them; each tool above does that.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def write(path: Path = DEFAULT_PATH) -> Path:
    """Write the index out."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(build())
    return path


def differences(path: Path = DEFAULT_PATH) -> list[str]:
    """How the index on disk differs from the list, plus anything unlisted."""
    found = [f"docs/{Path(name).name} is not in the index" for name in unlisted()]
    found.extend(f"the index names {name}, which is not there" for name in missing())
    if not path.exists():
        found.append(f"there is no index at {path}")
        return found
    if path.read_text() != build():
        found.append(f"{path} is not what the list builds")
    return found


def main(argv: list[str] | None = None) -> int:
    """Write the index, or check it and fail when it has gone stale."""
    parser = argparse.ArgumentParser(description="build or check the docs index")
    parser.add_argument("--path", type=Path, default=DEFAULT_PATH)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    if not args.check:
        written = write(args.path)
        print(f"wrote {written} listing {len(DOCUMENTS)} documents")
        return OK
    problems = differences(args.path)
    for problem in problems:
        print(problem)
    if problems:
        print("run python -m kilodial.tools.build_index to bring it up to date")
        return FAILED
    print(f"{args.path} lists all {len(DOCUMENTS)} generated documents")
    return OK


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())


__all__ = [
    "DEFAULT_PATH",
    "DOCUMENTS",
    "Document",
    "build",
    "differences",
    "main",
    "missing",
    "unlisted",
    "write",
]
