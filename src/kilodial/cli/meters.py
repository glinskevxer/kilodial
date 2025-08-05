"""Meter asset commands.

The move command is the one that matters. It takes the state by name and lets
the model refuse an illegal move, rather than offering a separate command per
transition, because a per transition command set drifts out of step with the
transition table the moment somebody adds a state.
"""

from __future__ import annotations

import click

from kilodial.cli.context import Context, pass_context
from kilodial.cli.render import or_dash, pairs, table
from kilodial.errors import BadInputError
from kilodial.model.meter import Meter, MeterState

STATES = {s.value: s for s in MeterState}


def state_named(text: str) -> MeterState:
    """Read a meter state by name, naming the alternatives when it is wrong."""
    key = text.strip().lower()
    if key not in STATES:
        raise BadInputError(f"{text!r} is not one of {', '.join(sorted(STATES))}")
    return STATES[key]


@click.group("meter")
def meters() -> None:
    """The meters themselves."""


@meters.command("receive")
@click.argument("serial")
@click.option("--type", "device_key", required=True, help="catalogue key, maker/model")
@click.option("--acquired", required=True, help="the day the shop took delivery")
@click.option("--owner", default="utility", show_default=True, help="who owns the asset")
@click.option("--seal", default=None, help="seal number if one is on it")
@click.option(
    "--uncatalogued",
    is_flag=True,
    help="take delivery of a type that is not on the catalogue yet",
)
@pass_context
def meter_receive(
    context: Context,
    serial: str,
    device_key: str,
    acquired: str,
    owner: str,
    seal: str | None,
    uncatalogued: bool,
) -> None:
    """Book a meter in for the first time."""
    shop = context.open()
    meter = Meter.receive(serial, device_key, acquired=acquired, owner=owner, seal=seal)
    with shop.transaction():
        shop.meters.add(meter, require_device=not uncatalogued)
    context.say(f"received {meter}")


@meters.command("move")
@click.argument("serial")
@click.argument("state")
@click.option("--on", "day", default=None, help="the day it happened, needed for scrap")
@pass_context
def meter_move(context: Context, serial: str, state: str, day: str | None) -> None:
    """Move a meter to another state."""
    shop = context.open()
    with shop.transaction():
        moved = shop.meters.move(serial, state_named(state), on=day)
    context.say(f"{moved.serial} is now {moved.state}")


@meters.command("seal")
@click.argument("serial")
@click.argument("seal", required=False)
@pass_context
def meter_seal(context: Context, serial: str, seal: str | None) -> None:
    """Put a seal on a meter, or cut the old one off by leaving it out."""
    shop = context.open()
    with shop.transaction():
        resealed = shop.meters.reseal(serial, seal)
    context.say(f"{resealed.serial} seal is now {or_dash(resealed.seal)}")


@meters.command("list")
@click.option("--state", default=None, help="only meters in this state")
@click.option("--type", "device_key", default=None, help="only meters of this type")
@click.option("--in-shop", is_flag=True, help="only meters a bench could take today")
@pass_context
def meter_list(context: Context, state: str | None, device_key: str | None, in_shop: bool) -> None:
    """List meters."""
    shop = context.open()
    if in_shop:
        found = shop.meters.in_shop()
    elif state is not None:
        found = shop.meters.by_state(state_named(state))
    elif device_key is not None:
        found = shop.meters.by_device(device_key)
    else:
        found = shop.meters.all()
    rows = [
        [
            m.serial,
            m.device_key,
            m.state.value,
            m.acquired.isoformat(),
            m.owner,
            or_dash(m.seal),
        ]
        for m in found
    ]
    for line in table(["serial", "type", "state", "acquired", "owner", "seal"], rows):
        click.echo(line)


@meters.command("show")
@click.argument("serial")
@pass_context
def meter_show(context: Context, serial: str) -> None:
    """Everything on one meter, including its run history."""
    shop = context.open()
    meter = shop.meters.get(serial)
    device = shop.devices.find(meter.device_key)
    runs = shop.runs.for_meter(meter.serial)
    detail = [
        ("serial", meter.serial),
        ("type", meter.device_key if device is None else str(device)),
        ("state", str(meter.state)),
        ("acquired", meter.acquired.isoformat()),
        ("owner", meter.owner),
        ("seal", or_dash(meter.seal)),
        ("retired", or_dash(None if meter.retired_on is None else meter.retired_on.isoformat())),
        ("runs", str(len(runs))),
    ]
    for line in pairs(detail):
        click.echo(line)
    if runs:
        click.echo("")
        rows = [[r.reference, r.tested_on.isoformat(), str(r.kind), r.technician] for r in runs]
        for line in table(["run", "tested", "kind", "by"], rows):
            click.echo(line)


@meters.command("counts")
@pass_context
def meter_counts(context: Context) -> None:
    """How many meters are in each state."""
    shop = context.open()
    counts = shop.meters.counts_by_state()
    rows = [[state.value, str(counts[state])] for state in MeterState]
    for line in table(["state", "meters"], rows):
        click.echo(line)


__all__ = ["STATES", "meters", "state_named"]
