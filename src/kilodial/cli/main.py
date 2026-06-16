"""The command tree, and the one place a ShopError turns into an exit code.

Every command in this package raises. Nothing catches, nothing prints a warning
and carries on, and nothing returns a status code that a caller has to remember
to look at. The single handler here turns a ShopError into a one line message
and exit code 2, and lets anything else escape with its traceback, because an
error that is not a ShopError is a bug in this package rather than a mistake by
the person at the keyboard.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import click

from kilodial import __version__
from kilodial.cli.adjust import adjustments, bills
from kilodial.cli.benches import benches, standards
from kilodial.cli.complaints import complaints
from kilodial.cli.context import DEFAULT_BOOK, Context, pass_context
from kilodial.cli.devices import devices
from kilodial.cli.doctor import doctor
from kilodial.cli.estimate import estimates
from kilodial.cli.groups import due, groups
from kilodial.cli.ingest import imports
from kilodial.cli.installs import points
from kilodial.cli.meters import meters
from kilodial.cli.orders import orders
from kilodial.cli.readings import readings
from kilodial.cli.render import pairs, table
from kilodial.cli.repairs import repairs
from kilodial.cli.reports import reports
from kilodial.cli.runs import runs
from kilodial.cli.tamper import tamper
from kilodial.cli.technicians import technicians
from kilodial.cli.transformers import transformers
from kilodial.errors import ConfigError, ShopError
from kilodial.store import dump
from kilodial.store.events import DEFAULT_ACTOR
from kilodial.store.schema import latest_number

EXIT_SHOP_ERROR = 2


TRACEBACK = "KILODIAL_TRACEBACK"


class ShopGroup(click.Group):
    """The top level group, with the one error handler the package has.

    Putting it here rather than in the console script entry point means the
    exit code is the same whether the tool is run from a shell or driven
    straight through click's test runner, which is how it is mostly exercised.

    Setting KILODIAL_TRACEBACK lets the exception through instead, which is
    what somebody debugging wants and what nobody at a shop counter does.
    """

    def invoke(self, ctx: click.Context) -> object:
        try:
            return super().invoke(ctx)
        except ShopError as exc:
            if os.environ.get(TRACEBACK):
                raise
            click.echo(str(exc), err=True)
            raise SystemExit(EXIT_SHOP_ERROR) from exc


@click.group(cls=ShopGroup, context_settings={"help_option_names": ["-h", "--help"]})
@click.option(
    "--book",
    "book_path",
    default=DEFAULT_BOOK,
    show_default=True,
    envvar="KILODIAL_BOOK",
    type=click.Path(dir_okay=False, path_type=Path),
    help="the sqlite book to work on",
)
@click.option("--quiet", is_flag=True, help="say nothing that is not asked for")
@click.option(
    "--actor",
    default=None,
    envvar="KILODIAL_ACTOR",
    help="who is at the keyboard, for the event log",
)
@click.version_option(__version__, prog_name="kilodial")
@click.pass_context
def cli(ctx: click.Context, book_path: Path, quiet: bool, actor: str | None) -> None:
    """Meter shop register, accuracy testing and billing adjustment."""
    ctx.obj = Context(
        book_path=book_path,
        quiet=quiet,
        actor=DEFAULT_ACTOR if actor is None else actor,
    )
    ctx.call_on_close(ctx.obj.close)


@cli.command()
@click.option("--force", is_flag=True, help="migrate a book that is already there")
@pass_context
def init(context: Context, force: bool) -> None:
    """Create the book, or bring an existing one up to date."""
    existed = context.book_path.exists()
    shop = context.open(create=True, migrate=False)
    if existed and not force and not shop.book.pending():
        context.say(f"{context.book_path} is already at migration {shop.book.version}")
        return
    ran = shop.book.migrate()
    if ran:
        context.say(f"ran migration {ran[0]} through {ran[-1]} on {context.book_path}")
    else:
        context.say(f"{context.book_path} was already up to date")


@cli.command("about")
@pass_context
def about(context: Context) -> None:
    """What this is, what version, and where everything lives."""
    from kilodial.report.catalogue import CATALOGUE

    lines = [
        ("kilodial", __version__),
        ("book", str(context.book_path)),
        ("book exists", "yes" if context.book_path.exists() else "no"),
        ("actor", context.actor),
        ("commands", str(len(cli.commands))),
        ("reports", str(len(CATALOGUE))),
        ("migrations", str(latest_number())),
        ("command reference", "docs/commands.md"),
        ("schema", "docs/schema.sql"),
        ("glossary", "docs/glossary.md"),
        ("layers", "docs/layers.md"),
    ]
    for line in pairs(lines):
        click.echo(line)


@cli.group()
def book() -> None:
    """Look after the book itself."""


@book.command("check")
@pass_context
def book_check(context: Context) -> None:
    """Report anything structurally wrong with the book."""
    shop = context.open()
    faults = shop.book.check()
    if not faults:
        context.say(f"{context.book_path} is at migration {shop.book.version} and checks out")
        return
    for fault in faults:
        click.echo(fault)
    raise SystemExit(1)


@book.command("audit")
@pass_context
def book_audit(context: Context) -> None:
    """Report every record that points at something that is not there."""
    shop = context.open()
    faults = shop.audit()
    if not faults:
        context.say("nothing on the book points at anything missing")
        return
    for fault in faults:
        click.echo(fault)
    raise SystemExit(1)


@book.command("size")
@pass_context
def book_size(context: Context) -> None:
    """How big the book is and how much of it is free space."""
    shop = context.open()
    for name, value in shop.book.size().items():
        click.echo(f"{name:<12}{value:>12}")


@book.command("compact")
@click.confirmation_option(prompt="rewrite the book without its free pages?")
@pass_context
def book_compact(context: Context) -> None:
    """Rewrite the book without its free pages."""
    shop = context.open()
    found = shop.book.compact()
    context.say(f"{found['before']} bytes to {found['after']}, saved {found['saved']}")


@book.command("export")
@click.option(
    "--out",
    type=click.Path(dir_okay=False, path_type=Path),
    default=None,
    help="write to a file rather than to standard output",
)
@pass_context
def book_export(context: Context, out: Path | None) -> None:
    """Write the whole book out as json."""
    shop = context.open()
    text = dump.to_json(shop.book)
    if out is None:
        click.echo(text, nl=False)
        return
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text)
    rows = sum(dump.counts(dump.dump(shop.book)).values())
    context.say(f"wrote {out}, {rows} rows at migration {shop.book.version}")


@book.command("restore")
@click.argument("path", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.confirmation_option(prompt="load a dump into this book?")
@pass_context
def book_restore(context: Context, path: Path) -> None:
    """Load a json dump into an empty book."""
    shop = context.open(create=True)
    try:
        payload = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise ConfigError(f"{path} is not json: {exc}") from exc
    loaded = dump.restore(shop.book, payload)
    rows = sum(loaded.values())
    context.say(f"restored {rows} rows into {context.book_path}")
    for name, count in sorted(loaded.items()):
        if count:
            context.say(f"  {name} {count}")


@book.command("history")
@click.option("--subject", default=None, help="only lines about this subject")
@click.option("--action", default=None, help="only lines with this action")
@click.option("--by", "actor", default=None, help="only lines by this actor")
@click.option("--on", "day", default=None, help="only lines from this day")
@click.option("--last", type=int, default=None, help="only the last so many lines")
@pass_context
def book_history(
    context: Context,
    subject: str | None,
    action: str | None,
    actor: str | None,
    day: str | None,
    last: int | None,
) -> None:
    """What has been done to the book, oldest first."""
    shop = context.open()
    if subject is not None:
        found = shop.events.about(subject)
    elif action is not None:
        found = shop.events.by_action(action)
    elif actor is not None:
        found = shop.events.by_actor(actor)
    elif day is not None:
        found = shop.events.on_day(day)
    else:
        found = shop.events.all(limit=last)
    rows = [[str(e.sequence), e.at, e.actor, e.action, e.subject, e.detail or "-"] for e in found]
    for line in table(["seq", "at", "actor", "action", "subject", "detail"], rows):
        click.echo(line)
    gaps = shop.events.gaps()
    if gaps:
        click.echo(f"the log is missing {len(gaps)} lines: {gaps[:10]}")
        raise SystemExit(1)


@book.command("summary")
@pass_context
def book_summary(context: Context) -> None:
    """Count what is on the book."""
    shop = context.open()
    for name, count in shop.summary().items():
        click.echo(f"{name:<14}{count:>7}")


cli.add_command(devices)
cli.add_command(meters)
cli.add_command(standards)
cli.add_command(benches)
cli.add_command(runs)
cli.add_command(transformers)
cli.add_command(points)
cli.add_command(groups)
cli.add_command(due)
cli.add_command(bills)
cli.add_command(adjustments)
cli.add_command(complaints)
cli.add_command(orders)
cli.add_command(imports)
cli.add_command(reports)
cli.add_command(technicians)
cli.add_command(doctor)
cli.add_command(tamper)
cli.add_command(estimates)
cli.add_command(repairs)
cli.add_command(readings)


def run() -> None:
    """The console script entry point."""
    sys.exit(cli.main(standalone_mode=True))


if __name__ == "__main__":  # pragma: no cover
    run()


__all__ = ["EXIT_SHOP_ERROR", "TRACEBACK", "ShopGroup", "book", "cli", "run"]
