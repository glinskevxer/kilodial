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
@click.option("--to", "last", default=None)
@click.option("--note", default=None)
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
    if first is not None and last is not None:
        found = options_for(shop, point_code, DateSpan(first, last), note=note)
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
@click.option("--from", "first", required=True)
@click.option("--to", "last", required=True)
@click.option("--kw", "kilowatts", required=True, help="connected load in kilowatts")
@click.option("--duty", required=True, help="share of the day the load ran")
@click.option("--rate", "rate_per_kwh", required=True, help="energy rate")
@click.option("--note", default=None)
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


@estimates.command("bases")
def estimate_bases() -> None:
    """The bases an estimate can rest on, strongest first."""
    rows = [[b.label, str(b.strength)] for b in sorted(Basis, key=lambda x: -x.strength)]
    for line in table(["basis", "strength"], rows):
        click.echo(line)


__all__ = ["estimates"]
