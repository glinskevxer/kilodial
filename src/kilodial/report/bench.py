"""Who benched what, and what came of it.

The shop supervisor's version of the question is "is the work getting done" and
the commission's version is "can you show me that the person who signed this was
allowed to". Both are answered off the same rows, so they are one report.

The column worth watching is void. A technician whose runs come back void is not
doing bad work; they are working on a bench whose standard has lapsed, or their
own certification has, and both of those are somebody else's job to fix. A
technician whose runs come back failed is finding bad meters, which is the job.
Putting the two columns side by side is the point of the report.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from kilodial.model.run import RunKind
from kilodial.report.document import Document, Grid
from kilodial.store.shop import Shop
from kilodial.testing.verdict import Outcome
from kilodial.units.span import DateSpan

HEADINGS = ["technician", "badge", "runs", "passed", "failed", "void", "suspect", "void rate"]
UNSIGNED = "unsigned"


@dataclass(frozen=True)
class Worker:
    """One technician's bench work over a window."""

    name: str
    badge: str
    outcomes: dict[Outcome, int]
    kinds: dict[RunKind, int]

    @property
    def runs(self) -> int:
        return sum(self.outcomes.values())

    @property
    def void_rate(self) -> Decimal:
        if self.runs == 0:
            return Decimal(0)
        return (Decimal(self.outcomes[Outcome.VOID]) / self.runs * 100).quantize(Decimal("0.1"))

    def row(self) -> list[str]:
        return [
            self.name,
            self.badge,
            str(self.runs),
            str(self.outcomes[Outcome.PASSED]),
            str(self.outcomes[Outcome.FAILED]),
            str(self.outcomes[Outcome.VOID]),
            str(self.outcomes[Outcome.SUSPECT]),
            str(self.void_rate),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.badge}) {self.runs} runs"


def workers(shop: Shop, window: DateSpan) -> list[Worker]:
    """Every technician who benched anything over a window, busiest first."""
    found: dict[tuple[str, str], Worker] = {}
    for run in shop.runs.between(window.start, window.end or window.start):
        badge = run.badge or UNSIGNED
        key = (run.technician, badge)
        if key not in found:
            found[key] = Worker(
                run.technician,
                badge,
                dict.fromkeys(Outcome, 0),
                dict.fromkeys(RunKind, 0),
            )
        try:
            verdict = shop.judge_run(run)
        except Exception:  # noqa: BLE001 - a run naming a missing record is a book fault
            continue
        found[key].outcomes[verdict.outcome] += 1
        found[key].kinds[run.kind] += 1
    return sorted(found.values(), key=lambda w: (-w.runs, w.name))


def grid(rows: list[Worker]) -> Grid:
    """A row per technician."""
    return Grid.of(HEADINGS, [w.row() for w in rows])


def kind_grid(rows: list[Worker]) -> Grid:
    """A row per run kind, totalled across everybody."""
    totals = dict.fromkeys(RunKind, 0)
    for worker in rows:
        for kind, count in worker.kinds.items():
            totals[kind] += count
    return Grid.of(["kind", "runs"], [[kind.value, str(totals[kind])] for kind in RunKind])


def build(shop: Shop, *, first: object, last: object) -> Document:
    """The whole bench report for a window."""
    window = DateSpan(first, last)
    rows = workers(shop, window)
    doc = Document(f"Bench report, {window}")

    section = doc.section("By technician", grid(rows))
    section.fact("technicians", len(rows))
    section.fact("runs", sum(w.runs for w in rows))
    section.fact("void", sum(w.outcomes[Outcome.VOID] for w in rows))
    unsigned = [w for w in rows if w.badge == UNSIGNED]
    section.fact("unsigned runs", sum(w.runs for w in unsigned))
    for worker in rows:
        if worker.void_rate > 0:
            section.note(
                f"{worker} at a {worker.void_rate} percent void rate, which is a "
                "bench or a certificate rather than the technician"
            )

    doc.section("By run kind", kind_grid(rows))
    return doc


__all__ = ["HEADINGS", "UNSIGNED", "Worker", "build", "grid", "kind_grid", "workers"]
