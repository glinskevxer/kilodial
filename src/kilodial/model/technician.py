"""Technicians, and what they are certified to sign.

A bench result is a legal statement about a customer's meter, and in this
jurisdiction it is only a statement if the person who made it was certified to
make it on the day they made it. That is not paperwork for its own sake: a
technician's certification lapses, and a shop that keeps running runs against a
lapsed one has a season of results it cannot defend.

Certification has grades and they are not interchangeable. A bench technician
signs single phase work. A polyphase technician signs everything a bench
technician does and polyphase besides. A supervisor signs anything, including
the referee runs a customer complaint turns on, which the other two may not,
because a referee run is the utility's answer to a complaint about itself.

So the question this module answers is not "is this person certified" but "was
this person certified for this run on this day", and both halves of that matter.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass
from datetime import date

from kilodial.errors import BadInputError, RuleError
from kilodial.model.device import DeviceType
from kilodial.model.run import RunKind
from kilodial.units.span import DateSpan, parse_date
from kilodial.units.text import key, optional, tidy


class Grade(enum.Enum):
    """What a certification lets somebody sign, in ascending order."""

    BENCH = ("bench", 1)
    POLYPHASE = ("polyphase", 2)
    SUPERVISOR = ("supervisor", 3)

    def __init__(self, label: str, rank: int) -> None:
        self.label = label
        self.rank = rank

    @property
    def signs_polyphase(self) -> bool:
        return self.rank >= Grade.POLYPHASE.rank

    @property
    def signs_referee(self) -> bool:
        """Only a supervisor answers a customer complaint."""
        return self is Grade.SUPERVISOR

    def __str__(self) -> str:
        return self.label


def grade_named(value: object) -> Grade:
    """Read a certification grade by name."""
    if isinstance(value, Grade):
        return value
    wanted = str(value).strip().lower()
    for member in Grade:
        if member.label == wanted:
            return member
    raise BadInputError(f"{value!r} is not a certification grade")


@dataclass(frozen=True)
class Technician:
    """One person, and the window their certification covers."""

    badge: str
    name: str
    grade: Grade
    certified_on: date
    certificate_due: date
    note: str | None

    @classmethod
    def build(
        cls,
        badge: object,
        name: object,
        *,
        grade: object,
        certified_on: object,
        certificate_due: object,
        note: object = None,
    ) -> Technician:
        """Certify somebody, refusing a window that is not one."""
        first = parse_date(certified_on)
        last = parse_date(certificate_due)
        if last <= first:
            raise RuleError("a certification has to run out after it was issued")
        return cls(
            badge=key(badge, "badge number", 12),
            name=tidy(name, "technician name", 40),
            grade=grade_named(grade),
            certified_on=first,
            certificate_due=last,
            note=optional(note, "certification note", 240),
        )

    @property
    def window(self) -> DateSpan:
        return DateSpan(self.certified_on, self.certificate_due)

    def is_certified_on(self, day: object) -> bool:
        return self.window.contains(day)

    def days_left_on(self, day: object) -> int:
        """Days of certification remaining, negative once it has lapsed."""
        return (self.certificate_due - parse_date(day)).days

    def may_sign(self, kind: RunKind, device: DeviceType, *, on: object) -> bool:
        """Whether this person could sign that run on that day."""
        return not self.refusals(kind, device, on=on)

    def refusals(self, kind: RunKind, device: DeviceType, *, on: object) -> list[str]:
        """Every reason this person could not sign that run, in words."""
        when = parse_date(on)
        found: list[str] = []
        if not self.is_certified_on(when):
            found.append(
                f"{self.badge} was not certified on {when.isoformat()}, "
                f"the certification runs {self.window}"
            )
        if device.form.is_polyphase and not self.grade.signs_polyphase:
            found.append(f"{self.badge} is certified {self.grade} and {device.key} is polyphase")
        if kind is RunKind.REFEREE and not self.grade.signs_referee:
            found.append(
                f"{self.badge} is certified {self.grade} and a referee run "
                "is signed by a supervisor"
            )
        return found

    def __str__(self) -> str:
        return f"{self.badge} {self.name} ({self.grade}, to {self.certificate_due.isoformat()})"


__all__ = ["Grade", "Technician", "grade_named"]
