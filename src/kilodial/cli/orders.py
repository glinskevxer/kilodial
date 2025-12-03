"""Work order commands, and the planner that fills the shop's week.

The plan command has a dry run and that is not a nicety. Raising a season's
orders is a hundred rows nobody wants to unpick, and looking at the list before
committing to it is how a supervisor catches a group whose interval was entered
wrong. It prints the same table either way, so what you saw is what you get.
"""

from __future__ import annotations

import click

from kilodial.cli.context import Context, pass_context
from kilodial.cli.render import or_dash, pairs, table
from kilodial.errors import RuleError
from kilodial.orders.order import (
    OrderKind,
    OrderState,
    WorkOrder,
    disposition_named,
    order_kind,
    priority_named,
)
from kilodial.orders.planner import plan, raise_orders


@click.group("work")
def orders() -> None:
    """Shop work orders."""


@orders.command("raise")
@click.argument("reference")
@click.argument("kind")
@click.argument("meter_serial")
@click.option("--on", "day", required=True, help="the day it was raised")
@click.option("--priority", default="normal", show_default=True)
@click.option("--point", "point_code", default=None)
@click.option("--note", default=None)
@pass_context
def order_raise(
    context: Context,
    reference: str,
    kind: str,
    meter_serial: str,
    day: str,
    priority: str,
    point_code: str | None,
    note: str | None,
) -> None:
    """Open one work order by hand."""
    shop = context.open()
    order = WorkOrder.raise_order(
        reference,
        order_kind(kind),
        meter_serial,
        raised_on=day,
        priority=priority_named(priority),
        point_code=point_code,
        note=note,
    )
    with shop.transaction():
        shop.orders.add(order)
    context.say(f"{order}, due {order.due_on.isoformat()}")


@orders.command("assign")
@click.argument("reference")
@click.argument("technician")
@pass_context
def order_assign(context: Context, reference: str, technician: str) -> None:
    """Put a technician's name on an order."""
    shop = context.open()
    with shop.transaction():
        assigned = shop.orders.save(shop.orders.get(reference).assigned(technician))
    context.say(f"{assigned.reference} assigned to {assigned.assigned_to}")


@orders.command("done")
@click.argument("reference")
@click.option("--on", "day", required=True)
@click.option("--run", "run_reference", default=None, help="for a test order")
@click.option("--disposition", default=None, help="for a repair order")
@click.option("--repair", "repair_reference", default=None, help="the repair record")
@pass_context
def order_done(
    context: Context,
    reference: str,
    day: str,
    run_reference: str | None,
    disposition: str | None,
    repair_reference: str | None,
) -> None:
    """Close an order with whatever evidence its kind wants."""
    shop = context.open()
    order = shop.orders.get(reference)
    if run_reference is not None:
        shop.runs.get(run_reference)
    if repair_reference is not None:
        repair = shop.repairs.get(repair_reference)
        if repair.meter_serial != order.meter_serial:
            raise RuleError(
                f"repair {repair.reference} is on meter {repair.meter_serial} and "
                f"order {order.reference} is on {order.meter_serial}"
            )
    with shop.transaction():
        closed = shop.orders.save(
            order.done(
                on=day,
                run_reference=run_reference,
                disposition=None if disposition is None else disposition_named(disposition),
                repair_reference=repair_reference,
            )
        )
    context.say(f"{closed.reference} done after {closed.days_open(day)} days")


@orders.command("cancel")
@click.argument("reference")
@click.option("--on", "day", required=True)
@click.option("--why", required=True, help="cancelling needs a reason")
@pass_context
def order_cancel(context: Context, reference: str, day: str, why: str) -> None:
    """Close an order without doing it."""
    shop = context.open()
    with shop.transaction():
        cancelled = shop.orders.save(shop.orders.get(reference).cancelled(on=day, why=why))
    context.say(f"{cancelled.reference} cancelled")


@orders.command("list")
@click.option("--all", "everything", is_flag=True, help="closed ones too")
@click.option("--meter", "meter_serial", default=None)
@click.option("--kind", default=None)
@click.option("--to", "technician", default=None, help="assigned to this technician")
@click.option("--late", "day", default=None, help="only ones late on this day")
@pass_context
def order_list(
    context: Context,
    everything: bool,
    meter_serial: str | None,
    kind: str | None,
    technician: str | None,
    day: str | None,
) -> None:
    """List work orders, live ones by default."""
    shop = context.open()
    if day is not None:
        found = shop.orders.late_on(day)
    elif meter_serial is not None:
        found = shop.orders.for_meter(meter_serial)
    elif kind is not None:
        found = shop.orders.by_kind(order_kind(kind))
    elif technician is not None:
        found = shop.orders.assigned_to(technician)
    elif everything:
        found = shop.orders.all()
    else:
        found = shop.orders.live()
    rows = [
        [
            o.reference,
            str(o.kind),
            o.meter_serial,
            str(o.priority),
            o.raised_on.isoformat(),
            o.due_on.isoformat(),
            str(o.state),
            or_dash(o.assigned_to),
        ]
        for o in found
    ]
    headings = ["order", "kind", "meter", "priority", "raised", "due", "state", "to"]
    for line in table(headings, rows):
        click.echo(line)


@orders.command("show")
@click.argument("reference")
@pass_context
def order_show(context: Context, reference: str) -> None:
    """One order and everything on it."""
    shop = context.open()
    order = shop.orders.get(reference)
    detail = [
        ("order", order.reference),
        ("kind", str(order.kind)),
        ("meter", order.meter_serial),
        ("point", or_dash(order.point_code)),
        ("priority", str(order.priority)),
        ("raised", order.raised_on.isoformat()),
        ("due", order.due_on.isoformat()),
        ("state", str(order.state)),
        ("assigned to", or_dash(order.assigned_to)),
        ("closed", or_dash(None if order.closed_on is None else order.closed_on.isoformat())),
        ("run", or_dash(order.run_reference)),
        ("disposition", or_dash(None if order.disposition is None else str(order.disposition))),
        ("repair", or_dash(order.repair_reference)),
        ("note", or_dash(order.note)),
    ]
    for line in pairs(detail):
        click.echo(line)


@orders.command("plan")
@click.option("--on", "day", required=True, help="the day to plan from")
@click.option("--limit", type=int, default=None, help="cap the number raised")
@click.option("--raise", "commit", is_flag=True, help="actually put them on the book")
@pass_context
def order_plan(context: Context, day: str, limit: int | None, commit: bool) -> None:
    """Work out the test orders the due list calls for."""
    shop = context.open()
    if commit:
        with shop.transaction():
            planned = raise_orders(shop, on=day, limit=limit)
    else:
        planned = plan(shop, on=day, limit=limit)
    rows = [
        [o.reference, o.meter_serial, str(o.priority), o.due_on.isoformat(), or_dash(o.note)]
        for o in planned.orders
    ]
    for line in table(["order", "meter", "priority", "due", "why"], rows):
        click.echo(line)
    for serial, why in planned.skipped:
        click.echo(f"skipped {serial}: {why}")
    click.echo(planned.show() + ("" if commit else ", nothing written"))


@orders.command("counts")
@pass_context
def order_counts(context: Context) -> None:
    """How many orders are in each state."""
    shop = context.open()
    counts = shop.orders.counts_by_state()
    rows = [[str(state), str(counts[state])] for state in OrderState]
    for line in table(["state", "orders"], rows):
        click.echo(line)


@orders.command("kinds")
def order_kinds() -> None:
    """The kinds of order the shop raises, and what closes each."""
    rows = []
    for kind in OrderKind:
        closes = "a run" if kind.needs_run else ("a disposition" if kind.needs_disposition else "-")
        rows.append([kind.label, closes])
    for line in table(["kind", "closes with"], rows):
        click.echo(line)


__all__ = ["orders"]
