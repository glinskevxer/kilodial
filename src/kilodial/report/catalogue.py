"""What reports there are and what question each one answers.

Six reports is enough that somebody has to be told which one to run, and the
answer lives in six docstrings in six modules where nobody will look. So the
list is here, with the question each report answers written as a question,
because that is how a person arriving at the tool thinks about it.

The list is checked against the command tree, so a report added without a line
here fails a test rather than quietly existing.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Entry:
    """One report, its command, and what it is for."""

    name: str
    question: str
    period: bool

    @property
    def command(self) -> str:
        return f"kilodial report {self.name}"

    def row(self) -> list[str]:
        return [
            self.name,
            "period" if self.period else "as at",
            self.question,
        ]

    def __str__(self) -> str:
        return f"{self.command} - {self.question}"


CATALOGUE: tuple[Entry, ...] = (
    Entry(
        "shop",
        "What does the shop look like today, and is anything about to lapse?",
        False,
    ),
    Entry(
        "commission",
        "What do we have to tell the commission we tested this year?",
        True,
    ),
    Entry(
        "register",
        "Which service points owe money or are owed it, and how much?",
        False,
    ),
    Entry(
        "certificates",
        "What has a certificate on it and how long has each one left?",
        False,
    ),
    Entry(
        "faults",
        "What breaks, on which types, and what does keeping them going cost?",
        True,
    ),
    Entry(
        "bench",
        "Who benched what, and how much of it came back unusable?",
        True,
    ),
)


def names() -> list[str]:
    """Every report's name, in the order the catalogue lists them."""
    return [entry.name for entry in CATALOGUE]


def find(name: str) -> Entry:
    """One entry by name."""
    wanted = name.strip().lower()
    for entry in CATALOGUE:
        if entry.name == wanted:
            return entry
    raise KeyError(f"{name!r} is not a report this shop produces")


def by_period() -> tuple[list[Entry], list[Entry]]:
    """The reports split into the ones over a window and the ones as at a day."""
    return (
        [e for e in CATALOGUE if e.period],
        [e for e in CATALOGUE if not e.period],
    )


__all__ = ["CATALOGUE", "Entry", "by_period", "find", "names"]
