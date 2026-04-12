"""Billed history and adjustment commands.

The adjustment command prints the month by month working rather than a single
figure, and it prints it the same way whether the answer is a refund or a back
bill. That is not politeness: a customer who is being back billed has exactly
the same right to check the arithmetic as one being refunded, and a shop that
produces a detailed sheet in one direction and a bare total in the other looks
like it is hiding something even when it is not.
"""

from __future__ import annotations

import click

from kilodial.adjust.compute import Adjustment, BilledMonth
from kilodial.adjust.rules import STATE_TARIFF
from kilodial.adjust.service import Refusal, raise_adjustment
from kilodial.cli.context import Context, pass_context
from kilodial.cli.render import or_dash, pairs, table
from kilodial.cli.transformers import load_factor
from kilodial.cli.window import span_of


@click.group("bill")
def bills() -> None:
    """What the customer was charged, which an adjustment works off."""


@bills.command("add")
@click.argument("point_code")
@click.option("--from", "first", required=True, help="first day of the billing period")
@click.option("--to", "last", required=True, help="last day of the billing period")
@click.option("--amount", required=True, help="what was charged")
@click.option("--kwh", default=None, help="energy billed, if it is known")
@pass_context
def bill_add(
    context: Context, point_code: str, first: str, last: str, amount: str, kwh: str | None
) -> None:
    """Record one billing period."""
    shop = context.open()
    month = BilledMonth.of(first, last, amount)
    with shop.transaction():
        shop.billing.add(point_code, month, kwh=kwh)
    context.say(f"billed {month} on {point_code.strip().upper()}")


@bills.command("list")
@click.argument("point_code")
@click.option("--from", "first", default=None, help="start of the window")
@click.option("--to", "last", default=None, help="end of the window")
@pass_context
def bill_list(context: Context, point_code: str, first: str | None, last: str | None) -> None:
    """List a point's billed history."""
    shop = context.open()
    code = shop.points.get(point_code).code
    months = shop.billing.for_point(code)
    window = span_of(first, last)
    if window is not None:
        months = shop.billing.covering(code, window)
    rows = [
        [
            m.span.start.isoformat(),
            "-" if m.span.end is None else m.span.end.isoformat(),
            str(m.span.days),
            str(m.amount),
            or_dash(shop.billing.kwh_for(code, m.span.start)),
        ]
        for m in months
    ]
    for line in table(["from", "to", "days", "amount", "kwh"], rows):
        click.echo(line)


@bills.command("remove")
@click.argument("point_code")
@click.argument("first_day")
@click.confirmation_option(prompt="take that billing period off the book?")
@pass_context
def bill_remove(context: Context, point_code: str, first_day: str) -> None:
    """Take one billing period back off the book."""
    shop = context.open()
    with shop.transaction():
        shop.billing.delete(point_code, first_day)
    context.say(f"removed the period starting {first_day} on {point_code.strip().upper()}")


@click.group("adjust")
def adjustments() -> None:
    """Billing adjustments for meters found out of tolerance."""


@adjustments.command("show")
@click.argument("point_code")
@click.option("--on", "day", required=True, help="the day the adjustment is worked out")
@click.option(
    "--pf", "power_factor", default="unity", show_default=True, help="the load angle to judge at"
)
@pass_context
def adjust_show(context: Context, point_code: str, day: str, power_factor: str) -> None:
    """Work out an adjustment and print the month by month sheet."""
    shop = context.open()
    found = raise_adjustment(shop, point_code, on=day, power_factor=load_factor(power_factor))
    if isinstance(found, Refusal):
        click.echo(str(found))
        return
    _print_header(found)
    click.echo("")
    rows = [
        [
            line.span.start.isoformat(),
            "-" if line.span.end is None else line.span.end.isoformat(),
            str(line.span.days),
            str(line.billed),
            str(line.moved),
            str(line.interest),
            str(line.total),
        ]
        for line in found.lines
    ]
    rows.append(
        [
            "",
            "",
            str(found.period.days),
            str(found.billed),
            str(found.moved),
            str(found.interest),
            str(found.total),
        ]
    )
    for line in table(["from", "to", "days", "billed", "moved", "interest", "total"], rows):
        click.echo(line)


def _print_header(found: Adjustment) -> None:
    detail = [
        ("point", found.point_code),
        ("meter", found.meter_serial),
        ("direction", str(found.direction)),
        ("period", str(found.period.span)),
        ("period starts at", str(found.period.reason)),
        ("tariff", found.tariff.name),
        ("share of the bill", f"{found.share * 100:.4f} percent"),
        ("total", str(found.total)),
    ]
    for line in pairs(detail):
        click.echo(line)


@adjustments.command("period")
@click.argument("point_code")
@click.option("--on", "day", required=True, help="the day to work the period out as at")
@click.option(
    "--pf", "power_factor", default="unity", show_default=True, help="the load angle to judge at"
)
@pass_context
def adjust_period(context: Context, point_code: str, day: str, power_factor: str) -> None:
    """The period an adjustment would cover, and what bounds it."""
    shop = context.open()
    found = raise_adjustment(shop, point_code, on=day, power_factor=load_factor(power_factor))
    if isinstance(found, Refusal):
        click.echo(str(found))
        return
    period = found.period
    detail = [
        ("point", found.point_code),
        ("period", str(period.span)),
        ("days", str(period.days)),
        ("starts at", str(period.reason)),
        ("tariff cap reaches", period.capped_at.isoformat()),
        ("meter set", period.set_at.isoformat()),
        (
            "last clean test",
            or_dash(None if period.clean_at is None else period.clean_at.isoformat()),
        ),
        ("lookback", f"{found.tariff.cap_for(found.direction, multiplier=False)} months"),
    ]
    for line in pairs(detail):
        click.echo(line)


@adjustments.command("tariff")
def adjust_tariff() -> None:
    """The rules adjustments are worked out under."""
    tariff = STATE_TARIFF
    detail = [
        ("tariff", tariff.name),
        ("tolerance", f"+/-{tariff.tolerance} percent"),
        ("refund lookback", f"{tariff.refund_months} months"),
        ("back bill lookback", f"{tariff.back_bill_months} months"),
        ("multiplier lookback", f"{tariff.multiplier_months} months"),
        ("refund interest", f"{tariff.refund_interest * 100} percent a year"),
    ]
    for line in pairs(detail):
        click.echo(line)


__all__ = ["adjustments", "bills"]
