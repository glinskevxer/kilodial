"""Write the command reference out of the command tree itself.

A hand written command reference is wrong within a month. This one is generated
by walking the click tree and reading the help text that is already there, so
the only way for it to be wrong is for a command's own help to be wrong, and
that is visible to anybody who runs the command.

``--check`` regenerates and compares rather than writing, which is what CI runs.
A command added without its documentation fails the build, and the diff on the
pull request is the new command's entry, which is the thing a reviewer wants.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import click

from kilodial import __version__
from kilodial.cli.main import cli
from kilodial.tools import FAILED, OK

DEFAULT_PATH = Path("docs/commands.md")
HEADER = """# kilodial commands

Generated from the command tree. Do not edit by hand.
Rebuild with: python -m kilodial.tools.build_docs
"""


def walk(command: click.Command, path: list[str]) -> list[tuple[list[str], click.Command]]:
    """Every command in the tree, depth first, with the path to reach it."""
    found: list[tuple[list[str], click.Command]] = []
    if not isinstance(command, click.Group):
        return [(path, command)]
    for name in sorted(command.commands):
        found.extend(walk(command.commands[name], [*path, name]))
    return found


def options_of(command: click.Command) -> list[tuple[str, str]]:
    """A command's options, as a name and its help."""
    found: list[tuple[str, str]] = []
    for param in command.params:
        if not isinstance(param, click.Option) or param.name == "help":
            continue
        name = ", ".join(param.opts)
        detail = param.help or ""
        if param.required:
            detail = f"{detail} (required)".strip()
        found.append((name, detail))
    return found


def arguments_of(command: click.Command) -> list[str]:
    """A command's positional arguments, in order."""
    return [str(p.name).upper() for p in command.params if isinstance(p, click.Argument)]


def build() -> str:
    """The whole reference as markdown."""
    lines = [HEADER]
    groups = sorted({path[0] for path, _ in walk(cli, []) if len(path) > 1})
    lines.append("Groups: " + ", ".join(groups) + "\n")
    for path, command in walk(cli, []):
        usage = " ".join(["kilodial", *path, *arguments_of(command)])
        lines.append(f"## `{' '.join(path)}`\n")
        lines.append(f"    {usage}\n")
        summary = (command.help or "").strip().splitlines()
        if summary:
            lines.append(summary[0] + "\n")
        options = options_of(command)
        if options:
            for name, detail in options:
                lines.append(f"- `{name}` {detail}".rstrip())
            lines.append("")
    lines.append(f"Generated for kilodial {__version__}.")
    return "\n".join(lines) + "\n"


def write(path: Path = DEFAULT_PATH) -> Path:
    """Write the reference out, creating the directory if it is not there."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(build())
    return path


def differences(path: Path = DEFAULT_PATH) -> list[str]:
    """How the file on disk differs from the command tree."""
    if not path.exists():
        return [f"there is no command reference at {path}"]
    on_disk = path.read_text().splitlines()
    wanted = build().splitlines()
    if on_disk == wanted:
        return []
    found = [f"{path} is {len(on_disk)} lines and the tree builds {len(wanted)}"]
    for index, (was, now) in enumerate(zip(on_disk, wanted, strict=False), start=1):
        if was != now:
            found.append(f"line {index}: {was!r} should be {now!r}")
            break
    return found


def main(argv: list[str] | None = None) -> int:
    """Write the reference, or check it and fail when it has gone stale."""
    parser = argparse.ArgumentParser(description="build or check the command reference")
    parser.add_argument("--path", type=Path, default=DEFAULT_PATH)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    if not args.check:
        written = write(args.path)
        print(f"wrote {written} covering {len(walk(cli, []))} commands")
        return OK
    problems = differences(args.path)
    for problem in problems:
        print(problem)
    if problems:
        print("run python -m kilodial.tools.build_docs to bring it up to date")
        return FAILED
    print(f"{args.path} matches the command tree")
    return OK


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())


__all__ = [
    "DEFAULT_PATH",
    "HEADER",
    "arguments_of",
    "build",
    "differences",
    "main",
    "options_of",
    "walk",
    "write",
]
