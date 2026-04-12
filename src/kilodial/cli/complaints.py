"""Customer requested test commands.

The list command defaults to open requests because that is the working list: a
thirty day clock is running on every one of them and a closed request is
history. Asking for everything is one flag away.
"""

from __future__ import annotations

import click

from kilodial.cli.context import Context, pass_context
from kilodial.cli.render import or_dash, pairs, table
from kilodial.cli.transformers import load_factor
from kilodial.complaint.request import Reason, reason_named
from kilodial.complaint.service import answer, log
from kilodial.units.money import Money
from kilodial.units.span import parse_date


@click.group("complaint")
def complaints() -> None:
    """Tests the customer asked for."""


@complaints.command("open")
@click.argument("reference")
@click.argument("point_code")
@click.option("--on", "day", required=True, help="the day the customer asked")
@click.option("--by", "requester", required=True, help="who asked")
@click.option(
    "--reason", default="other", show_default=True, help="why the customer says the meter is wrong"
)
@click.option("--note", default=None, help="anything worth writing down")
@pass_context
def complaint_open(
    context: Context,
    reference: str,
    point_code: str,
    day: str,
    requester: str,
    reason: str,
    note: str | None,
) -> None:
    """Log a customer request against a service point."""
    shop = context.open()
    with shop.transaction():
        opened = log(
            shop,
            reference,
            point_code,
            on=day,
            by=requester,
            reason=reason_named(reason),
            note=note,
        )
    context.say(f"{opened.reference} logged, test due by {opened.request.due_by.isoformat()}")


@complaints.command("answer")
@click.argument("reference")
@click.option("--run", "run_reference", required=True, help="the referee run")
@click.option("--on", "day", required=True, help="the day the request is closed")
@click.option("--fee", default=None, help="override the standard fee")
@click.option(
    "--pf", "power_factor", default="unity", show_default=True, help="the load angle to judge at"
)
@pass_context
def complaint_answer(
    context: Context,
    reference: str,
    run_reference: str,
    day: str,
    fee: str | None,
    power_factor: str,
) -> None:
    """Close a request with the referee run that answered it."""
    shop = context.open()
    with shop.transaction():
        found = answer(
            shop,
            reference,
            run_reference=run_reference,
            on=day,
            fee=None if fee is None else Money(fee),
            power_factor=load_factor(power_factor),
        )
    detail = [
        ("request", found.complaint.reference),
        ("run", str(found.complaint.run_reference)),
        ("meter", str(found.accuracy.meter)),
        ("overall", str(found.accuracy.overall)),
        ("multiplier right", "yes" if found.accuracy.multiplier_is_right else "no"),
        ("days taken", str(found.complaint.request.days_taken(day))),
        ("fee", str(found.fee)),
        ("decision", str(found.charge)),
    ]
    for line in pairs(detail):
        click.echo(line)


@complaints.command("list")
@click.option("--all", "everything", is_flag=True, help="closed ones too")
@click.option("--point", "point_code", default=None, help="only this service point")
@click.option("--overdue", "day", default=None, help="only ones past due on this day")
@pass_context
def complaint_list(
    context: Context, everything: bool, point_code: str | None, day: str | None
) -> None:
    """List customer requests, open by default."""
    shop = context.open()
    if day is not None:
        found = shop.complaints.overdue(day)
    elif point_code is not None:
        found = shop.complaints.for_point(point_code)
    elif everything:
        found = shop.complaints.all()
    else:
        found = shop.complaints.open_ones()
    rows = [
        [
            c.reference,
            c.request.point_code,
            c.request.requested_on.isoformat(),
            c.request.due_by.isoformat(),
            str(c.request.reason),
            or_dash(c.run_reference),
            "open" if c.is_open else str(c.charge),
            "-" if c.fee is None else str(c.fee),
        ]
        for c in found
    ]
    headings = ["request", "point", "asked", "due by", "reason", "run", "state", "fee"]
    for line in table(headings, rows):
        click.echo(line)


@complaints.command("show")
@click.argument("reference")
@pass_context
def complaint_show(context: Context, reference: str) -> None:
    """One request and everything decided about it."""
    shop = context.open()
    complaint = shop.complaints.get(reference)
    previous = shop.complaints.previous_for(
        complaint.request.point_code, complaint.request.requested_on
    )
    detail = [
        ("request", complaint.reference),
        ("point", complaint.request.point_code),
        ("asked on", complaint.request.requested_on.isoformat()),
        ("asked by", complaint.request.requested_by),
        ("reason", str(complaint.request.reason)),
        ("note", or_dash(complaint.request.note)),
        ("due by", complaint.request.due_by.isoformat()),
        ("last asked", or_dash(None if previous is None else previous.isoformat())),
        ("run", or_dash(complaint.run_reference)),
        ("decision", or_dash(None if complaint.charge is None else str(complaint.charge))),
        ("fee", or_dash(complaint.fee)),
        (
            "closed",
            or_dash(None if complaint.closed_on is None else complaint.closed_on.isoformat()),
        ),
    ]
    for line in pairs(detail):
        click.echo(line)


@complaints.command("reasons")
def complaint_reasons() -> None:
    """The reasons a request can be filed under."""
    for reason in Reason:
        click.echo(reason.value)


@complaints.command("clock")
@click.option("--on", "day", required=True, help="the day to work this out as at")
@pass_context
def complaint_clock(context: Context, day: str) -> None:
    """How many days are left on each open request."""
    shop = context.open()
    when = parse_date(day)
    rows = []
    for complaint in shop.complaints.open_ones():
        left = (complaint.request.due_by - when).days
        rows.append(
            [
                complaint.reference,
                complaint.request.point_code,
                complaint.request.due_by.isoformat(),
                str(left),
                "late" if left < 0 else "in time",
            ]
        )
    for line in table(["request", "point", "due by", "days left", "state"], rows):
        click.echo(line)


__all__ = ["complaints"]
