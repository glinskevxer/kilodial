"""The shop report: what the shop looks like on a given day.

This is the one the supervisor reads on a Monday. It is deliberately a snapshot
rather than a period report, because the questions it answers are all of the
form "what is true now": how many meters are in each state, how many runs came
back unusable, which standards are about to run out of certificate, what is
overdue.

The unusable count is the number worth watching. A shop whose void and suspect
runs are climbing has a bench problem or a standard problem, and both of them
turn into a season's work being thrown away if they are not caught.
"""

from __future__ import annotations

from kilodial.model.meter import MeterState
from kilodial.model.run import RunKind
from kilodial.orders.order import OrderState
from kilodial.programme import roster
from kilodial.programme.schedule import DueState
from kilodial.report.document import Document, Grid
from kilodial.store.shop import Shop
from kilodial.testing.verdict import Outcome
from kilodial.units.span import parse_date

CERTIFICATE_WARNING_DAYS = 90


def fleet_grid(shop: Shop) -> Grid:
    """A row per meter state, with the count in it."""
    counts = shop.meters.counts_by_state()
    return Grid.of(
        ["state", "meters"],
        [[state.value, str(counts[state])] for state in MeterState],
    )


def run_grid(shop: Shop) -> Grid:
    """A row per run kind, with what each kind's verdicts came to."""
    tallies: dict[RunKind, dict[Outcome, int]] = {
        kind: dict.fromkeys(Outcome, 0) for kind in RunKind
    }
    for run in shop.runs.all():
        try:
            verdict = shop.judge_run(run)
        except Exception:  # noqa: BLE001 - a run naming a missing record is a book fault
            continue
        tallies[run.kind][verdict.outcome] += 1
    return Grid.of(
        ["kind", "passed", "failed", "void", "suspect"],
        [
            [
                kind.value,
                str(tallies[kind][Outcome.PASSED]),
                str(tallies[kind][Outcome.FAILED]),
                str(tallies[kind][Outcome.VOID]),
                str(tallies[kind][Outcome.SUSPECT]),
            ]
            for kind in RunKind
        ],
    )


def standards_grid(shop: Shop, on: object) -> Grid:
    """Standards and how much certificate they have left."""
    when = parse_date(on)
    rows = []
    for standard in shop.standards.all():
        left = standard.days_left_on(when)
        rows.append(
            [
                standard.serial,
                standard.certificate,
                standard.certificate_due.isoformat(),
                str(left),
                "expired"
                if left < 0
                else ("due" if left <= CERTIFICATE_WARNING_DAYS else "current"),
            ]
        )
    return Grid.of(["standard", "certificate", "due", "days left", "state"], rows)


def build(shop: Shop, *, on: object) -> Document:
    """The whole shop report for a day."""
    when = parse_date(on)
    doc = Document(f"Meter shop report as at {when.isoformat()}")

    counts = shop.summary()
    overview = doc.section("Overview")
    for name, count in counts.items():
        overview.fact(name, count)

    doc.section("Fleet", fleet_grid(shop))

    runs = doc.section("Bench runs", run_grid(shop))
    unusable = shop.unusable_runs()
    runs.fact("unusable", len(unusable))
    for run, verdict in unusable[:5]:
        runs.note(f"{run.reference} {verdict.outcome}: {verdict.why()}")

    standards = doc.section("Reference standards", standards_grid(shop, when))
    expired = shop.standards.expired_on(when)
    standards.fact("expired", len(expired))

    built = roster.build(shop, on=when)
    programme = doc.section("Periodic programme")
    due_counts = built.counts()
    for due_state in DueState:
        programme.fact(due_state.value, due_counts[due_state])
    programme.fact("ungrouped", len(built.ungrouped()))

    orders = doc.section("Work orders")
    order_counts = shop.orders.counts_by_state()
    for order_state in OrderState:
        orders.fact(order_state.value, order_counts[order_state])
    orders.fact("late", len(shop.orders.late_on(when)))

    complaints = doc.section("Customer requests")
    complaints.fact("open", len(shop.complaints.open_ones()))
    complaints.fact("past their deadline", len(shop.complaints.overdue(when)))

    faults = shop.audit()
    book = doc.section("Book")
    book.fact("faults", len(faults))
    for fault in faults[:5]:
        book.note(fault)
    return doc


__all__ = [
    "CERTIFICATE_WARNING_DAYS",
    "build",
    "fleet_grid",
    "run_grid",
    "standards_grid",
]
