"""The due list, assembled from everything else on the book.

This is the report the shop plans a year around, and it is the place where the
circularity in the whole scheme shows up: a group's sample decides its interval,
the interval decides which meters are due, and which meters get tested decides
what next season's sample looks like. Nothing here breaks that circle, it just
evaluates it as it stands today.

Two decisions that are easy to get wrong and expensive to get wrong:

A meter belongs to the first group that takes it, in group code order. Meters
falling into two groups is a criteria problem for the group report to raise, not
something to be resolved silently here by picking the tighter interval, because
picking one quietly means nobody ever fixes the overlap.

A group can carry its own grace period and it wins over the roster's. The
roster's number is the shop's default; a group's is a decision about that
population, and a decision beats a default.

A meter in no group at all is still on the list. It goes on at the bottom
interval, which is the shortest, so an ungrouped meter is tested too often
rather than never. That is the right way round to be wrong.
"""

from __future__ import annotations

from dataclasses import dataclass

from kilodial.model.meter import Meter, MeterState
from kilodial.model.run import RunKind
from kilodial.programme.schedule import (
    GRACE_DAYS,
    RESTARTS_CLOCK,
    DueMeter,
    DueState,
    schedule_for,
)
from kilodial.sampling.plan import INTERVAL_LADDER
from kilodial.store.shop import Shop

UNGROUPED = "-"
OUT_OF_PROGRAMME = frozenset({MeterState.SCRAP, MeterState.LOST})


@dataclass(frozen=True)
class Roster:
    """Every meter in the programme, with where it sits today."""

    lines: tuple[DueMeter, ...]

    def due(self) -> list[DueMeter]:
        return [line for line in self.lines if line.state is DueState.DUE]

    def overdue(self) -> list[DueMeter]:
        return [line for line in self.lines if line.state is DueState.OVERDUE]

    def needing_work(self) -> list[DueMeter]:
        return [line for line in self.lines if line.state.needs_work]

    def for_group(self, code: str) -> list[DueMeter]:
        wanted = code.strip().upper()
        return [line for line in self.lines if line.group_code == wanted]

    def counts(self) -> dict[DueState, int]:
        found = dict.fromkeys(DueState, 0)
        for line in self.lines:
            found[line.state] += 1
        return found

    def ungrouped(self) -> list[DueMeter]:
        return [line for line in self.lines if line.group_code == UNGROUPED]

    def __len__(self) -> int:
        return len(self.lines)

    def __iter__(self) -> object:
        return iter(self.lines)


def clock_start(shop: Shop, serial: str) -> tuple[str, RunKind] | None:
    """The most recent usable run that restarts a meter's periodic clock."""
    for run in reversed(shop.runs.for_meter(serial)):
        if run.kind not in RESTARTS_CLOCK:
            continue
        try:
            verdict = shop.judge_run(run)
        except Exception:  # noqa: BLE001 - a run naming a missing record is not a crash
            continue
        if verdict.outcome.is_usable:
            return (run.tested_on.isoformat(), run.kind)
    return None


def group_of(shop: Shop, meter: Meter) -> str:
    """The group a meter falls into, or the ungrouped marker."""
    found = shop.groups.group_for(meter.serial)
    return found[0].code if found else UNGROUPED


def grace_for(shop: Shop, code: str, fallback: int) -> int:
    """The grace period a group runs on, or the programme's own.

    A group can name its own, and when it does it wins over the number passed
    into the roster. That is the right way round: the caller's number is the
    shop's default and the group's is a decision somebody made about that
    population.
    """
    if code == UNGROUPED:
        return fallback
    group = shop.groups.get(code)
    return fallback if group.grace_days is None else group.grace_days


def build(shop: Shop, *, on: object, grace_days: int = GRACE_DAYS) -> Roster:
    """Assemble the due list as it stands on a day."""
    lines: list[DueMeter] = []
    for meter in shop.meters.all():
        if meter.state in OUT_OF_PROGRAMME:
            continue
        code = group_of(shop, meter)
        months = INTERVAL_LADDER[0] if code == UNGROUPED else shop.plans.interval(code)
        lines.append(
            schedule_for(
                meter.serial,
                group_code=code,
                interval_months=months,
                acquired=meter.acquired,
                last_run=clock_start(shop, meter.serial),
                on=on,
                grace_days=grace_for(shop, code, grace_days),
            )
        )
    lines.sort(key=lambda line: (line.due, line.serial))
    return Roster(tuple(lines))


__all__ = [
    "OUT_OF_PROGRAMME",
    "UNGROUPED",
    "Roster",
    "build",
    "clock_start",
    "grace_for",
    "group_of",
]
