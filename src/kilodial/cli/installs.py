"""Service point and meter set commands.

The accuracy command is where most of this package finally meets: it pulls the
set standing at a point, the meter's own as found registration, and the
transformers behind it, and reports the two kinds of error separately. A
technician looking at that output can tell in one line whether they are being
sent to change a meter or to correct a number in the billing system, and those
are different trucks.
"""

from __future__ import annotations

import click

from kilodial.cli.context import Context, pass_context
from kilodial.cli.render import or_dash, pairs, table, yes_no
from kilodial.cli.transformers import load_factor
from kilodial.errors import BadInputError
from kilodial.install.point import MeterSet, ServicePoint
from kilodial.model.form import Service

SERVICES = {s.value: s for s in Service}


def service_named(text: str) -> Service:
    """Read a service code the way a crew writes it, refusing the rest."""
    key = text.strip().upper()
    if key not in SERVICES:
        raise BadInputError(f"{text!r} is not one of {', '.join(sorted(SERVICES))}")
    return SERVICES[key]


@click.group("point")
def points() -> None:
    """Service points, and what is set at them."""


@points.command("add")
@click.argument("code")
@click.option("--account", required=True)
@click.option("--address", required=True)
@click.option("--service", required=True, help="1P2W, 1P3W, 3P3W, 3P4WY, 3P4WD or NET3W")
@click.option("--volts", required=True)
@click.option("--rate", "rate_code", required=True)
@click.option("--energised", required=True)
@pass_context
def point_add(
    context: Context,
    code: str,
    account: str,
    address: str,
    service: str,
    volts: str,
    rate_code: str,
    energised: str,
) -> None:
    """Put a service point on the book."""
    shop = context.open()
    point = ServicePoint.build(
        code,
        account=account,
        address=address,
        service=service_named(service),
        voltage=volts,
        rate_code=rate_code,
        energised=energised,
    )
    with shop.transaction():
        shop.points.add(point)
    context.say(f"service point {point} on the book")


@points.command("disconnect")
@click.argument("code")
@click.option("--on", "day", required=True)
@pass_context
def point_disconnect(context: Context, code: str, day: str) -> None:
    """Close a service point off."""
    shop = context.open()
    current = shop.points.get(code)
    closed = ServicePoint.build(
        current.code,
        account=current.account,
        address=current.address,
        service=current.service,
        voltage=current.voltage.value,
        rate_code=current.rate_code,
        energised=current.energised,
        disconnected=day,
    )
    with shop.transaction():
        shop.points.save(closed)
    context.say(f"{closed.code} disconnected on {day}")


@points.command("set")
@click.argument("code")
@click.argument("meter_serial")
@click.option("--ct", "ct_serial", default=None)
@click.option("--vt", "vt_serial", default=None)
@click.option("--register-multiplier", default="1", show_default=True)
@click.option("--multiplier", "programmed_multiplier", required=True, help="as programmed")
@click.option("--on", "set_on", required=True)
@pass_context
def point_set(
    context: Context,
    code: str,
    meter_serial: str,
    ct_serial: str | None,
    vt_serial: str | None,
    register_multiplier: str,
    programmed_multiplier: str,
    set_on: str,
) -> None:
    """Set a meter at a service point."""
    shop = context.open()
    meter = shop.meters.get(meter_serial)
    for serial in (ct_serial, vt_serial):
        if serial is not None:
            shop.transformers.get(serial)
    meter_set = MeterSet.build(
        code,
        meter.serial,
        ct_serial=ct_serial,
        vt_serial=vt_serial,
        register_multiplier=register_multiplier,
        programmed_multiplier=programmed_multiplier,
        set_on=set_on,
    )
    with shop.transaction():
        shop.installs.set_meter(meter_set)
        context.log("set", f"point {meter_set.point_code}", meter_set.meter_serial)
    context.say(f"set {meter_set}")


@points.command("pull")
@click.argument("code")
@click.option("--on", "day", required=True)
@pass_context
def point_pull(context: Context, code: str, day: str) -> None:
    """Pull whatever meter is standing at a service point."""
    shop = context.open()
    with shop.transaction():
        pulled = shop.installs.pull(code, day)
        context.log("pulled", f"point {pulled.point_code}", pulled.meter_serial)
    context.say(f"pulled {pulled.meter_serial} off {pulled.point_code} on {day}")


@points.command("list")
@click.option("--account", default=None)
@click.option("--on", "day", default=None, help="only points live on this day")
@pass_context
def point_list(context: Context, account: str | None, day: str | None) -> None:
    """List service points."""
    shop = context.open()
    if account is not None:
        found = shop.points.by_account(account)
    elif day is not None:
        found = shop.points.live_on(day)
    else:
        found = shop.points.all()
    rows = []
    for point in found:
        standing = shop.installs.current(point.code)
        rows.append(
            [
                point.code,
                point.account,
                point.address,
                point.service.value,
                point.rate_code,
                or_dash(None if standing is None else standing.meter_serial),
            ]
        )
    for line in table(["point", "account", "address", "service", "rate", "meter"], rows):
        click.echo(line)


@points.command("history")
@click.argument("code")
@pass_context
def point_history(context: Context, code: str) -> None:
    """Every meter that has ever stood at a service point."""
    shop = context.open()
    point = shop.points.get(code)
    rows = [
        [
            s.meter_serial,
            s.set_on.isoformat(),
            "-" if s.removed_on is None else s.removed_on.isoformat(),
            or_dash(s.ct_serial),
            or_dash(s.vt_serial),
            f"{s.programmed_multiplier.normalize():f}",
        ]
        for s in shop.installs.history(point.code)
    ]
    for line in table(["meter", "set", "pulled", "ct", "vt", "multiplier"], rows):
        click.echo(line)


@points.command("accuracy")
@click.argument("code")
@click.option("--on", "day", default=None, help="the day the set was standing")
@click.option("--pf", "power_factor", default="unity", show_default=True)
@pass_context
def point_accuracy(context: Context, code: str, day: str | None, power_factor: str) -> None:
    """What the installation at a point registers, and why."""
    shop = context.open()
    found = shop.installed_accuracy(code, on=day, power_factor=load_factor(power_factor))
    detail = [
        ("point", code.strip().upper()),
        ("load", str(found.power_factor)),
        ("meter", str(found.meter)),
        ("current transformer", or_dash(found.current_transformer)),
        ("voltage transformer", or_dash(found.voltage_transformer)),
        ("overall", str(found.overall)),
        ("multiplier programmed", f"{found.programmed_multiplier.normalize():f}"),
        ("multiplier computed", f"{found.expected_multiplier.normalize():f}"),
        ("multiplier right", yes_no(found.multiplier_is_right)),
        ("as billed", str(found.billed_registration)),
    ]
    for line in pairs(detail):
        click.echo(line)
    for fault in found.faults():
        click.echo(fault)
    if found.faults():
        raise SystemExit(1)


__all__ = ["SERVICES", "points", "service_named"]
