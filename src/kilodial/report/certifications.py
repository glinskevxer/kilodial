"""Everything with a certificate on it, in one place and on one clock.

Three separate things in this shop expire and every one of them voids work when
it does: a reference standard's certificate, a technician's certification, and
an instrument transformer's last test. They are tracked in three different
tables by three different people, and the failure is always the same shape:
somebody notices in March that something lapsed in November and a season of runs
is in question.

So this report puts them on one page with one column that matters, which is days
left. The transformers are the odd ones out because a transformer test does not
expire on a date; it has an interval, and the interval is a shop policy rather
than a certificate. It is included anyway, because a transformer eight years
past its test is the same problem wearing different clothes.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass
from datetime import date

from kilodial.report.document import Document, Grid
from kilodial.store.shop import Shop
from kilodial.units.span import add_months, parse_date

# How often the shop tests its instrument transformers.
TRANSFORMER_INTERVAL_MONTHS = 96

WARNING_DAYS = 90


class Standing(enum.Enum):
    """Where a certificate sits against today."""

    CURRENT = "current"
    DUE = "due"
    LAPSED = "lapsed"

    @property
    def needs_work(self) -> bool:
        return self is not Standing.CURRENT

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class Line:
    """One certified thing and how long it has left."""

    kind: str
    reference: str
    detail: str
    expires: date
    days_left: int
    standing: Standing

    def row(self) -> list[str]:
        return [
            self.kind,
            self.reference,
            self.detail,
            self.expires.isoformat(),
            str(self.days_left),
            str(self.standing),
        ]

    def __str__(self) -> str:
        return f"{self.kind} {self.reference} {self.standing} ({self.days_left} days)"


HEADINGS = ["kind", "reference", "detail", "expires", "days left", "standing"]


def standing_of(days_left: int, *, warning: int = WARNING_DAYS) -> Standing:
    """Current, due or lapsed, from the days remaining."""
    if days_left < 0:
        return Standing.LAPSED
    return Standing.DUE if days_left <= warning else Standing.CURRENT


def lines_for(shop: Shop, on: object, *, warning: int = WARNING_DAYS) -> list[Line]:
    """Every certified thing on the book, soonest to expire first."""
    when = parse_date(on)
    found: list[Line] = []
    for standard in shop.standards.all():
        left = standard.days_left_on(when)
        found.append(
            Line(
                "standard",
                standard.serial,
                f"{standard.maker} {standard.model_code}, {standard.certificate}",
                standard.certificate_due,
                left,
                standing_of(left, warning=warning),
            )
        )
    for person in shop.technicians.all():
        left = person.days_left_on(when)
        found.append(
            Line(
                "technician",
                person.badge,
                f"{person.name}, {person.grade}",
                person.certificate_due,
                left,
                standing_of(left, warning=warning),
            )
        )
    for transformer in shop.transformers.all():
        due = add_months(transformer.tested_on, TRANSFORMER_INTERVAL_MONTHS)
        left = (due - when).days
        found.append(
            Line(
                "transformer",
                transformer.serial,
                f"{transformer.kind}, class {transformer.accuracy}",
                due,
                left,
                standing_of(left, warning=warning),
            )
        )
    return sorted(found, key=lambda line: (line.days_left, line.kind, line.reference))


def grid(lines: list[Line]) -> Grid:
    """The lines as a table."""
    return Grid.of(HEADINGS, [line.row() for line in lines])


def build(shop: Shop, *, on: object, warning: int = WARNING_DAYS) -> Document:
    """The whole certification report for a day."""
    when = parse_date(on)
    lines = lines_for(shop, when, warning=warning)
    doc = Document(f"Certification report as at {when.isoformat()}")
    section = doc.section("Certificates", grid(lines))
    section.fact("tracked", len(lines))
    for standing in Standing:
        section.fact(standing.value, sum(1 for line in lines if line.standing is standing))
    section.fact("warning window", f"{warning} days")
    lapsed = [line for line in lines if line.standing is Standing.LAPSED]
    for line in lapsed[:5]:
        section.note(f"{line} expired {line.expires.isoformat()}")
    doc.section("Transformer policy").fact(
        "test interval", f"{TRANSFORMER_INTERVAL_MONTHS} months"
    ).note(
        "a transformer test does not expire on a date, so its due day is worked "
        "out from the shop's own interval"
    )
    return doc


__all__ = [
    "HEADINGS",
    "TRANSFORMER_INTERVAL_MONTHS",
    "WARNING_DAYS",
    "Line",
    "Standing",
    "build",
    "grid",
    "lines_for",
    "standing_of",
]
