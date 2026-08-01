"""Report commands, built from the catalogue rather than written six times.

The six commands were six copies of the same eleven lines: the same format
option, the same output path option, and either an ``--on`` or a ``--from`` and
``--to`` pair depending on whether the report covers a period. Two of the copies
had already drifted, one carrying a ``--warning`` option the others did not and
one whose help said "as at" where the report was over a window.

So they are generated from the catalogue, which already had to list every report
and say which shape it takes. A report added to the catalogue with a builder
gets its command for nothing, and one added without either fails the catalogue's
own test.

The one report with an option of its own is handled by an extras table rather
than by an exception in the loop, so it is visible next to the others.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any, TypeVar

import click

from kilodial.cli.context import Context, pass_context
from kilodial.report import bench, catalogue, certifications, commission, faults, register
from kilodial.report import shop as shop_report
from kilodial.report.document import Document
from kilodial.report.layout import table

FORMATS = ("text", "json", "csv")

_F = TypeVar("_F", bound=Callable[..., Any])

# The function that builds each report, against the name the catalogue lists it
# under.
BUILDERS: dict[str, Callable[..., Document]] = {
    "shop": shop_report.build,
    "commission": commission.build,
    "register": register.build,
    "certificates": certifications.build,
    "faults": faults.build,
    "bench": bench.build,
}

# Options a single report takes and the others do not.
EXTRAS: dict[str, list[Callable[[_F], _F]]] = {
    "certificates": [
        click.option(
            "--warning",
            type=int,
            default=None,
            help="days ahead to warn on",
        )
    ],
}


def render(doc: Document, shape: str) -> str:
    """The report in the shape the caller asked for."""
    if shape == "json":
        return doc.as_json()
    if shape == "csv":
        return doc.as_csv()
    return doc.render()


def emit(context: Context, doc: Document, shape: str, out: Path | None) -> None:
    """Print the report, or write it out in one go."""
    text = render(doc, shape)
    if out is None:
        click.echo(text, nl=False)
        return
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text)
    context.say(f"wrote {out} ({len(text.splitlines())} lines)")


def format_option() -> Callable[[_F], _F]:
    """The shared format flag, so the reports cannot drift apart."""
    return click.option(
        "--format",
        "shape",
        type=click.Choice(FORMATS),
        default="text",
        show_default=True,
        help="the shape to write it in",
    )


def out_option() -> Callable[[_F], _F]:
    """The shared output path flag."""
    return click.option(
        "--out",
        type=click.Path(dir_okay=False, path_type=Path),
        default=None,
        help="write to a file rather than to standard output",
    )


@click.group("report")
def reports() -> None:
    """Reports the shop and the commission ask for."""


def _register(entry: catalogue.Entry) -> None:
    """Wire one catalogue entry up as a command."""
    build = BUILDERS[entry.name]

    @pass_context
    def command(context: Context, /, shape: str, out: Path | None, **rest: object) -> None:
        doc = build(context.open(), **{k: v for k, v in rest.items() if v is not None})
        emit(context, doc, shape, out)

    command.__doc__ = entry.question
    made = click.command(entry.name)(command)
    for extra in reversed(EXTRAS.get(entry.name, [])):
        made = extra(made)
    made = out_option()(made)
    made = format_option()(made)
    if entry.period:
        made = click.option("--to", "last", required=True, help="end of the reporting period")(made)
        made = click.option("--from", "first", required=True, help="start of the reporting period")(
            made
        )
    else:
        made = click.option("--on", "on", required=True, help="the day to report as at")(made)
    reports.add_command(made)


for _entry in catalogue.CATALOGUE:
    _register(_entry)


@reports.command("list")
def report_list() -> None:
    """Every report there is and what question it answers."""
    rows = [entry.row() for entry in catalogue.CATALOGUE]
    for line in table(["report", "takes", "answers"], rows):
        click.echo(line)
    over, at = catalogue.by_period()
    click.echo("")
    click.echo(f"{len(over)} take --from and --to, {len(at)} take --on")


@reports.command("formats")
def report_formats() -> None:
    """The shapes a report can be written in."""
    for shape in FORMATS:
        click.echo(shape)


__all__ = [
    "BUILDERS",
    "EXTRAS",
    "FORMATS",
    "emit",
    "format_option",
    "out_option",
    "render",
    "reports",
]
