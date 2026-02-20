"""Report commands.

Every report takes the same three format options and there is no default beyond
text, because the person running it in a terminal wants to read it and the
script running it in a pipeline wants json. Writing to a file rather than to
standard output is a flag rather than a redirect, so that a report that fails
halfway does not leave a half written file somebody then emails.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any, TypeVar

import click

from kilodial.cli.context import Context, pass_context
from kilodial.report import bench, certifications, commission, faults, register
from kilodial.report import shop as shop_report
from kilodial.report.document import Document

FORMATS = ("text", "json", "csv")

_F = TypeVar("_F", bound=Callable[..., Any])


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
    """The shared format flag, so the three reports cannot drift apart."""
    return click.option(
        "--format",
        "shape",
        type=click.Choice(FORMATS),
        default="text",
        show_default=True,
    )


@click.group("report")
def reports() -> None:
    """Reports the shop and the commission ask for."""


@reports.command("shop")
@click.option("--on", "day", required=True, help="the day to report as at")
@format_option()
@click.option("--out", type=click.Path(dir_okay=False, path_type=Path), default=None)
@pass_context
def report_shop(context: Context, day: str, shape: str, out: Path | None) -> None:
    """What the shop looks like on a day."""
    emit(context, shop_report.build(context.open(), on=day), shape, out)


@reports.command("commission")
@click.option("--from", "first", required=True, help="start of the reporting period")
@click.option("--to", "last", required=True, help="end of the reporting period")
@format_option()
@click.option("--out", type=click.Path(dir_okay=False, path_type=Path), default=None)
@pass_context
def report_commission(
    context: Context, first: str, last: str, shape: str, out: Path | None
) -> None:
    """The annual filing for the commission."""
    doc = commission.build(context.open(), first=first, last=last)
    emit(context, doc, shape, out)


@reports.command("register")
@click.option("--on", "day", required=True, help="the day to price the register at")
@format_option()
@click.option("--out", type=click.Path(dir_okay=False, path_type=Path), default=None)
@pass_context
def report_register(context: Context, day: str, shape: str, out: Path | None) -> None:
    """Every point that owes money or is owed it."""
    emit(context, register.build(context.open(), on=day), shape, out)


@reports.command("bench")
@click.option("--from", "first", required=True, help="start of the window")
@click.option("--to", "last", required=True, help="end of the window")
@format_option()
@click.option("--out", type=click.Path(dir_okay=False, path_type=Path), default=None)
@pass_context
def report_bench(context: Context, first: str, last: str, shape: str, out: Path | None) -> None:
    """Who benched what, and what came of it."""
    emit(context, bench.build(context.open(), first=first, last=last), shape, out)


@reports.command("faults")
@click.option("--from", "first", required=True, help="start of the window")
@click.option("--to", "last", required=True, help="end of the window")
@format_option()
@click.option("--out", type=click.Path(dir_okay=False, path_type=Path), default=None)
@pass_context
def report_faults(context: Context, first: str, last: str, shape: str, out: Path | None) -> None:
    """What breaks, on which types, and what it costs to keep fixing."""
    emit(context, faults.build(context.open(), first=first, last=last), shape, out)


@reports.command("certificates")
@click.option("--on", "day", required=True, help="the day to report as at")
@click.option("--warning", type=int, default=None, help="days ahead to warn on")
@format_option()
@click.option("--out", type=click.Path(dir_okay=False, path_type=Path), default=None)
@pass_context
def report_certificates(
    context: Context, day: str, warning: int | None, shape: str, out: Path | None
) -> None:
    """Standards, technicians and transformers on one clock."""
    shop = context.open()
    doc = (
        certifications.build(shop, on=day)
        if warning is None
        else certifications.build(shop, on=day, warning=warning)
    )
    emit(context, doc, shape, out)


@reports.command("formats")
def report_formats() -> None:
    """The shapes a report can be written in."""
    for shape in FORMATS:
        click.echo(shape)


__all__ = ["FORMATS", "emit", "format_option", "render", "reports"]
