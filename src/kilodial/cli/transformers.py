"""Instrument transformer commands.

The check command is the one people use. It answers whether a transformer is
holding the class stamped on it, and it takes the power factor as an argument
rather than assuming unity, because that is the whole point: a transformer with
a phase angle error passes at unity and fails on a motor load, and asking the
question without naming a load gets an answer that means nothing.
"""

from __future__ import annotations

import click

from kilodial.cli.context import Context, pass_context
from kilodial.cli.render import pairs, table, yes_no
from kilodial.errors import BadInputError
from kilodial.units.electrical import PowerFactor, Sense
from kilodial.xfmr.transformer import InstrumentTransformer, TransformerKind, accuracy_class

KINDS = {k.value: k for k in TransformerKind}


def transformer_kind(text: str) -> TransformerKind:
    key = text.strip().lower()
    if key not in KINDS:
        raise BadInputError(f"{text!r} is not one of {', '.join(sorted(KINDS))}")
    return KINDS[key]


def load_factor(text: str) -> PowerFactor:
    """Read a power factor written the way a technician says it out loud."""
    parts = text.strip().lower().split()
    value = parts[0]
    if value in ("1", "1.0", "unity"):
        return PowerFactor.unity()
    if len(parts) < 2:
        raise BadInputError(f"{text!r} needs a sense, such as '0.5 lagging'")
    sense = parts[1]
    if sense.startswith("lag"):
        return PowerFactor(value, Sense.LAGGING)
    if sense.startswith("lead"):
        return PowerFactor(value, Sense.LEADING)
    raise BadInputError(f"{sense!r} is neither lagging nor leading")


@click.group("xfmr")
def transformers() -> None:
    """Current and voltage transformers."""


@transformers.command("add")
@click.argument("serial")
@click.option("--kind", required=True, help="current or voltage")
@click.option("--maker", required=True)
@click.option("--ratio", "marked_ratio", required=True, help="marked ratio as a number")
@click.option("--accuracy", required=True, help="0.3, 0.6 or 1.2")
@click.option("--rcf", required=True, help="ratio correction factor")
@click.option("--minutes", "phase_minutes", default="0", show_default=True)
@click.option("--burden", default="B0.1", show_default=True)
@click.option("--tested", required=True, help="the day it was last tested")
@pass_context
def transformer_add(
    context: Context,
    serial: str,
    kind: str,
    maker: str,
    marked_ratio: str,
    accuracy: str,
    rcf: str,
    phase_minutes: str,
    burden: str,
    tested: str,
) -> None:
    """Put an instrument transformer on the book."""
    shop = context.open()
    transformer = InstrumentTransformer.build(
        serial,
        kind=transformer_kind(kind),
        maker=maker,
        marked_ratio=marked_ratio,
        accuracy=accuracy,
        rcf=rcf,
        phase_minutes=phase_minutes,
        burden=burden,
        tested_on=tested,
    )
    with shop.transaction():
        shop.transformers.add(transformer)
    context.say(f"transformer {transformer} on the book")


@transformers.command("retest")
@click.argument("serial")
@click.option("--rcf", required=True)
@click.option("--minutes", "phase_minutes", required=True)
@click.option("--tested", required=True)
@click.option("--burden", default=None)
@pass_context
def transformer_retest(
    context: Context,
    serial: str,
    rcf: str,
    phase_minutes: str,
    tested: str,
    burden: str | None,
) -> None:
    """Record a new test against a transformer already on the book."""
    shop = context.open()
    current = shop.transformers.get(serial)
    retested = InstrumentTransformer.build(
        current.serial,
        kind=current.kind,
        maker=current.maker,
        marked_ratio=current.marked_ratio,
        accuracy=current.accuracy,
        rcf=rcf,
        phase_minutes=phase_minutes,
        burden=current.burden if burden is None else burden,
        tested_on=tested,
    )
    with shop.transaction():
        shop.transformers.save(retested)
    context.say(f"{retested.serial} retested, RCF {current.rcf} is now {retested.rcf}")


@transformers.command("list")
@click.option("--kind", default=None, help="current or voltage")
@click.option("--accuracy", default=None, help="0.3, 0.6 or 1.2")
@click.option("--tested-before", "before", default=None, help="only ones older than this day")
@pass_context
def transformer_list(
    context: Context, kind: str | None, accuracy: str | None, before: str | None
) -> None:
    """List instrument transformers."""
    shop = context.open()
    if before is not None:
        found = shop.transformers.tested_before(before)
    elif kind is not None:
        found = shop.transformers.by_kind(transformer_kind(kind))
    elif accuracy is not None:
        found = shop.transformers.by_accuracy(accuracy_class(accuracy))
    else:
        found = shop.transformers.all()
    rows = [
        [
            t.serial,
            t.kind.value,
            f"{t.marked_ratio.normalize():f}",
            t.accuracy.code,
            str(t.rcf),
            f"{t.phase_minutes.normalize():f}",
            t.burden,
            t.tested_on.isoformat(),
        ]
        for t in found
    ]
    headings = ["serial", "kind", "ratio", "class", "rcf", "minutes", "burden", "tested"]
    for line in table(headings, rows):
        click.echo(line)


@transformers.command("check")
@click.argument("serial")
@click.option("--pf", "power_factor", default="unity", show_default=True, help="the load angle")
@pass_context
def transformer_check(context: Context, serial: str, power_factor: str) -> None:
    """Say whether a transformer holds its class at a given load."""
    shop = context.open()
    transformer = shop.transformers.get(serial)
    load = load_factor(power_factor)
    low, high = transformer.accuracy.limits
    detail = [
        ("transformer", transformer.serial),
        ("kind", str(transformer.kind)),
        ("marked ratio", f"{transformer.marked_ratio.normalize():f}"),
        ("true ratio", f"{transformer.true_ratio.normalize():f}"),
        ("load", str(load)),
        ("rcf", str(transformer.rcf)),
        ("pacf", str(transformer.pacf(load))),
        ("tcf", str(transformer.tcf(load))),
        ("class limits", f"{low} to {high}"),
        ("contribution", str(transformer.contribution(load))),
        ("holds class", yes_no(transformer.within_class(load))),
    ]
    for line in pairs(detail):
        click.echo(line)
    if not transformer.within_class(load):
        raise SystemExit(1)


@transformers.command("where")
@click.argument("serial")
@pass_context
def transformer_where(context: Context, serial: str) -> None:
    """Which service points a transformer has been installed at."""
    shop = context.open()
    transformer = shop.transformers.get(serial)
    rows = [
        [
            s.point_code,
            s.meter_serial,
            s.set_on.isoformat(),
            "-" if s.removed_on is None else s.removed_on.isoformat(),
        ]
        for s in shop.installs.using_transformer(transformer.serial)
    ]
    for line in table(["point", "meter", "set", "pulled"], rows):
        click.echo(line)


__all__ = ["KINDS", "load_factor", "transformer_kind", "transformers"]
