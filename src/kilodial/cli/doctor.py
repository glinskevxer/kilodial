"""One command that asks every question the shop should be able to answer.

The individual checks all exist elsewhere and every one of them is reachable
from its own command. This is the one somebody runs on a Monday, or when a book
has been handed over, or before a filing, and its whole value is that it is one
command with one exit code.

Findings are graded rather than counted. A book that fails its integrity check
and a book with three meters missing from every group are both findings and only
one of them means stop what you are doing.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass

import click

from kilodial.cli.context import Context, pass_context
from kilodial.cli.render import table
from kilodial.programme import roster
from kilodial.store.shop import Shop
from kilodial.units.span import parse_date

CERTIFICATE_WARNING_DAYS = 60


class Level(enum.Enum):
    """How much a finding matters."""

    STOP = ("stop", 3)
    WARN = ("warn", 2)
    NOTE = ("note", 1)

    def __init__(self, label: str, rank: int) -> None:
        self.label = label
        self.rank = rank

    def __str__(self) -> str:
        return self.label


@dataclass(frozen=True)
class Finding:
    """One thing the doctor noticed."""

    level: Level
    check: str
    detail: str

    def row(self) -> list[str]:
        return [str(self.level), self.check, self.detail]

    def __str__(self) -> str:
        return f"{self.level}: {self.check}, {self.detail}"


def examine(shop: Shop, on: object) -> list[Finding]:
    """Every finding about a book on a day, worst first."""
    when = parse_date(on)
    found: list[Finding] = []

    for fault in shop.book.check():
        found.append(Finding(Level.STOP, "book", fault))
    for fault in shop.audit():
        found.append(Finding(Level.STOP, "references", fault))

    unusable = shop.unusable_runs()
    if unusable:
        found.append(
            Finding(
                Level.WARN,
                "runs",
                f"{len(unusable)} runs cannot be relied on, first is {unusable[0][0].reference}",
            )
        )

    expired = shop.standards.expired_on(when)
    for standard in expired:
        found.append(
            Finding(
                Level.STOP,
                "standards",
                f"{standard.serial} ran out of certificate on "
                f"{standard.certificate_due.isoformat()}",
            )
        )
    for standard in shop.standards.due_within(when, CERTIFICATE_WARNING_DAYS):
        found.append(
            Finding(
                Level.WARN,
                "standards",
                f"{standard.serial} has {standard.days_left_on(when)} days left",
            )
        )

    for person in shop.technicians.lapsed_on(when):
        found.append(Finding(Level.WARN, "technicians", f"{person.badge} is no longer certified"))

    built = roster.build(shop, on=when)
    overdue = built.overdue()
    if overdue:
        found.append(Finding(Level.WARN, "programme", f"{len(overdue)} meters are overdue"))
    ungrouped = built.ungrouped()
    if ungrouped:
        found.append(
            Finding(
                Level.NOTE,
                "programme",
                f"{len(ungrouped)} meters fall into no sampling group",
            )
        )

    late = shop.complaints.overdue(when)
    if late:
        found.append(
            Finding(
                Level.STOP,
                "complaints",
                f"{len(late)} customer requests are past their thirty days",
            )
        )

    behind = shop.orders.late_on(when)
    if behind:
        found.append(Finding(Level.WARN, "work orders", f"{len(behind)} orders are past due"))

    return sorted(found, key=lambda f: (-f.level.rank, f.check, f.detail))


def worst(findings: list[Finding]) -> Level | None:
    """The most serious level in a set of findings, or nothing when it is clean."""
    levels = [f.level for f in findings]
    if not levels:
        return None
    return max(levels, key=lambda level: level.rank)


@click.command("doctor")
@click.option("--on", "day", required=True, help="the day to examine the book as at")
@click.option("--quiet", "only_bad", is_flag=True, help="leave the notes out")
@pass_context
def doctor(context: Context, day: str, only_bad: bool) -> None:
    """Ask every question the shop should be able to answer."""
    shop = context.open()
    findings = examine(shop, day)
    if only_bad:
        findings = [f for f in findings if f.level is not Level.NOTE]
    if not findings:
        context.say(f"nothing to report on {day}")
        return
    for line in table(["level", "check", "detail"], [f.row() for f in findings]):
        click.echo(line)
    if worst(findings) is Level.STOP:
        raise SystemExit(2)
    raise SystemExit(1)


__all__ = ["CERTIFICATE_WARNING_DAYS", "Finding", "Level", "doctor", "examine", "worst"]
