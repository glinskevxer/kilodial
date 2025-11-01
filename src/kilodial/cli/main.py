"""The command tree, and the one place a ShopError turns into an exit code.

Every command in this package raises. Nothing catches, nothing prints a warning
and carries on, and nothing returns a status code that a caller has to remember
to look at. The single handler here turns a ShopError into a one line message
and exit code 2, and lets anything else escape with its traceback, because an
error that is not a ShopError is a bug in this package rather than a mistake by
the person at the keyboard.
"""

from __future__ import annotations

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
from kilodial.cli.groups import due, groups
from kilodial.cli.ingest import imports
from kilodial.cli.installs import points
from kilodial.cli.meters import meters
from kilodial.cli.orders import orders
from kilodial.cli.reports import reports
from kilodial.cli.runs import runs
from kilodial.cli.technicians import technicians
from kilodial.cli.transformers import transformers
from kilodial.errors import ShopError

EXIT_SHOP_ERROR = 2


class ShopGroup(click.Group):
    """The top level group, with the one error handler the package has.

    Putting it here rather than in the console script entry point means the
    exit code is the same whether the tool is run from a shell or driven
    straight through click's test runner, which is how it is mostly exercised.
    """

    def invoke(self, ctx: click.Context) -> object:
        try:
            return super().invoke(ctx)
        except ShopError as exc:
            click.echo(str(exc), err=True)
            raise SystemExit(EXIT_SHOP_ERROR) from exc


@click.group(cls=ShopGroup, context_settings={"help_option_names": ["-h", "--help"]})
@click.option(
    "--book",
    "book_path",
    default=DEFAULT_BOOK,
    show_default=True,
    type=click.Path(dir_okay=False, path_type=Path),
    help="the sqlite book to work on",
)
@click.option("--quiet", is_flag=True, help="say nothing that is not asked for")
@click.version_option(__version__, prog_name="kilodial")
@click.pass_context
def cli(ctx: click.Context, book_path: Path, quiet: bool) -> None:
    """Meter shop register, accuracy testing and billing adjustment."""
    ctx.obj = Context(book_path=book_path, quiet=quiet)
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


def run() -> None:
    """The console script entry point."""
    sys.exit(cli.main(standalone_mode=True))


if __name__ == "__main__":  # pragma: no cover
    run()


__all__ = ["EXIT_SHOP_ERROR", "ShopGroup", "book", "cli", "run"]
