"""Tamper finding commands.

Confirming is a separate command from logging and it asks for two things a
suspicion does not have: the day the interference is judged to have started, and
what was actually seen. Both are required because a confirmed finding triples
the back bill window, and a three year bill built on a date somebody guessed is
not one the utility should be sending.
"""

from __future__ import annotations

import click

from kilodial.cli.context import Context, pass_context
from kilodial.cli.render import or_dash, pairs, table
from kilodial.tamper.event import Finding, TamperKind, tamper_kind


@click.group("tamper")
def tamper() -> None:
    """Seals, and what the shop does when one has been cut."""


@tamper.command("log")
@click.argument("reference")
@click.argument("point_code")
@click.argument("kind")
@click.option("--on", "day", required=True, help="the day it was found")
@click.option("--by", "finder", required=True, help="who found it")
@click.option("--evidence", default=None, help="what was seen")
@pass_context
def tamper_log(
    context: Context,
    reference: str,
    point_code: str,
    kind: str,
    day: str,
    finder: str,
    evidence: str | None,
) -> None:
    """Log a suspicion against a service point."""
    shop = context.open()
    finding = Finding.raise_finding(
        reference,
        point_code,
        tamper_kind(kind),
        found_on=day,
        found_by=finder,
        evidence=evidence,
    )
    with shop.transaction():
        shop.tamper.add(finding)
    context.say(f"{finding} logged, nothing moves until it is confirmed")


@tamper.command("confirm")
@click.argument("reference")
@click.option("--on", "day", required=True, help="the day it was confirmed")
@click.option("--since", required=True, help="the day the interference started")
@click.option("--evidence", required=True, help="what was seen")
@pass_context
def tamper_confirm(context: Context, reference: str, day: str, since: str, evidence: str) -> None:
    """Confirm a suspicion, which changes what the customer can be billed."""
    shop = context.open()
    with shop.transaction():
        confirmed = shop.tamper.save(
            shop.tamper.get(reference).confirmed(on=day, since=since, evidence=evidence)
        )
        context.log("confirmed", f"tamper {confirmed.reference}", f"since {since}")
    context.say(f"{confirmed.reference} confirmed over {confirmed.span()}")
    if confirmed.unmeters:
        context.say(
            "this stopped the meter measuring, so the usage has to be estimated "
            "rather than corrected from a registration"
        )


@tamper.command("clear")
@click.argument("reference")
@click.option("--on", "day", required=True)
@click.option("--why", required=True, help="clearing needs a reason")
@pass_context
def tamper_clear(context: Context, reference: str, day: str, why: str) -> None:
    """Close a suspicion without confirming it."""
    shop = context.open()
    with shop.transaction():
        cleared = shop.tamper.save(shop.tamper.get(reference).cleared(on=day, why=why))
        context.log("cleared", f"tamper {cleared.reference}", why)
    context.say(f"{cleared.reference} cleared")


@tamper.command("list")
@click.option("--all", "everything", is_flag=True, help="settled ones too")
@click.option("--point", "point_code", default=None)
@click.option("--from", "first", default=None)
@click.option("--to", "last", default=None)
@pass_context
def tamper_list(
    context: Context,
    everything: bool,
    point_code: str | None,
    first: str | None,
    last: str | None,
) -> None:
    """List tamper findings, open suspicions by default."""
    shop = context.open()
    if first is not None and last is not None:
        found = shop.tamper.between(first, last)
    elif first is not None or last is not None:
        raise click.BadParameter("a window needs both --from and --to")
    elif point_code is not None:
        found = shop.tamper.for_point(point_code)
    elif everything:
        found = shop.tamper.all()
    else:
        found = shop.tamper.open_ones()
    rows = [
        [
            f.reference,
            f.point_code,
            str(f.kind),
            str(f.standing),
            f.found_on.isoformat(),
            f.found_by,
            or_dash(None if f.since is None else f.since.isoformat()),
            "yes" if f.unmeters else "no",
        ]
        for f in found
    ]
    headings = ["finding", "point", "kind", "standing", "found", "by", "since", "unmetered"]
    for line in table(headings, rows):
        click.echo(line)


@tamper.command("show")
@click.argument("reference")
@pass_context
def tamper_show(context: Context, reference: str) -> None:
    """One finding and everything decided about it."""
    shop = context.open()
    finding = shop.tamper.get(reference)
    detail = [
        ("finding", finding.reference),
        ("point", finding.point_code),
        ("kind", str(finding.kind)),
        ("standing", str(finding.standing)),
        ("found on", finding.found_on.isoformat()),
        ("found by", finding.found_by),
        (
            "settled",
            or_dash(None if finding.settled_on is None else finding.settled_on.isoformat()),
        ),
        (
            "interference since",
            or_dash(None if finding.since is None else finding.since.isoformat()),
        ),
        ("stopped measuring", "yes" if finding.unmeters else "no"),
        ("evidence", or_dash(finding.evidence)),
    ]
    for line in pairs(detail):
        click.echo(line)


@tamper.command("kinds")
def tamper_kinds() -> None:
    """The findings the shop records, and which stop the meter measuring."""
    rows = [[k.label, "yes" if k.unmeters else "no"] for k in TamperKind]
    for line in table(["kind", "stops measuring"], rows):
        click.echo(line)


__all__ = ["tamper"]
