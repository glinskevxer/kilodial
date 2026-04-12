"""Bench and reference standard commands.

Recertification is a separate command from adding a standard rather than an
edit, because it is the one thing that happens to a standard again and again and
because the old certificate number is worth keeping visible in the shell history
when somebody is trying to work out which certificate covered a run in March.
"""

from __future__ import annotations

import click

from kilodial.cli.context import Context, pass_context
from kilodial.cli.render import or_dash, pairs, table, yes_no
from kilodial.cli.window import counted_from
from kilodial.model.bench import Bench, ReferenceStandard
from kilodial.programme import rota


@click.group("standard")
def standards() -> None:
    """Reference standards and their certificates."""


@standards.command("add")
@click.argument("serial")
@click.option("--maker", required=True, help="who made it")
@click.option("--model", "model_code", required=True, help="the model code")
@click.option("--certificate", required=True, help="the certificate number")
@click.option("--certified", required=True, help="the day the certificate was issued")
@click.option("--due", required=True, help="the day the certificate runs out")
@click.option("--uncertainty", required=True, help="stated uncertainty in percent")
@click.option(
    "--traceable", default="NIST", show_default=True, help="what the certificate traces to"
)
@pass_context
def standard_add(
    context: Context,
    serial: str,
    maker: str,
    model_code: str,
    certificate: str,
    certified: str,
    due: str,
    uncertainty: str,
    traceable: str,
) -> None:
    """Put a reference standard on the book."""
    shop = context.open()
    standard = ReferenceStandard.build(
        serial,
        maker=maker,
        model_code=model_code,
        certificate=certificate,
        certified_on=certified,
        certificate_due=due,
        uncertainty=uncertainty,
        traceable_to=traceable,
    )
    with shop.transaction():
        shop.standards.add(standard)
    context.say(f"standard {standard.serial} on the book, {standard}")


@standards.command("recertify")
@click.argument("serial")
@click.option("--certificate", required=True, help="the new certificate number")
@click.option("--certified", required=True, help="the day it was issued")
@click.option("--due", required=True, help="the day it runs out")
@click.option("--uncertainty", default=None, help="stated uncertainty, if it changed")
@pass_context
def standard_recertify(
    context: Context,
    serial: str,
    certificate: str,
    certified: str,
    due: str,
    uncertainty: str | None,
) -> None:
    """Record a new certificate against a standard already on the book."""
    shop = context.open()
    current = shop.standards.get(serial)
    renewed = ReferenceStandard.build(
        current.serial,
        maker=current.maker,
        model_code=current.model_code,
        certificate=certificate,
        certified_on=certified,
        certificate_due=due,
        uncertainty=current.uncertainty if uncertainty is None else uncertainty,
        traceable_to=current.traceable_to,
    )
    with shop.transaction():
        shop.standards.save(renewed)
    context.say(
        f"{renewed.serial} recertified, {current.certificate} replaced by {renewed.certificate}"
    )


@standards.command("list")
@click.option("--on", "day", default=None, help="only standards valid on this day")
@click.option("--due-within", "window", type=int, default=None, help="days ahead to look")
@pass_context
def standard_list(context: Context, day: str | None, window: int | None) -> None:
    """List reference standards."""
    shop = context.open()
    if window is not None:
        found = shop.standards.due_within(counted_from(day, "--due-within"), window)
    elif day is not None:
        found = shop.standards.valid_on(day)
    else:
        found = shop.standards.all()
    rows = [
        [
            s.serial,
            f"{s.maker} {s.model_code}",
            s.certificate,
            s.certified_on.isoformat(),
            s.certificate_due.isoformat(),
            str(s.uncertainty),
        ]
        for s in found
    ]
    for line in table(["standard", "make", "certificate", "certified", "due", "uncertainty"], rows):
        click.echo(line)


@standards.command("expired")
@click.option("--on", "day", required=True, help="the day to judge against")
@pass_context
def standard_expired(context: Context, day: str) -> None:
    """List standards whose certificate had run out on a day."""
    shop = context.open()
    found = shop.standards.expired_on(day)
    rows = [[s.serial, s.certificate_due.isoformat(), str(-s.days_left_on(day))] for s in found]
    for line in table(["standard", "due", "days over"], rows):
        click.echo(line)


@click.group("bench")
def benches() -> None:
    """Test benches."""


@benches.command("add")
@click.argument("code")
@click.argument("name")
@click.option("--positions", type=int, required=True, help="how many meters the bench holds")
@click.option(
    "--standard", "standard_serial", required=True, help="the reference standard behind it"
)
@click.option("--max-amps", required=True, help="the most current the bench can hold")
@click.option("--max-volts", required=True, help="the most voltage the bench can hold")
@click.option("--polyphase", is_flag=True, help="the bench can hold polyphase meters")
@click.option("--installed", required=True, help="the day it went into service")
@pass_context
def bench_add(
    context: Context,
    code: str,
    name: str,
    positions: int,
    standard_serial: str,
    max_amps: str,
    max_volts: str,
    polyphase: bool,
    installed: str,
) -> None:
    """Put a bench on the book."""
    shop = context.open()
    bench = Bench.build(
        code,
        name,
        positions=positions,
        standard_serial=standard_serial,
        max_amperes=max_amps,
        max_volts=max_volts,
        polyphase=polyphase,
        installed=installed,
    )
    with shop.transaction():
        shop.benches.add(bench)
    context.say(f"bench {bench} on the book")


@benches.command("restandard")
@click.argument("code")
@click.argument("standard_serial")
@pass_context
def bench_restandard(context: Context, code: str, standard_serial: str) -> None:
    """Put a different standard on a bench."""
    shop = context.open()
    current = shop.benches.get(code)
    wanted = shop.standards.get(standard_serial)
    moved = Bench(
        code=current.code,
        name=current.name,
        positions=current.positions,
        standard_serial=wanted.serial,
        max_amperes=current.max_amperes,
        max_volts=current.max_volts,
        polyphase=current.polyphase,
        installed=current.installed,
        removed=current.removed,
    )
    with shop.transaction():
        shop.benches.save(moved)
    context.say(f"{moved.code} now runs against {wanted.serial}")


@benches.command("list")
@click.option("--on", "day", default=None, help="only benches in service on this day")
@pass_context
def bench_list(context: Context, day: str | None) -> None:
    """List benches."""
    shop = context.open()
    found = shop.benches.available_on(day) if day is not None else shop.benches.all()
    rows = [
        [
            b.code,
            b.name,
            str(b.positions),
            b.standard_serial,
            str(b.max_amperes),
            str(b.max_volts),
            yes_no(b.polyphase),
        ]
        for b in found
    ]
    for line in table(
        ["bench", "name", "positions", "standard", "max amps", "max volts", "polyphase"], rows
    ):
        click.echo(line)


@benches.command("day")
@click.option("--on", "day", required=True, help="the day to plan")
@click.option("--bench", "code", default=None, help="only this bench")
@pass_context
def bench_day(context: Context, day: str, code: str | None) -> None:
    """Fill the benches for a day off the live test orders."""
    shop = context.open()
    planned = rota.plan_day(shop, on=day)
    slots = planned.on_bench(code) if code is not None else list(planned.slots)
    rows = [
        [s.bench_code, str(s.position), s.meter_serial, s.order_reference, str(s.priority)]
        for s in slots
    ]
    for line in table(["bench", "position", "meter", "order", "priority"], rows):
        click.echo(line)
    for reference, why in planned.unplaced:
        click.echo(f"could not place {reference}: {why}")
    load = ", ".join(f"{name} {count}" for name, count in sorted(planned.load().items()))
    click.echo(f"{planned.show()} ({load})")
    if planned.unplaced:
        raise SystemExit(1)


@benches.command("capacity")
@click.option("--on", "day", required=True, help="the day to work this out as at")
@pass_context
def bench_capacity(context: Context, day: str) -> None:
    """How many positions the shop has on a day, and why any are missing."""
    shop = context.open()
    rows = []
    for bench, why in rota.usable_benches(shop, day):
        rows.append([bench.code, str(bench.positions), yes_no(why is None), why or "-"])
    for line in table(["bench", "positions", "usable", "why not"], rows):
        click.echo(line)
    click.echo(f"{rota.capacity(shop, day)} positions on {day}")


@benches.command("show")
@click.argument("code")
@pass_context
def bench_show(context: Context, code: str) -> None:
    """One bench, and the standard behind it."""
    shop = context.open()
    bench = shop.benches.get(code)
    standard = shop.standards.get(bench.standard_serial)
    detail = [
        ("bench", bench.code),
        ("name", bench.name),
        ("positions", str(bench.positions)),
        ("polyphase", yes_no(bench.polyphase)),
        ("max amps", str(bench.max_amperes)),
        ("max volts", str(bench.max_volts)),
        ("installed", bench.installed.isoformat()),
        ("removed", or_dash(None if bench.removed is None else bench.removed.isoformat())),
        ("standard", str(standard)),
        ("uncertainty", f"{standard.uncertainty} percent"),
        ("traceable to", standard.traceable_to),
        ("runs", str(len(shop.runs.on_bench(bench.code)))),
    ]
    for line in pairs(detail):
        click.echo(line)


__all__ = ["benches", "standards"]
