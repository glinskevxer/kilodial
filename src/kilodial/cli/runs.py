"""Bench run commands: record a run, judge it, look it up.

Recording takes percentages and nothing else. The bench code decides which
standard the run is recorded against unless one is named, which is right almost
all the time and wrong exactly when a standard has just been swapped and the
technician is entering yesterday's sheet. Hence the override.

Judging is a separate command from recording on purpose. A run is a
measurement and a verdict is an opinion about it, and the opinion can change
when a certificate turns out to have lapsed or a form gets corrected. Storing
the verdict would freeze an opinion that ought to be recomputed.
"""

from __future__ import annotations

import click

from kilodial.cli.context import Context, pass_context
from kilodial.cli.render import or_dash, pairs, table
from kilodial.errors import BadInputError
from kilodial.model.run import BenchRun, RunKind
from kilodial.testing.record import Readings, build_run
from kilodial.testing.verdict import Verdict

KINDS = {k.value.replace(" ", "_"): k for k in RunKind}
CREEP_WORDS = {"held": False, "crept": True}


def run_kind(text: str) -> RunKind:
    """Read a run kind, tolerating the hyphen and the space people type."""
    key = text.strip().lower().replace("-", "_").replace(" ", "_")
    if key not in KINDS:
        raise BadInputError(f"{text!r} is not one of {', '.join(sorted(KINDS))}")
    return KINDS[key]


def creep_word(text: str | None) -> bool | None:
    """Read the creep result, which is written held or crept and nothing else."""
    if text is None:
        return None
    key = text.strip().lower()
    if key not in CREEP_WORDS:
        raise BadInputError(f"creep is either held or crept, not {text!r}")
    return CREEP_WORDS[key]


@click.group("run")
def runs() -> None:
    """Bench runs."""


@runs.command("record")
@click.argument("reference")
@click.option("--meter", "meter_serial", required=True)
@click.option("--bench", "bench_code", required=True)
@click.option("--standard", "standard_serial", default=None, help="override the bench standard")
@click.option("--kind", default="as_found", show_default=True)
@click.option("--on", "tested_on", required=True, help="the day it was run")
@click.option("--by", "technician", required=True)
@click.option("--badge", default=None, help="the signing technician's badge")
@click.option("--fl", default=None, help="full load registration")
@click.option("--ll", default=None, help="light load registration")
@click.option("--pf", default=None, help="lagging power factor registration")
@click.option("--hl", default=None, help="heavy load registration")
@click.option("--register", default=None, help="register or dial test registration")
@click.option("--demand", default=None, help="demand registration")
@click.option("--creep", default=None, help="held or crept")
@click.option("--volts", default=None, help="service voltage if not the nameplate")
@click.option("--interval-seconds", default=None, help="measured demand window")
@click.option("--note", default=None)
@pass_context
def run_record(
    context: Context,
    reference: str,
    meter_serial: str,
    bench_code: str,
    standard_serial: str | None,
    kind: str,
    tested_on: str,
    technician: str,
    badge: str | None,
    fl: str | None,
    ll: str | None,
    pf: str | None,
    hl: str | None,
    register: str | None,
    demand: str | None,
    creep: str | None,
    volts: str | None,
    interval_seconds: str | None,
    note: str | None,
) -> None:
    """Write a bench run down."""
    shop = context.open()
    device = shop.device_for(meter_serial)
    bench = shop.benches.get(bench_code)
    standard = (
        shop.standards.get(standard_serial)
        if standard_serial is not None
        else shop.standards.get(bench.standard_serial)
    )
    run = build_run(
        reference,
        device=device,
        meter_serial=shop.meters.get(meter_serial).serial,
        bench_code=bench.code,
        standard_serial=standard.serial,
        kind=run_kind(kind),
        tested_on=tested_on,
        technician=technician,
        readings=Readings.of(
            full_load=fl,
            light_load=ll,
            power_factor=pf,
            heavy_load=hl,
            register=register,
            demand=demand,
            crept=creep_word(creep),
        ),
        note=note,
        volts=volts,
        demand_seconds=interval_seconds,
        badge=badge,
    )
    with shop.transaction():
        shop.runs.add(run)
        context.log("recorded", f"run {run.reference}", run.meter_serial)
    verdict = shop.judge_run(run)
    context.say(f"recorded {run.reference}, {verdict.outcome} at {_shown(verdict)}")


def _shown(verdict: Verdict) -> str:
    return "no reading" if verdict.registration is None else str(verdict.registration)


@runs.command("show")
@click.argument("reference")
@pass_context
def run_show(context: Context, reference: str) -> None:
    """One run, its points and the verdict it earns today."""
    shop = context.open()
    run = shop.runs.get(reference)
    verdict = shop.judge_run(run)
    for line in pairs(_header(run, verdict)):
        click.echo(line)
    click.echo("")
    rows = [
        [
            p.kind.code,
            str(p.amperes),
            str(p.volts),
            str(p.power_factor),
            "-" if p.registration is None else str(p.registration),
            "-" if p.crept is None else ("crept" if p.crept else "held"),
        ]
        for p in run.points
    ]
    for line in table(["point", "amps", "volts", "pf", "registration", "creep"], rows):
        click.echo(line)
    if verdict.average is not None:
        click.echo("")
        click.echo(verdict.average.show())
    if verdict.reasons:
        click.echo("")
        for reason in verdict.reasons:
            click.echo(reason)


def _header(run: BenchRun, verdict: Verdict) -> list[tuple[str, str]]:
    return [
        ("run", run.reference),
        ("meter", run.meter_serial),
        ("bench", run.bench_code),
        ("standard", run.standard_serial),
        ("kind", str(run.kind)),
        ("tested", run.tested_on.isoformat()),
        ("by", run.technician),
        ("badge", or_dash(run.badge)),
        ("note", or_dash(run.note)),
        ("outcome", str(verdict.outcome)),
        ("weighted", _shown(verdict)),
        ("band", f"+/-{verdict.band.weighted} percent"),
    ]


@runs.command("list")
@click.option("--meter", "meter_serial", default=None)
@click.option("--bench", "bench_code", default=None)
@click.option("--kind", default=None)
@click.option("--from", "first", default=None)
@click.option("--to", "last", default=None)
@pass_context
def run_list(
    context: Context,
    meter_serial: str | None,
    bench_code: str | None,
    kind: str | None,
    first: str | None,
    last: str | None,
) -> None:
    """List runs."""
    shop = context.open()
    if meter_serial is not None:
        found = shop.runs.for_meter(meter_serial)
    elif bench_code is not None:
        found = shop.runs.on_bench(bench_code)
    elif first is not None and last is not None:
        found = shop.runs.between(first, last)
    elif first is not None or last is not None:
        raise click.BadParameter("a window needs both --from and --to")
    else:
        found = shop.runs.all()
    if kind is not None:
        wanted = run_kind(kind)
        found = [r for r in found if r.kind is wanted]
    rows = []
    for run in found:
        verdict = shop.judge_run(run)
        rows.append(
            [
                run.reference,
                run.meter_serial,
                run.tested_on.isoformat(),
                str(run.kind),
                str(verdict.outcome),
                _shown(verdict),
            ]
        )
    for line in table(["run", "meter", "tested", "kind", "outcome", "weighted"], rows):
        click.echo(line)


@runs.command("demand")
@click.argument("reference")
@pass_context
def run_demand(context: Context, reference: str) -> None:
    """Judge the demand half of a run on its own."""
    shop = context.open()
    verdict = shop.judge_demand(reference)
    detail = [
        ("run", verdict.run_reference),
        ("outcome", str(verdict.outcome)),
        ("registration", "-" if verdict.registration is None else str(verdict.registration)),
        ("band", f"+/-{verdict.band} percent"),
        ("interval", or_dash(verdict.interval)),
        ("timing error", or_dash(None if verdict.timing is None else f"{verdict.timing} percent")),
    ]
    for line in pairs(detail):
        click.echo(line)
    for reason in verdict.reasons:
        click.echo(reason)
    if verdict.outcome.was_tested and not verdict.outcome.passed:
        raise SystemExit(1)


@runs.command("judge")
@click.argument("reference")
@pass_context
def run_judge(context: Context, reference: str) -> None:
    """Judge one run and say why."""
    shop = context.open()
    verdict = shop.judge(reference)
    click.echo(f"{verdict.run_reference} {verdict.outcome} at {_shown(verdict)}")
    click.echo(verdict.why())
    if not verdict.passed:
        raise SystemExit(1)


@runs.command("delete")
@click.argument("reference")
@click.confirmation_option(prompt="delete the run and its points?")
@pass_context
def run_delete(context: Context, reference: str) -> None:
    """Remove a run that should not have been entered."""
    shop = context.open()
    with shop.transaction():
        shop.runs.delete(reference)
        context.log("deleted", f"run {reference.upper()}")
    context.say(f"{reference.upper()} deleted")


__all__ = ["CREEP_WORDS", "KINDS", "creep_word", "run_kind", "runs"]
