"""Sampling group and periodic programme commands.

The sample command is the one that changes anything. It reads a window of bench
work, judges the group against the spread and failure rules, and records the
interval that comes out. It prints the working whether it passes or fails,
because the commission asks for the working and reconstructing it a year later
from a single number is not possible.
"""

from __future__ import annotations

import click

from kilodial.cli.context import Context, pass_context
from kilodial.cli.devices import _technology
from kilodial.cli.render import or_dash, pairs, table
from kilodial.programme import roster
from kilodial.programme.season import run_sample
from kilodial.sampling.group import Group
from kilodial.sampling.plan import required
from kilodial.units.span import DateSpan


@click.group("group")
def groups() -> None:
    """Homogeneous groups and their periodic sample plans."""


@groups.command("add")
@click.argument("code")
@click.argument("name")
@click.option("--type", "device_keys", multiple=True, help="catalogue key, repeatable")
@click.option("--class", "class_code", default=None, help="only this meter class")
@click.option("--tech", default=None, help="only this technology")
@click.option("--form", "form_codes", multiple=True, help="ANSI form, repeatable")
@click.option("--acquired-from", default=None, help="earliest delivery day in the group")
@click.option("--acquired-to", default=None, help="latest delivery day in the group")
@pass_context
def group_add(
    context: Context,
    code: str,
    name: str,
    device_keys: tuple[str, ...],
    class_code: str | None,
    tech: str | None,
    form_codes: tuple[str, ...],
    acquired_from: str | None,
    acquired_to: str | None,
) -> None:
    """Put a sampling group on the book."""
    shop = context.open()
    group = Group.build(
        code,
        name,
        device_keys=list(device_keys),
        class_code=class_code,
        technology=None if tech is None else _technology(tech),
        form_codes=list(form_codes),
        acquired_from=acquired_from,
        acquired_to=acquired_to,
    )
    with shop.transaction():
        shop.groups.add(group)
    context.say(f"group {group} on the book, taking {', '.join(group.criteria())}")


@groups.command("list")
@pass_context
def group_list(context: Context) -> None:
    """List groups with their population and interval."""
    shop = context.open()
    rows = []
    for group in shop.groups.all():
        population = shop.groups.population(group.code)
        rows.append(
            [
                group.code,
                group.name,
                str(population),
                str(required(population)),
                str(shop.plans.interval(group.code)),
                or_dash(shop.plans.next_due(group.code)),
            ]
        )
    for line in table(["group", "name", "population", "sample", "interval", "next due"], rows):
        click.echo(line)


@groups.command("show")
@click.argument("code")
@pass_context
def group_show(context: Context, code: str) -> None:
    """One group, its criteria, and its decision history."""
    shop = context.open()
    group = shop.groups.get(code)
    population = shop.groups.population(group.code)
    detail = [
        ("group", group.code),
        ("name", group.name),
        ("criteria", "; ".join(group.criteria())),
        ("population", str(population)),
        ("sample needed", str(required(population))),
        ("interval", f"{shop.plans.interval(group.code)} months"),
        ("next due", or_dash(shop.plans.next_due(group.code))),
    ]
    for line in pairs(detail):
        click.echo(line)
    history = shop.plans.history(group.code)
    if not history:
        return
    click.echo("")
    rows = [
        [
            d.decided_on.isoformat(),
            str(d.outcome.tested),
            str(d.outcome.mean),
            str(d.outcome.deviation),
            str(d.outcome.failures),
            "passed" if d.passed else "failed",
            "mass test" if d.is_mass_test else str(d.interval_months),
        ]
        for d in history
    ]
    for line in table(
        ["decided", "tested", "mean", "deviation", "failures", "outcome", "interval"], rows
    ):
        click.echo(line)


@groups.command("members")
@click.argument("code")
@pass_context
def group_members(context: Context, code: str) -> None:
    """The meters in a group right now."""
    shop = context.open()
    rows = [
        [m.serial, m.device_key, m.state.value, m.acquired.isoformat()]
        for m in shop.groups.members(code)
    ]
    for line in table(["serial", "type", "state", "acquired"], rows):
        click.echo(line)


@groups.command("sample")
@click.argument("code")
@click.option("--from", "first", required=True, help="start of the season")
@click.option("--to", "last", required=True, help="end of the season")
@click.option("--on", "decided", required=True, help="the day the decision is taken")
@click.option("--note", default=None, help="anything worth writing down")
@pass_context
def group_sample(
    context: Context, code: str, first: str, last: str, decided: str, note: str | None
) -> None:
    """Judge a season's bench work and set the group's next interval."""
    shop = context.open()
    with shop.transaction():
        season, decision = run_sample(shop, code, span=DateSpan(first, last), on=decided, note=note)
    click.echo(season.show())
    click.echo(decision.outcome.show())
    for reason in decision.reasons():
        click.echo(reason)
    where = "mass test" if decision.is_mass_test else f"{decision.interval_months} months"
    click.echo(f"{decision.group_code}: {decision.previous_months} months to {where}")
    for reference, outcome in season.skipped:
        click.echo(f"left out {reference} ({outcome})")
    if not decision.passed:
        raise SystemExit(1)


@click.group("due")
def due() -> None:
    """The periodic test programme."""


@due.command("list")
@click.option("--on", "day", required=True, help="the day to judge against")
@click.option("--group", "group_code", default=None, help="only this sampling group")
@click.option("--overdue", is_flag=True, help="only meters past their grace period")
@click.option("--grace", type=int, default=None, help="grace period in days")
@pass_context
def due_list(
    context: Context, day: str, group_code: str | None, overdue: bool, grace: int | None
) -> None:
    """Who is due, and how far past it."""
    shop = context.open()
    built = (
        roster.build(shop, on=day)
        if grace is None
        else roster.build(shop, on=day, grace_days=grace)
    )
    lines = built.overdue() if overdue else built.needing_work()
    if group_code is not None:
        wanted = group_code.strip().upper()
        lines = [line for line in lines if line.group_code == wanted]
    rows = [
        [
            line.serial,
            line.group_code,
            str(line.interval_months),
            line.baseline.isoformat(),
            line.due.isoformat(),
            str(line.state),
            str(line.days_over),
        ]
        for line in lines
    ]
    for line in table(["serial", "group", "interval", "since", "due", "state", "days over"], rows):
        click.echo(line)


@due.command("counts")
@click.option("--on", "day", required=True, help="the day to work this out as at")
@pass_context
def due_counts(context: Context, day: str) -> None:
    """How many meters are current, due and overdue."""
    shop = context.open()
    built = roster.build(shop, on=day)
    rows = [[str(state), str(count)] for state, count in built.counts().items()]
    rows.append(["ungrouped", str(len(built.ungrouped()))])
    for line in table(["state", "meters"], rows):
        click.echo(line)


__all__ = ["due", "groups"]
