"""Running a season's sample and recording what it decided.

A season is a window: the shop pulls a batch of meters out of a group over a few
months, benches them, and at the end asks what the group's registration looks
like. This module gathers those readings and turns them into a decision.

Which readings count is the fiddly part and it is worth being explicit:

Only as found runs. An as left run measures a meter the shop has just adjusted,
and averaging those in would tell you how good the shop's adjustments are rather
than how the group is drifting.

Only usable ones. A run against an expired standard has no reading, and a
suspect one has a reading that is not a meter error. Both are left out, and the
count of what was left out is reported, because a season that quietly dropped a
third of its runs is a season whose sample size was never met.

One reading per meter. A meter benched twice in a season contributes its latest
run and not two votes.
"""

from __future__ import annotations

from dataclasses import dataclass

from kilodial.errors import RuleError
from kilodial.model.run import RunKind
from kilodial.sampling.decision import Decision, decide
from kilodial.sampling.plan import SampleOutcome, assess
from kilodial.store.shop import Shop
from kilodial.units.registration import Registration
from kilodial.units.span import DateSpan


@dataclass(frozen=True)
class Season:
    """What a window of bench work turned up for one group."""

    group_code: str
    span: DateSpan
    population: int
    readings: tuple[Registration, ...]
    serials: tuple[str, ...]
    skipped: tuple[tuple[str, str], ...]

    @property
    def tested(self) -> int:
        return len(self.readings)

    def outcome(self) -> SampleOutcome:
        return assess(list(self.readings), population=self.population)

    def show(self) -> str:
        return (
            f"{self.group_code} over {self.span}: {self.tested} readings from a "
            f"population of {self.population}, {len(self.skipped)} runs left out"
        )

    def __str__(self) -> str:
        return self.show()


def gather(shop: Shop, group_code: str, span: DateSpan) -> Season:
    """Collect one usable as found reading per member meter over a window."""
    group = shop.groups.get(group_code)
    members = shop.groups.members(group.code)
    population = len(members)
    if population == 0:
        raise RuleError(f"group {group.code} has no meters in it")
    serials = {m.serial for m in members}
    readings: dict[str, Registration] = {}
    skipped: list[tuple[str, str]] = []
    for run in shop.runs.between(span.start, span.end or span.start):
        if run.meter_serial not in serials or run.kind is not RunKind.AS_FOUND:
            continue
        verdict = shop.judge_run(run)
        if verdict.registration is None or not verdict.outcome.is_usable:
            skipped.append((run.reference, str(verdict.outcome)))
            continue
        readings[run.meter_serial] = verdict.registration
    ordered = sorted(readings)
    return Season(
        group_code=group.code,
        span=span,
        population=population,
        readings=tuple(readings[s] for s in ordered),
        serials=tuple(ordered),
        skipped=tuple(skipped),
    )


def run_sample(
    shop: Shop,
    group_code: str,
    *,
    span: DateSpan,
    on: object,
    note: object = None,
) -> tuple[Season, Decision]:
    """Gather a season, judge it, and record the decision on the book."""
    season = gather(shop, group_code, span)
    decision = decide(
        season.group_code,
        season.outcome(),
        on=on,
        current_months=shop.plans.interval(season.group_code),
        note=note,
    )
    shop.plans.record(decision)
    return (season, decision)


__all__ = ["Season", "gather", "run_sample"]
