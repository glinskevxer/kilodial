"""Technician register commands.

The command worth having is ``may``. It answers, before a run is entered rather
than after, whether the person about to do it is allowed to sign it. Finding out
afterwards means a void run, a meter that has to come back to the bench, and a
customer who has waited an extra fortnight.
"""

from __future__ import annotations

import click

from kilodial.cli.context import Context, pass_context
from kilodial.cli.render import or_dash, pairs, table
from kilodial.cli.runs import run_kind
from kilodial.model.technician import Grade, Technician, grade_named


@click.group("tech")
def technicians() -> None:
    """The technician certification register."""


@technicians.command("add")
@click.argument("badge")
@click.argument("name")
@click.option("--grade", required=True, help="bench, polyphase or supervisor")
@click.option("--certified", required=True, help="the day the certification was issued")
@click.option("--due", required=True, help="the day it runs out")
@click.option("--note", default=None)
@pass_context
def technician_add(
    context: Context,
    badge: str,
    name: str,
    grade: str,
    certified: str,
    due: str,
    note: str | None,
) -> None:
    """Put a technician on the register."""
    shop = context.open()
    person = Technician.build(
        badge,
        name,
        grade=grade_named(grade),
        certified_on=certified,
        certificate_due=due,
        note=note,
    )
    with shop.transaction():
        shop.technicians.add(person)
    context.say(f"{person} on the register")


@technicians.command("recertify")
@click.argument("badge")
@click.option("--certified", required=True)
@click.option("--due", required=True)
@click.option("--grade", default=None, help="promote at the same time")
@pass_context
def technician_recertify(
    context: Context, badge: str, certified: str, due: str, grade: str | None
) -> None:
    """Record a new certification against somebody already on the register."""
    shop = context.open()
    current = shop.technicians.get(badge)
    renewed = Technician.build(
        current.badge,
        current.name,
        grade=current.grade if grade is None else grade_named(grade),
        certified_on=certified,
        certificate_due=due,
        note=current.note,
    )
    with shop.transaction():
        shop.technicians.save(renewed)
    context.say(
        f"{renewed.badge} recertified to {renewed.certificate_due.isoformat()} as {renewed.grade}"
    )


@technicians.command("list")
@click.option("--on", "day", default=None, help="only those certified on this day")
@click.option("--grade", default=None)
@click.option("--due-within", "window", type=int, default=None, help="days ahead to look")
@pass_context
def technician_list(
    context: Context, day: str | None, grade: str | None, window: int | None
) -> None:
    """List the register."""
    shop = context.open()
    if window is not None:
        if day is None:
            raise click.BadParameter("--due-within needs --on to count from")
        found = shop.technicians.due_within(day, window)
    elif grade is not None:
        found = shop.technicians.by_grade(grade_named(grade))
    elif day is not None:
        found = shop.technicians.certified_on(day)
    else:
        found = shop.technicians.all()
    rows = [
        [
            t.badge,
            t.name,
            str(t.grade),
            t.certified_on.isoformat(),
            t.certificate_due.isoformat(),
            or_dash(t.note),
        ]
        for t in found
    ]
    for line in table(["badge", "name", "grade", "certified", "due", "note"], rows):
        click.echo(line)


@technicians.command("lapsed")
@click.option("--on", "day", required=True)
@pass_context
def technician_lapsed(context: Context, day: str) -> None:
    """Certifications that had run out on a day."""
    shop = context.open()
    rows = [
        [t.badge, t.name, t.certificate_due.isoformat(), str(-t.days_left_on(day))]
        for t in shop.technicians.lapsed_on(day)
    ]
    for line in table(["badge", "name", "due", "days over"], rows):
        click.echo(line)


@technicians.command("may")
@click.argument("badge")
@click.argument("meter_serial")
@click.option("--kind", default="as_found", show_default=True)
@click.option("--on", "day", required=True)
@pass_context
def technician_may(context: Context, badge: str, meter_serial: str, kind: str, day: str) -> None:
    """Say whether somebody may sign that run on that day, before it is run."""
    shop = context.open()
    person = shop.technicians.get(badge)
    device = shop.device_for(meter_serial)
    refusals = person.refusals(run_kind(kind), device, on=day)
    detail = [
        ("badge", person.badge),
        ("name", person.name),
        ("grade", str(person.grade)),
        ("certified to", person.certificate_due.isoformat()),
        ("meter", meter_serial.strip().upper()),
        ("type", device.key),
        ("run kind", kind),
        ("may sign", "no" if refusals else "yes"),
    ]
    for line in pairs(detail):
        click.echo(line)
    for refusal in refusals:
        click.echo(refusal)
    if refusals:
        raise SystemExit(1)


@technicians.command("grades")
def technician_grades() -> None:
    """The grades and what each one signs."""
    rows = [
        [
            g.label,
            "yes" if g.signs_polyphase else "no",
            "yes" if g.signs_referee else "no",
        ]
        for g in Grade
    ]
    for line in table(["grade", "polyphase", "referee"], rows):
        click.echo(line)


__all__ = ["technicians"]
