"""Tamper findings, from a cut seal to a confirmed bypass.

A meter that has been interfered with is a different problem from a meter that
has drifted, and the tariff treats it differently in one specific way: the
lookback on a back bill is much longer. The ordinary twelve months exists
because the customer had no way of knowing the meter was slow. A customer who
ran a jumper around it knew.

So a finding here has a state and the state is what matters. A seal found cut is
suspected: seals get cut by tree crews and by the utility's own people, and
back billing three years on a suspicion is indefensible. A finding is confirmed
when somebody has looked and written down what they saw, and only a confirmed
finding moves the lookback.

Cleared is a real outcome and it is kept rather than deleted. A point with three
cleared findings and a fourth suspicion is a different conversation from a point
with one suspicion, and deleting the cleared ones loses that.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, replace
from datetime import date

from kilodial.errors import BadInputError, RuleError, StateError
from kilodial.units.span import DateSpan, parse_date
from kilodial.units.text import key, optional, tidy


class TamperKind(enum.Enum):
    """What was found, and whether it stops the meter measuring."""

    SEAL_CUT = ("seal cut", False)
    SEAL_MISSING = ("seal missing", False)
    BYPASS = ("bypass", True)
    REVERSED = ("reversed", True)
    DIALS_TURNED = ("dials turned", True)
    METER_MISSING = ("meter missing", True)

    def __init__(self, label: str, unmeters: bool) -> None:
        self.label = label
        self.unmeters = unmeters

    def __str__(self) -> str:
        return self.label


class Standing(enum.Enum):
    """Where a finding has got to."""

    SUSPECTED = "suspected"
    CONFIRMED = "confirmed"
    CLEARED = "cleared"

    @property
    def is_open(self) -> bool:
        return self is Standing.SUSPECTED

    @property
    def moves_money(self) -> bool:
        """Only a confirmed finding changes what the customer can be billed."""
        return self is Standing.CONFIRMED

    def __str__(self) -> str:
        return self.value


def tamper_kind(value: object) -> TamperKind:
    """Read a tamper kind by its label or its name."""
    if isinstance(value, TamperKind):
        return value
    wanted = str(value).strip().lower().replace("_", " ")
    for member in TamperKind:
        if member.label == wanted or member.name.lower().replace("_", " ") == wanted:
            return member
    raise BadInputError(f"{value!r} is not a tamper finding")


@dataclass(frozen=True)
class Finding:
    """One tamper finding at one service point."""

    reference: str
    point_code: str
    kind: TamperKind
    standing: Standing
    found_on: date
    found_by: str
    settled_on: date | None
    since: date | None
    evidence: str | None

    @classmethod
    def raise_finding(
        cls,
        reference: object,
        point_code: object,
        kind: object,
        *,
        found_on: object,
        found_by: object,
        evidence: object = None,
    ) -> Finding:
        """Log a suspicion. Nothing is confirmed at this point."""
        return cls(
            reference=key(reference, "finding reference", 24),
            point_code=key(point_code, "service point code", 16),
            kind=tamper_kind(kind),
            standing=Standing.SUSPECTED,
            found_on=parse_date(found_on),
            found_by=tidy(found_by, "finder", 40),
            settled_on=None,
            since=None,
            evidence=optional(evidence, "evidence note", 240),
        )

    @property
    def is_open(self) -> bool:
        return self.standing.is_open

    @property
    def unmeters(self) -> bool:
        """Whether what was found stops the meter measuring what passed."""
        return self.kind.unmeters

    def confirmed(self, *, on: object, since: object, evidence: object) -> Finding:
        """Confirm a suspicion, which needs a date it started and something written down.

        ``since`` is the day the interference is judged to have begun. It is the
        one number a back bill hangs on, so it is required rather than inferred,
        and it cannot be later than the day the finding was made.
        """
        if not self.is_open:
            raise StateError(f"finding {self.reference} is already {self.standing}")
        settled = parse_date(on)
        started = parse_date(since)
        if started > self.found_on:
            raise RuleError("interference cannot have started after it was found")
        if settled < self.found_on:
            raise RuleError("a finding cannot be settled before it was made")
        written = optional(evidence, "evidence note", 240)
        if written is None:
            raise RuleError("confirming a tamper finding needs the evidence written down")
        return replace(
            self,
            standing=Standing.CONFIRMED,
            settled_on=settled,
            since=started,
            evidence=written,
        )

    def cleared(self, *, on: object, why: object) -> Finding:
        """Close a suspicion without confirming it, which needs a reason."""
        if not self.is_open:
            raise StateError(f"finding {self.reference} is already {self.standing}")
        reason = optional(why, "clearing note", 240)
        if reason is None:
            raise RuleError("clearing a tamper finding needs a reason")
        settled = parse_date(on)
        if settled < self.found_on:
            raise RuleError("a finding cannot be settled before it was made")
        return replace(
            self,
            standing=Standing.CLEARED,
            settled_on=settled,
            evidence=reason if self.evidence is None else f"{self.evidence}; {reason}",
        )

    def span(self) -> DateSpan:
        """The period the interference is judged to have covered."""
        if self.since is None:
            raise RuleError(f"finding {self.reference} is {self.standing} and has no period")
        return DateSpan(self.since, self.found_on)

    def __str__(self) -> str:
        return f"{self.reference} {self.point_code} {self.kind} ({self.standing})"


def confirmed_before(findings: list[Finding], day: object) -> list[Finding]:
    """Every confirmed finding at or before a day, earliest first."""
    when = parse_date(day)
    found = [f for f in findings if f.standing.moves_money and f.found_on <= when]
    return sorted(found, key=lambda f: (f.since or f.found_on, f.reference))


def earliest_since(findings: list[Finding], day: object) -> date | None:
    """The earliest day interference is judged to have begun, or nothing."""
    confirmed = confirmed_before(findings, day)
    if not confirmed:
        return None
    return min(f.since for f in confirmed if f.since is not None)


__all__ = [
    "Finding",
    "Standing",
    "TamperKind",
    "confirmed_before",
    "earliest_since",
    "tamper_kind",
]
