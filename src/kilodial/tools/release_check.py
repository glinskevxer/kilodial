"""Check the things that are only wrong at release time.

Everything else in this package is checked continuously, and none of it catches
the release-shaped mistakes, because they are all about agreement between files
that no code imports from each other.

The version in three places. ``pyproject.toml`` is what pip installs,
``__init__.py`` is what the package reports about itself, and the changelog is
what a person reads. Two of the three agreeing is the normal failure and it is
invisible until somebody files a bug against a version that was never shipped.

Markers left in the source. A ``TODO`` is fine in a branch and is not fine in a
release, and neither is a skipped test or a debugging print.

The changelog having something in it for this version, and enough of it. A
release whose changelog entry is one line is one where somebody wrote "fixes"
and moved on, and the person reading it six months later needs more than that.

The versions being in order. A changelog whose entries do not descend is one
where a release was inserted in the wrong place, which is the kind of thing
nobody notices until they are looking for when something changed.
"""

from __future__ import annotations

import argparse
import importlib
import re
import sys
import tomllib
from pathlib import Path

import kilodial
from kilodial.tools import FAILED, OK
from kilodial.tools.check_exports import module_names

PYPROJECT = Path("pyproject.toml")
CHANGELOG = Path("CHANGELOG.md")

# Markers that mean the code was left mid thought.
MARKERS = ("TODO", "FIXME", "XXX", "HACK")

# The fewest bullet points a release entry can carry and still be an entry.
FEWEST_NOTES = 3

# Calls that are a debugging leftover in library code. The tools package prints
# on purpose, so it is excused by name.
DEBUG_CALLS = ("breakpoint(", "pdb.set_trace(")
PRINTS_ON_PURPOSE = "kilodial.tools"

# This module names every marker it looks for, so scanning it finds all of them
# every time. It is the only file excused and it is excused by name.
EXCUSED = "kilodial.tools.release_check"


def declared_version(path: Path = PYPROJECT) -> str:
    """The version pip will install."""
    return str(tomllib.loads(path.read_text())["project"]["version"])


def changelog_versions(path: Path = CHANGELOG) -> list[str]:
    """Every version the changelog has a heading for, newest first."""
    if not path.exists():
        return []
    return re.findall(r"^## (\d+\.\d+\.\d+)\s*$", path.read_text(), flags=re.M)


def changelog_body(version: str, path: Path = CHANGELOG) -> str:
    """What the changelog says about one version."""
    text = path.read_text() if path.exists() else ""
    found = re.search(rf"^## {re.escape(version)}\s*$(.*?)(?=^## |\Z)", text, re.M | re.S)
    return "" if found is None else found.group(1).strip()


def as_numbers(version: str) -> tuple[int, ...]:
    """A version as numbers, so two of them can be compared."""
    return tuple(int(part) for part in version.split("."))


def notes_in(version: str, path: Path = CHANGELOG) -> list[str]:
    """The bullet points a version's entry carries."""
    body = changelog_body(version, path)
    return [line.strip() for line in body.splitlines() if line.strip().startswith("- ")]


def markers_in_source() -> list[str]:
    """Every leftover marker or debugging call in the package.

    Modules are imported rather than read out of ``sys.modules``, because a
    module nobody has imported yet is exactly the one a marker survives in. An
    earlier version of this read the loaded modules and quietly scanned about a
    third of the package.
    """
    found: list[str] = []
    for name in module_names():
        if name == EXCUSED:
            continue
        module = importlib.import_module(name)
        source = getattr(module, "__file__", None)
        if source is None:
            continue
        path = Path(source)
        for number, line in enumerate(path.read_text().splitlines(), start=1):
            for marker in MARKERS:
                if marker in line:
                    found.append(f"{path.name}:{number} carries a {marker}")
            for call in DEBUG_CALLS:
                if call in line:
                    found.append(f"{path.name}:{number} calls {call}")
            if line.strip().startswith("print(") and not name.startswith(PRINTS_ON_PURPOSE):
                found.append(f"{path.name}:{number} prints from library code")
    return found


def faults(pyproject: Path = PYPROJECT, changelog: Path = CHANGELOG) -> list[str]:
    """Everything that would be wrong about cutting a release now."""
    found: list[str] = []
    declared = declared_version(pyproject)
    if kilodial.__version__ != declared:
        found.append(f"pyproject says {declared} and the package says {kilodial.__version__}")
    versions = changelog_versions(changelog)
    if not versions:
        found.append(f"{changelog} has no version headings")
    elif versions[0] != declared:
        found.append(f"the changelog leads with {versions[0]} and the version is {declared}")
    elif not changelog_body(declared, changelog):
        found.append(f"the changelog says nothing about {declared}")
    elif len(notes_in(declared, changelog)) < FEWEST_NOTES:
        found.append(
            f"the changelog gives {declared} "
            f"{len(notes_in(declared, changelog))} notes, which is not an entry"
        )
    ordered = sorted(versions, key=as_numbers, reverse=True)
    if versions != ordered:
        found.append(f"the changelog runs {versions} rather than {ordered}")
    if len(versions) != len(set(versions)):
        found.append("the changelog lists a version twice")
    found.extend(markers_in_source())
    return found


def main(argv: list[str] | None = None) -> int:
    """Print what would be wrong with a release and say so in the exit code."""
    parser = argparse.ArgumentParser(description="check the repository is releasable")
    parser.add_argument("--pyproject", type=Path, default=PYPROJECT)
    parser.add_argument("--changelog", type=Path, default=CHANGELOG)
    args = parser.parse_args(argv)
    problems = faults(args.pyproject, args.changelog)
    for problem in problems:
        print(problem)
    if problems:
        print(f"{len(problems)} things stand in the way of a release")
        return FAILED
    version = declared_version(args.pyproject)
    print(f"kilodial {version} is releasable, changelog covers {len(changelog_versions())}")
    return OK


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())


__all__ = [
    "CHANGELOG",
    "DEBUG_CALLS",
    "EXCUSED",
    "FEWEST_NOTES",
    "MARKERS",
    "PRINTS_ON_PURPOSE",
    "PYPROJECT",
    "as_numbers",
    "changelog_body",
    "changelog_versions",
    "declared_version",
    "faults",
    "main",
    "markers_in_source",
    "notes_in",
]
