"""Repair record commands.

``faults`` is the report that changes a purchasing decision. It counts what went
wrong by type, and a type whose board failures outnumber everything else is a
type to stop buying whatever its accuracy record looks like.
"""

from __future__ import annotations

import click

from kilodial.cli.context import Context, pass_context
from kilodial.cli.render import or_dash, pairs, table
from kilodial.cli.window import span_of
from kilodial.model.repair import Fault, Repair, families, fault_named


@click.group("repair")
def repairs() -> None:
    """What was wrong with a meter and what it took to fix."""


@repairs.command("record")
@click.argument("reference")
@click.argument("meter_serial")
@click.argument("fault")
@click.option("--on", "day", required=True, help="the day it was repaired")
@click.option("--by", "technician", required=True)
@click.option("--hours", required=True, help="time on the bench")
@click.option("--parts", default="0", show_default=True, help="what the parts cost")
@click.option("--replacement", required=True, help="what a new meter would cost")
@click.option("--note", default=None)
@pass_context
def repair_record(
    context: Context,
    reference: str,
    meter_serial: str,
    fault: str,
    day: str,
    technician: str,
    hours: str,
    parts: str,
    replacement: str,
    note: str | None,
) -> None:
    """Write a repair down."""
    shop = context.open()
    repair = Repair.build(
        reference,
        meter_serial,
        fault_named(fault),
        repaired_on=day,
        by=technician,
        hours=hours,
        parts=parts,
        replacement_cost=replacement,
        note=note,
    )
    with shop.transaction():
        shop.repairs.add(repair)
    context.say(f"{repair}: {repair.verdict()}")


@repairs.command("list")
@click.option("--meter", "meter_serial", default=None)
@click.option("--fault", default=None)
@click.option("--from", "first", default=None)
@click.option("--to", "last", default=None)
@click.option("--wasteful", is_flag=True, help="only ones that cost more than a meter")
@pass_context
def repair_list(
    context: Context,
    meter_serial: str | None,
    fault: str | None,
    first: str | None,
    last: str | None,
    wasteful: bool,
) -> None:
    """List repairs."""
    shop = context.open()
    if wasteful:
        found = shop.repairs.not_worth_it()
    elif meter_serial is not None:
        found = shop.repairs.for_meter(meter_serial)
    elif fault is not None:
        found = shop.repairs.by_fault(fault_named(fault))
    elif (window := span_of(first, last)) is not None:
        found = shop.repairs.between(window.start, window.end)
    else:
        found = shop.repairs.all()
    rows = [
        [
            r.reference,
            r.meter_serial,
            str(r.fault),
            r.repaired_on.isoformat(),
            str(r.hours.normalize()),
            str(r.parts),
            str(r.cost),
            "yes" if r.was_worth_it else "no",
        ]
        for r in found
    ]
    headings = ["repair", "meter", "fault", "on", "hours", "parts", "cost", "worth it"]
    for line in table(headings, rows):
        click.echo(line)


@repairs.command("show")
@click.argument("reference")
@pass_context
def repair_show(context: Context, reference: str) -> None:
    """One repair and what it came to."""
    shop = context.open()
    repair = shop.repairs.get(reference)
    detail = [
        ("repair", repair.reference),
        ("meter", repair.meter_serial),
        ("fault", str(repair.fault)),
        ("family", repair.fault.family),
        ("repaired", repair.repaired_on.isoformat()),
        ("by", repair.by),
        ("hours", str(repair.hours.normalize())),
        ("labour", str(repair.labour)),
        ("parts", str(repair.parts)),
        ("cost", str(repair.cost)),
        ("replacement", str(repair.replacement_cost)),
        ("share", f"{repair.share_of_replacement * 100:.2f} percent"),
        ("verdict", repair.verdict()),
        ("note", or_dash(repair.note)),
    ]
    for line in pairs(detail):
        click.echo(line)


@repairs.command("faults")
@click.option("--type", "device_key", default=None, help="only this device type")
@pass_context
def repair_faults(context: Context, device_key: str | None) -> None:
    """Count what went wrong, which is the question a purchase order asks."""
    shop = context.open()
    counts = (
        shop.repairs.counts_for_device(device_key)
        if device_key is not None
        else shop.repairs.counts_by_fault()
    )
    total = sum(counts.values())
    rows = []
    for fault in Fault:
        share = "0.0" if total == 0 else f"{counts[fault] / total * 100:.1f}"
        rows.append([fault.label, fault.family, str(counts[fault]), share])
    for line in table(["fault", "family", "repairs", "percent"], rows):
        click.echo(line)
    click.echo(f"{total} repairs across {len(families())} families")


@repairs.command("spend")
@click.option("--from", "first", required=True)
@click.option("--to", "last", required=True)
@pass_context
def repair_spend(context: Context, first: str, last: str) -> None:
    """What the shop spent on repairs over a window."""
    shop = context.open()
    found = shop.repairs.between(first, last)
    wasteful = [r for r in found if r.fault.is_a_fault and not r.was_worth_it]
    detail = [
        ("window", f"{first} to {last}"),
        ("repairs", str(len(found))),
        ("spent", str(shop.repairs.spent_between(first, last))),
        ("not worth doing", str(len(wasteful))),
        ("nothing found", str(sum(1 for r in found if not r.fault.is_a_fault))),
    ]
    for line in pairs(detail):
        click.echo(line)


__all__ = ["repairs"]
