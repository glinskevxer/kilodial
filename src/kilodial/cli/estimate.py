"""Estimate commands.

The list command prints every basis the book supports and does not pick one.
That is the whole design of this corner of the package: a person picks, and the
command's job is to put the alternatives and the spread between them in front of
that person before they do.
"""

from __future__ import annotations

import click

from kilodial.cli.context import Context, pass_context
from kilodial.cli.render import or_dash, pairs, table
from kilodial.cli.window import span_of
from kilodial.errors import BadInputError
from kilodial.estimate.basis import Basis, from_connected_load
from kilodial.estimate.service import estimate_point, gap_for, options_for
from kilodial.units.span import DateSpan


@click.group("estimate")
def estimates() -> None:
    """Estimating a period nobody metered."""


@estimates.command("gap")
@click.argument("point_code")
@click.option("--on", "day", required=True, help="the day to judge the findings as at")
@pass_context
def estimate_gap(context: Context, point_code: str, day: str) -> None:
    """The period confirmed interference covered, clipped to a meter set."""
    shop = context.open()
    span = gap_for(shop, point_code, on=day)
    detail = [
        ("point", point_code.strip().upper()),
        ("gap", str(span)),
        ("days", str(span.days)),
        ("findings", str(len(shop.tamper.confirmed_at(point_code, day)))),
    ]
    for line in pairs(detail):
        click.echo(line)


@estimates.command("list")
@click.argument("point_code")
@click.option("--on", "day", default=None, help="find the gap from the findings")
@click.option("--from", "first", default=None, help="or give the period yourself")
@click.option("--to", "last", default=None, help="end of the window")
@click.option("--note", default=None, help="anything worth writing down")
@pass_context
def estimate_list(
    context: Context,
    point_code: str,
    day: str | None,
    first: str | None,
    last: str | None,
    note: str | None,
) -> None:
    """Every basis the book supports for a gap, strongest first."""
    shop = context.open()
    window = span_of(first, last)
    if window is not None:
        found = options_for(shop, point_code, window, note=note)
    elif day is not None:
        found = estimate_point(shop, point_code, on=day, note=note)
    else:
        raise click.BadParameter("give either --on or both --from and --to")
    rows = [[str(e.basis), str(e.amount), str(e.daily), e.working] for e in found.offered]
    for line in table(["basis", "amount", "a day", "working"], rows):
        click.echo(line)
    for basis, why in found.refused:
        click.echo(f"no {basis}: {why}")
    click.echo(f"{found.show()}, spread {found.spread()}")
    if not found.has_any:
        raise SystemExit(1)


@estimates.command("load")
@click.argument("point_code")
@click.option("--from", "first", required=True, help="start of the window")
@click.option("--to", "last", required=True, help="end of the window")
@click.option("--kw", "kilowatts", required=True, help="connected load in kilowatts")
@click.option("--duty", required=True, help="share of the day the load ran")
@click.option("--rate", "rate_per_kwh", required=True, help="energy rate")
@click.option("--note", default=None, help="anything worth writing down")
@pass_context
def estimate_load(
    context: Context,
    point_code: str,
    first: str,
    last: str,
    kilowatts: str,
    duty: str,
    rate_per_kwh: str,
    note: str | None,
) -> None:
    """Estimate from nameplate load when there is no history to work from."""
    shop = context.open()
    code = shop.points.get(point_code).code
    found = from_connected_load(
        code,
        DateSpan(first, last),
        kilowatts=kilowatts,
        duty=duty,
        rate_per_kwh=rate_per_kwh,
        note=note,
    )
    detail = [
        ("point", found.point_code),
        ("period", str(found.span)),
        ("basis", str(found.basis)),
        ("amount", str(found.amount)),
        ("a day", str(found.daily)),
        ("working", found.working),
        ("note", or_dash(found.note)),
    ]
    for line in pairs(detail):
        click.echo(line)


@estimates.command("settle")
@click.argument("reference")
@click.argument("point_code")
@click.option("--basis", required=True, help="which basis was chosen")
@click.option("--on", "day", default=None, help="find the gap from the findings")
@click.option("--from", "first", default=None, help="or give the period yourself")
@click.option("--to", "last", default=None, help="end of the window")
@click.option("--settled-on", required=True, help="the day it was settled")
@click.option("--by", "settler", required=True, help="who settled it")
@click.option("--note", default=None, help="anything worth writing down")
@pass_context
def estimate_settle(
    context: Context,
    reference: str,
    point_code: str,
    basis: str,
    day: str | None,
    first: str | None,
    last: str | None,
    settled_on: str,
    settler: str,
    note: str | None,
) -> None:
    """Write down which estimate was used, and who chose it."""
    shop = context.open()
    window = span_of(first, last)
    if window is not None:
        options = options_for(shop, point_code, window, note=note)
    elif day is not None:
        options = estimate_point(shop, point_code, on=day, note=note)
    else:
        raise click.BadParameter("give either --on or both --from and --to")
    wanted = basis_named(basis)
    chosen = [e for e in options.offered if e.basis is wanted]
    if not chosen:
        offered = ", ".join(str(e.basis) for e in options.offered) or "nothing"
        raise BadInputError(
            f"{wanted} is not one of the bases the book supports here, which are {offered}"
        )
    with shop.transaction():
        settled = shop.estimates.settle(reference, chosen[0], on=settled_on, by=settler)
        context.log("estimated", f"point {settled.estimate.point_code}", str(settled.amount))
    context.say(str(settled))


@estimates.command("settled")
@click.argument("point_code")
@pass_context
def estimate_settled(context: Context, point_code: str) -> None:
    """Estimates already settled at a point."""
    shop = context.open()
    code = shop.points.get(point_code).code
    rows = [
        [
            s.reference,
            str(s.estimate.span),
            str(s.basis),
            str(s.amount),
            s.settled_on.isoformat(),
            s.settled_by,
        ]
        for s in shop.estimates.for_point(code)
    ]
    for line in table(["estimate", "period", "basis", "amount", "settled", "by"], rows):
        click.echo(line)
    click.echo(f"{shop.estimates.total_for(code)} settled at {code}")


def basis_named(text: str) -> Basis:
    """Read an estimate basis by its label."""
    wanted = text.strip().lower()
    for member in Basis:
        if member.label == wanted or member.name.lower() == wanted:
            return member
    raise BadInputError(f"{text!r} is not a basis an estimate can rest on")


@estimates.command("bases")
def estimate_bases() -> None:
    """The bases an estimate can rest on, strongest first."""
    rows = [[b.label, str(b.strength)] for b in sorted(Basis, key=lambda x: -x.strength)]
    for line in table(["basis", "strength"], rows):
        click.echo(line)


__all__ = ["basis_named", "estimates"]
