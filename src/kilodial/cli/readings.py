"""Register reading commands.

``consumption`` is the one that earns its place. It shows the dials, the
multiplier and the billed units as three separate numbers, and says in a word
whether the register rolled. A customer looking at a bill they think is wrong is
almost always looking at one of those three, and printing only the product tells
them nothing they can check.
"""

from __future__ import annotations

import click

from kilodial.cli.context import Context, pass_context
from kilodial.cli.render import or_dash, pairs, table
from kilodial.cli.window import require_span, span_of
from kilodial.model.reading import Reading, ReadingKind, reading_kind, wrap_at


@click.group("read")
def readings() -> None:
    """Register readings."""


@readings.command("take")
@click.argument("point_code")
@click.argument("meter_serial")
@click.argument("value", type=int)
@click.option("--on", "day", required=True, help="the day it was read")
@click.option("--dials", type=int, required=True, help="how many dials the register has")
@click.option("--kind", default="actual", show_default=True)
@click.option("--note", default=None)
@pass_context
def reading_take(
    context: Context,
    point_code: str,
    meter_serial: str,
    value: int,
    day: str,
    dials: int,
    kind: str,
    note: str | None,
) -> None:
    """Write a register reading down."""
    shop = context.open()
    meter = shop.meters.get(meter_serial)
    reading = Reading.build(
        shop.points.get(point_code).code,
        meter.serial,
        read_on=day,
        dials=dials,
        value=value,
        kind=reading_kind(kind),
        note=note,
    )
    with shop.transaction():
        shop.readings.add(reading)
        context.log("read", f"point {reading.point_code}", str(reading.value))
    context.say(f"read {reading}")


@readings.command("list")
@click.argument("point_code")
@click.option("--from", "first", default=None, help="start of the window")
@click.option("--to", "last", default=None, help="end of the window")
@pass_context
def reading_list(context: Context, point_code: str, first: str | None, last: str | None) -> None:
    """A point's readings, oldest first."""
    shop = context.open()
    code = shop.points.get(point_code).code
    window = span_of(first, last)
    found = (
        shop.readings.for_point(code) if window is None else shop.readings.covering(code, window)
    )
    rows = [
        [
            r.read_on.isoformat(),
            r.meter_serial,
            f"{r.value:0{r.dials}d}",
            str(r.dials),
            str(r.kind),
            or_dash(r.note),
        ]
        for r in found
    ]
    for line in table(["read on", "meter", "reading", "dials", "kind", "note"], rows):
        click.echo(line)


@readings.command("consumption")
@click.argument("point_code")
@click.option("--from", "first", required=True, help="start of the window")
@click.option("--to", "last", required=True, help="end of the window")
@click.option("--multiplier", default=None, help="override the set's multiplier")
@pass_context
def reading_consumption(
    context: Context, point_code: str, first: str, last: str, multiplier: str | None
) -> None:
    """What passed at a point between two readings."""
    shop = context.open()
    code = shop.points.get(point_code).code
    window = require_span(first, last)
    factor = multiplier
    if factor is None:
        standing = shop.installs.on_day(code, window.start)
        factor = "1" if standing is None else str(standing.programmed_multiplier)
    found = shop.readings.consumption_over(code, window, multiplier=factor)
    detail = [
        ("point", code),
        ("window", str(window)),
        ("days", str(found.days)),
        ("dials", str(found.units)),
        ("multiplier", str(found.multiplier.normalize())),
        ("billed units", str(found.billed_units)),
        ("a day", str(found.daily)),
        ("register rolled", "yes" if found.rolled else "no"),
        ("plausible", "yes" if found.plausible else "no"),
    ]
    for line in pairs(detail):
        click.echo(line)
    if found.reason is not None:
        click.echo(found.reason)
        raise SystemExit(1)


@readings.command("kinds")
def reading_kinds() -> None:
    """The kinds of reading the shop records."""
    rows = [
        [k.label, "yes" if k.is_read else "no", "yes" if k.bills else "no"] for k in ReadingKind
    ]
    for line in table(["kind", "a real read", "can end a period"], rows):
        click.echo(line)
    click.echo(f"a five dial register rolls at {wrap_at(5)}")


__all__ = ["readings"]
