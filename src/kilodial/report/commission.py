"""The annual filing: what the utility has to tell the commission it did.

The commission does not care how the shop is organised. It asks four questions
every year and it asks them in the same order:

How many meters are in service, broken down into the groups you test them as.

How many of each group you tested, and whether that met the sample your own plan
called for. A group tested short is the finding, and it is a finding whether the
result was good or not, because a sample that was not taken proves nothing.

What the tests found: how many were inside tolerance, how many outside, and
which way the ones outside were wrong.

How many customers asked for a test, how long you took, and how many of those
meters turned out to be bad.

Everything here is derived from the book at the moment it is asked for. There is
no stored copy of last year's filing, deliberately: if a run gets corrected in
March, last year's numbers change, and a shop that files the old ones because
they were saved has filed something it knows to be wrong.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from kilodial.complaint.request import Charge
from kilodial.model.meter import MeterState
from kilodial.model.run import RunKind
from kilodial.report.document import Document, Grid
from kilodial.sampling.plan import DEFAULT_BAND, required
from kilodial.store.shop import Shop
from kilodial.units.span import DateSpan

IN_SERVICE = frozenset({MeterState.SET})


@dataclass(frozen=True)
class GroupYear:
    """One group's year, as the filing states it."""

    code: str
    name: str
    population: int
    sample_needed: int
    tested: int
    inside: int
    fast: int
    slow: int
    interval_months: int

    @property
    def met_the_sample(self) -> bool:
        return self.tested >= self.sample_needed

    @property
    def share_tested(self) -> Decimal:
        if self.population == 0:
            return Decimal(0)
        return (Decimal(self.tested) / self.population * 100).quantize(Decimal("0.01"))

    def row(self) -> list[str]:
        return [
            self.code,
            self.name,
            str(self.population),
            str(self.sample_needed),
            str(self.tested),
            f"{self.share_tested}",
            str(self.inside),
            str(self.fast),
            str(self.slow),
            str(self.interval_months),
            "yes" if self.met_the_sample else "no",
        ]


HEADINGS = [
    "group",
    "name",
    "in service",
    "sample needed",
    "tested",
    "percent tested",
    "inside",
    "fast",
    "slow",
    "interval",
    "sample met",
]


def group_year(shop: Shop, code: str, window: DateSpan) -> GroupYear:
    """One group's figures over a window."""
    group = shop.groups.get(code)
    members = shop.groups.members(group.code)
    serials = {m.serial for m in members}
    inside = fast = slow = 0
    tested: set[str] = set()
    for run in shop.runs.between(window.start, window.end or window.start):
        if run.meter_serial not in serials or run.kind is not RunKind.AS_FOUND:
            continue
        verdict = shop.judge_run(run)
        if verdict.registration is None or not verdict.outcome.is_usable:
            continue
        tested.add(run.meter_serial)
        if verdict.registration.within(DEFAULT_BAND):
            inside += 1
        elif verdict.registration.is_fast:
            fast += 1
        else:
            slow += 1
    return GroupYear(
        code=group.code,
        name=group.name,
        population=len(members),
        sample_needed=required(len(members)),
        tested=len(tested),
        inside=inside,
        fast=fast,
        slow=slow,
        interval_months=shop.plans.interval(group.code),
    )


def group_grid(shop: Shop, window: DateSpan) -> Grid:
    """A row per group, in group code order."""
    rows = [group_year(shop, g.code, window).row() for g in shop.groups.all()]
    return Grid.of(HEADINGS, rows)


def build(shop: Shop, *, first: object, last: object) -> Document:
    """The whole filing for a period."""
    window = DateSpan(first, last)
    doc = Document(f"Commission meter test report, {window}")

    years = [group_year(shop, g.code, window) for g in shop.groups.all()]
    section = doc.section("Groups", group_grid(shop, window))
    section.fact("groups", len(years))
    section.fact("meters in groups", sum(y.population for y in years))
    section.fact("meters tested", sum(y.tested for y in years))
    section.fact("outside tolerance", sum(y.fast + y.slow for y in years))
    short = [y for y in years if not y.met_the_sample]
    section.fact("groups short of their sample", len(short))
    for year in short:
        section.note(f"{year.code} tested {year.tested} of a required {year.sample_needed}")

    ungrouped = [
        m
        for m in shop.meters.all()
        if m.state not in (MeterState.SCRAP, MeterState.LOST)
        and not shop.groups.group_for(m.serial)
    ]
    doc.section("Outside every group").fact("meters", len(ungrouped))

    requests = doc.section("Customer requested tests")
    answered = [
        c
        for c in shop.complaints.all()
        if c.closed_on is not None and window.contains(c.request.requested_on)
    ]
    opened = [c for c in shop.complaints.all() if window.contains(c.request.requested_on)]
    requests.fact("requested", len(opened))
    requests.fact("answered", len(answered))
    requests.fact(
        "meters found outside tolerance",
        sum(1 for c in answered if c.charge is Charge.WAIVED_ACCURACY),
    )
    requests.fact(
        "answered past the deadline",
        sum(1 for c in answered if c.charge is Charge.WAIVED_LATE),
    )
    late = [c for c in shop.complaints.open_ones() if window.contains(c.request.due_by)]
    requests.fact("still open from the period", len(late))
    return doc


__all__ = ["HEADINGS", "IN_SERVICE", "GroupYear", "build", "group_grid", "group_year"]
