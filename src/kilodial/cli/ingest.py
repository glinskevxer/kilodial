"""Import commands.

Both imports print the rows they could not take, with the line number, and exit
non zero when there were any. A silent partial import is the thing that has
somebody reconciling totals a week later with no idea which forty rows went
missing, and an exit code is the only part of that a shell script can see.
"""

from __future__ import annotations

from pathlib import Path

import click

from kilodial.cli.context import Context, pass_context
from kilodial.cli.render import table
from kilodial.ingest import bench as bench_import
from kilodial.ingest import billing as billing_import
from kilodial.ingest.sheet import Outcome, read_file


@click.group("import")
def imports() -> None:
    """Load files other systems produced."""


@imports.command("runs")
@click.argument("path", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--dry-run", is_flag=True, help="read and check without writing")
@pass_context
def import_runs(context: Context, path: Path, dry_run: bool) -> None:
    """Load a bench export into runs."""
    shop = context.open()
    if dry_run:
        sheet = read_file(path, required=bench_import.REQUIRED)
        skipped = []
        for row in sheet:
            try:
                bench_import.run_from(shop, row)
            except Exception as exc:  # noqa: BLE001 - a dry run reports, it does not raise
                skipped.append((row.line, str(exc)))
        _report(Outcome(len(sheet) - len(skipped), tuple(skipped)), dry=True)
        if skipped:
            raise SystemExit(1)
        return
    with shop.transaction():
        found = bench_import.load_file(shop, path)
    _report(found, dry=False)
    if not found.clean:
        raise SystemExit(1)


@imports.command("bills")
@click.argument("path", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@pass_context
def import_bills(context: Context, path: Path) -> None:
    """Load a billing extract into the billed history."""
    shop = context.open()
    with shop.transaction():
        found = billing_import.load_file(shop, path)
    _report(found, dry=False)
    if not found.clean:
        raise SystemExit(1)


def _report(outcome: Outcome, *, dry: bool) -> None:
    if outcome.skipped:
        rows = [[str(line), why] for line, why in outcome.skipped]
        for printed in table(["line", "why"], rows):
            click.echo(printed)
    tail = " (nothing written)" if dry else ""
    click.echo(outcome.show() + tail)


@imports.command("columns")
def import_columns() -> None:
    """The columns each import needs."""
    rows = [
        ["runs", ", ".join(bench_import.REQUIRED)],
        ["bills", ", ".join(billing_import.REQUIRED)],
    ]
    for line in table(["import", "required columns"], rows):
        click.echo(line)
    click.echo("")
    click.echo("runs also reads: standard, fl, ll, pf, hl, register, demand, creep, note, volts")
    click.echo("bills also reads: kwh")


__all__ = ["imports"]
