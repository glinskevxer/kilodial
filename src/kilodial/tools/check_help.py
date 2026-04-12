"""Check every command and option says what it is for.

An option with no help renders as a bare flag in ``--help`` and the person
reading it has to guess or read the source. It happens because click does not
mind, and because the author knew what the option did at the moment they wrote
it.

Three things are checked and the third is the one that matters:

Every command has a one line summary. Click takes this from the docstring, so a
command with no docstring has no help at all.

Every option has help text, unless it is one of the handful whose name is its
own explanation and which appear on a dozen commands.

Every command's summary is a sentence, not a fragment. A summary that starts
lower case or runs past a line is one that was written as a note to the author
rather than as a line in a help screen.
"""

from __future__ import annotations

import sys

import click

from kilodial.cli.main import cli
from kilodial.tools import FAILED, OK
from kilodial.tools.build_docs import walk

# Options whose name says everything, on enough commands that repeating the help
# on each of them is noise.
OBVIOUS = frozenset({"--help", "--version", "--yes"})

LONGEST_SUMMARY = 78


def summary_of(command: click.Command) -> str:
    """A command's first line of help."""
    text = (command.help or "").strip()
    return text.splitlines()[0] if text else ""


def faults_for(path: list[str], command: click.Command) -> list[str]:
    """Everything unhelpful about one command."""
    where = " ".join(path)
    found: list[str] = []
    summary = summary_of(command)
    if not summary:
        found.append(f"{where} has no help at all")
    else:
        if not summary[0].isupper():
            found.append(f"{where}: the summary does not start with a capital")
        if len(summary) > LONGEST_SUMMARY:
            found.append(
                f"{where}: the summary runs to {len(summary)} characters, over {LONGEST_SUMMARY}"
            )
        if not summary.endswith("."):
            found.append(f"{where}: the summary does not end in a full stop")
    for param in command.params:
        if not isinstance(param, click.Option):
            continue
        if any(opt in OBVIOUS for opt in param.opts):
            continue
        if not param.help:
            found.append(f"{where}: {', '.join(param.opts)} has no help")
    return found


def faults() -> list[str]:
    """Everything unhelpful across the whole command tree."""
    found: list[str] = []
    for path, command in walk(cli, []):
        found.extend(faults_for(path, command))
    return found


def counts() -> tuple[int, int]:
    """How many commands and options the tree carries."""
    commands = walk(cli, [])
    options = sum(
        1 for _, command in commands for param in command.params if isinstance(param, click.Option)
    )
    return (len(commands), options)


def main(argv: list[str] | None = None) -> int:
    """Print what is unhelpful and say so in the exit code."""
    problems = faults()
    for problem in problems:
        print(problem)
    if problems:
        print(f"{len(problems)} commands or options do not say what they are for")
        return FAILED
    commands, options = counts()
    print(f"{commands} commands and {options} options, every one of them explained")
    return OK


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())


__all__ = [
    "LONGEST_SUMMARY",
    "OBVIOUS",
    "counts",
    "faults",
    "faults_for",
    "main",
    "summary_of",
]
