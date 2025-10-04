"""Device type commands.

The catalogue is the first thing anybody sets up on a new book, because a meter
cannot be received against a type that is not there, so these commands take the
long option list rather than a file. It is entered once per model, not once per
meter.
"""

from __future__ import annotations

import click

from kilodial.cli.context import Context, pass_context
from kilodial.cli.render import or_dash, pairs, table, yes_no
from kilodial.model.device import DeviceType
from kilodial.model.form import MeterClass, Technology, meter_class
from kilodial.units.span import parse_date

TECHNOLOGIES = {t.name.lower(): t for t in Technology}


def _technology(text: str) -> Technology:
    key = text.strip().lower().replace(" ", "_")
    if key not in TECHNOLOGIES:
        raise click.BadParameter(f"{text!r} is not one of {', '.join(sorted(TECHNOLOGIES))}")
    return TECHNOLOGIES[key]


@click.group("device")
def devices() -> None:
    """The catalogue of meter models the shop stocks."""


@devices.command("add")
@click.argument("manufacturer")
@click.argument("model_code")
@click.option("--form", "form_code", required=True, help="ANSI form, such as 2S or 16S")
@click.option("--class", "class_code", required=True, help="meter class, such as CL200")
@click.option("--volts", required=True, help="nameplate voltage")
@click.option("--kh", required=True, help="watthour constant per revolution or pulse")
@click.option("--tech", default="induction", show_default=True, help="induction or solid_state")
@click.option("--ratio", default=None, help="register ratio, required on an induction meter")
@click.option("--demand", is_flag=True, help="the type registers demand as well as energy")
@click.option("--interval", "demand_interval", default=None, help="demand window in minutes")
@click.option("--introduced", required=True, help="first day the shop bought this type")
@click.option("--retired", default=None, help="last day the shop bought this type")
@pass_context
def device_add(
    context: Context,
    manufacturer: str,
    model_code: str,
    form_code: str,
    class_code: str,
    volts: str,
    kh: str,
    tech: str,
    ratio: str | None,
    demand: bool,
    demand_interval: str | None,
    introduced: str,
    retired: str | None,
) -> None:
    """Put a meter model on the catalogue."""
    shop = context.open()
    device = DeviceType.build(
        manufacturer,
        model_code,
        form_code=form_code,
        class_code=class_code,
        voltage=volts,
        kh=kh,
        technology=_technology(tech),
        register_ratio=ratio,
        demand_capable=demand,
        demand_interval=demand_interval,
        introduced=introduced,
        retired=retired,
    )
    with shop.transaction():
        shop.devices.add(device)
    context.say(f"catalogued {device}")


@devices.command("list")
@click.option("--class", "class_code", default=None, help="only this meter class")
@click.option("--tech", default=None, help="only this technology")
@click.option("--on", "day", default=None, help="only types the shop bought on this day")
@pass_context
def device_list(
    context: Context, class_code: str | None, tech: str | None, day: str | None
) -> None:
    """List the catalogue."""
    shop = context.open()
    if class_code is not None:
        found = shop.devices.by_class(meter_class(class_code))
    elif tech is not None:
        found = shop.devices.by_technology(_technology(tech))
    else:
        found = shop.devices.all()
    if day is not None:
        wanted = parse_date(day)
        found = [d for d in found if d.was_current_on(wanted)]
    rows = [
        [
            d.key,
            d.form.code,
            d.meter_class.code,
            str(d.voltage.value.normalize()),
            str(d.kh),
            d.technology.value,
            or_dash(None if d.retired is None else d.retired.isoformat()),
        ]
        for d in found
    ]
    for line in table(["type", "form", "class", "volts", "kh", "technology", "retired"], rows):
        click.echo(line)


@devices.command("show")
@click.argument("key")
@pass_context
def device_show(context: Context, key: str) -> None:
    """Everything on one catalogue entry."""
    shop = context.open()
    d = shop.devices.get(key)
    meters = shop.meters.by_device(d.key)
    detail = [
        ("type", d.key),
        ("form", f"{d.form.code} ({d.form.service}, {d.form.elements} element)"),
        ("class", f"{d.meter_class.code} at {d.test_amperes}"),
        ("volts", str(d.voltage)),
        ("kh", str(d.kh)),
        ("technology", str(d.technology)),
        ("register ratio", or_dash(d.register_ratio)),
        ("demand", yes_no(d.demand_capable)),
        ("demand interval", or_dash(d.demand_interval)),
        ("transformer rated", yes_no(d.is_transformer_rated)),
        ("introduced", d.introduced.isoformat()),
        ("retired", or_dash(None if d.retired is None else d.retired.isoformat())),
        ("meters on the book", str(len(meters))),
    ]
    for line in pairs(detail):
        click.echo(line)


@devices.command("retire")
@click.argument("key")
@click.option("--on", "day", required=True, help="last day the shop bought this type")
@pass_context
def device_retire(context: Context, key: str, day: str) -> None:
    """Close a catalogue entry off."""
    shop = context.open()
    current = shop.devices.get(key)
    retired = DeviceType(
        manufacturer=current.manufacturer,
        model_code=current.model_code,
        form=current.form,
        meter_class=current.meter_class,
        voltage=current.voltage,
        kh=current.kh,
        technology=current.technology,
        register_ratio=current.register_ratio,
        demand_capable=current.demand_capable,
        demand_interval=current.demand_interval,
        introduced=current.introduced,
        retired=parse_date(day),
    )
    with shop.transaction():
        shop.devices.replace(retired)
    context.say(f"{retired.key} retired on {day}")


__all__ = ["TECHNOLOGIES", "MeterClass", "devices"]
