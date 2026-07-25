"""Check the readme still describes this package.

A readme is the one file in a repository that nothing tests and everything
depends on, and it goes stale in three specific ways that are all checkable:

It links to files that have been moved or renamed. Every relative link in there
points at something in this repository, so every one of them can be resolved.

It shows commands that no longer exist. The worked example is the first thing
anybody types, and a readme whose first command is wrong is worse than one with
no example in it.

It names a version that is not this one. The readme is what somebody reads
before installing, and a version in it that pip will not install is a support
question waiting to happen.

What it does not check is whether the prose is any good, which is not something
a program can be told to look at.
"""

from __future__ import annotations

import re
import shlex
import sys
from pathlib import Path

import click

from kilodial import __version__
from kilodial.cli.main import cli
from kilodial.tools import FAILED, OK

README = Path("README.md")

LINK = re.compile(r"\[[^\]]+\]\(([^)#][^)]*)\)")
COMMAND = re.compile(r"^\s{4}kilodial (.+)$", re.M)
VERSION = re.compile(r"\b\d+\.\d+\.\d+\b")


def links(path: Path = README) -> list[str]:
    """Every relative link the readme carries."""
    return [
        target
        for target in LINK.findall(path.read_text())
        if not target.startswith(("http://", "https://", "mailto:"))
    ]


def commands(path: Path = README) -> list[str]:
    """Every kilodial command line the readme shows.

    A shell continuation is joined first, because a readme that shows a long
    command on one line is a readme nobody can copy out of.
    """
    text = path.read_text().replace("\\\n", " ")
    return [" ".join(line.split()) for line in COMMAND.findall(text)]


def resolves(line: str) -> bool:
    """Whether a command line names a command in the tree.

    Only the leading words are command names. Everything after the first thing
    that is not one is an argument, so the walk stops at the leaf rather than
    trying to look a meter serial up as a subcommand.
    """
    node: click.Command = cli
    for part in shlex.split(line):
        if not isinstance(node, click.Group):
            return True
        if part.startswith("-"):
            return False
        if part not in node.commands:
            return False
        node = node.commands[part]
    return not isinstance(node, click.Group)


def versions(path: Path = README) -> list[str]:
    """Every version-shaped string in the readme."""
    return VERSION.findall(path.read_text())


def faults(path: Path = README) -> list[str]:
    """Everything about the readme that has gone stale."""
    if not path.exists():
        return [f"there is no readme at {path}"]
    found: list[str] = []
    for target in links(path):
        if not Path(target).exists():
            found.append(f"the readme links to {target}, which is not there")
    for line in commands(path):
        if not resolves(line):
            found.append(f"the readme shows 'kilodial {line}', which is not a command")
    for version in versions(path):
        if version != __version__:
            found.append(f"the readme names version {version} and this is {__version__}")
    return found


def main(argv: list[str] | None = None) -> int:
    """Print what has gone stale in the readme and say so in the exit code."""
    problems = faults()
    for problem in problems:
        print(problem)
    if problems:
        print(f"{len(problems)} things in the readme no longer describe this package")
        return FAILED
    print(
        f"{len(links())} links and {len(commands())} command lines in the readme, all of them real"
    )
    return OK


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())


__all__ = [
    "COMMAND",
    "LINK",
    "README",
    "VERSION",
    "commands",
    "faults",
    "links",
    "main",
    "resolves",
    "versions",
]
