"""The other kind of sample plan: count the bad ones instead of measuring spread.

The variables plan in ``plan.py`` uses the mean and the spread of the readings,
which is the stronger test and needs every reading. An attributes plan asks one
question of each meter, in or out of tolerance, and decides on the count. It is
weaker and it is the one a shop reaches for when the readings are coming off a
handheld that reports pass or fail and nothing else, which is a real situation
and not a hypothetical one.

The numbers are the ordinary single sampling shape: a sample size for each lot
size, an acceptance number, and a rejection number one above it. There is no
double sampling here, and the reason is that a second sample doubles the shop's
work to buy a decision it will make anyway; the shop rejects and mass tests.

The two plans are deliberately not merged. They answer the same question with
different evidence and a group has to be on one or the other, because a group
that gets to pick the plan after the readings are in is a group that never fails.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from kilodial.errors import RuleError

# Lot size ceiling, sample size, acceptance number. A lot at or under the first
# ceiling is inspected whole and accepts on nothing at all.
PLANS: tuple[tuple[int, int, int], ...] = (
    (25, 0, 0),
    (50, 13, 0),
    (90, 20, 1),
    (150, 32, 2),
    (280, 50, 3),
    (500, 80, 5),
    (1200, 125, 7),
    (3200, 200, 10),
    (10000, 315, 14),
)
LARGEST = (500, 21)


@dataclass(frozen=True)
class Plan:
    """One row of the table: how many to test and how many bad ones are allowed."""

    lot: int
    sample: int
    accept: int

    @property
    def reject(self) -> int:
        """One more bad than the acceptance number rejects the lot."""
        return self.accept + 1

    @property
    def whole_lot(self) -> bool:
        """Whether the lot is small enough to be inspected entire."""
        return self.sample == 0

    @property
    def tested(self) -> int:
        """How many meters actually go on the bench."""
        return self.lot if self.whole_lot else min(self.sample, self.lot)

    @property
    def allowed_share(self) -> Decimal:
        """The failure rate the plan tolerates, for comparing plans."""
        if self.tested == 0:
            return Decimal(0)
        return (Decimal(self.accept) / self.tested * 100).quantize(Decimal("0.01"))

    def __str__(self) -> str:
        return (
            f"lot {self.lot}: test {self.tested}, accept on {self.accept}, reject on {self.reject}"
        )


def plan_for(lot: int) -> Plan:
    """The plan a lot of that size is inspected under."""
    if lot < 0:
        raise RuleError("a lot cannot be a negative number of meters")
    for ceiling, sample, accept in PLANS:
        if lot <= ceiling:
            return Plan(lot, sample, accept)
    return Plan(lot, LARGEST[0], LARGEST[1])


@dataclass(frozen=True)
class Outcome:
    """What an attributes sample decided."""

    plan: Plan
    tested: int
    failed: int
    reasons: tuple[str, ...]

    @property
    def passed(self) -> bool:
        return not self.reasons

    @property
    def share(self) -> Decimal:
        if self.tested == 0:
            return Decimal(0)
        return (Decimal(self.failed) / self.tested * 100).quantize(Decimal("0.01"))

    def show(self) -> str:
        return (
            f"{self.failed} of {self.tested} failed against an acceptance number "
            f"of {self.plan.accept}"
        )

    def __str__(self) -> str:
        return f"{'passed' if self.passed else 'failed'}: {self.show()}"


def assess(*, lot: int, tested: int, failed: int) -> Outcome:
    """Judge a sample on its count of failures alone."""
    plan = plan_for(lot)
    if tested < 0 or failed < 0:
        raise RuleError("a count of meters cannot be negative")
    if failed > tested:
        raise RuleError(f"{failed} of {tested} failed, which is more than were tested")
    if tested > lot:
        raise RuleError(f"{tested} were tested out of a lot of {lot}")
    reasons: list[str] = []
    if tested < plan.tested:
        reasons.append(f"the sample is {tested} and a lot of {lot} calls for {plan.tested}")
    if failed >= plan.reject:
        reasons.append(f"{failed} failed, and this plan rejects on {plan.reject}")
    return Outcome(plan, tested, failed, tuple(reasons))


def comparable(lot: int) -> tuple[int, Decimal]:
    """The sample size and tolerated failure rate, for setting a group's plan."""
    plan = plan_for(lot)
    return (plan.tested, plan.allowed_share)


__all__ = ["LARGEST", "PLANS", "Outcome", "Plan", "assess", "comparable", "plan_for"]
