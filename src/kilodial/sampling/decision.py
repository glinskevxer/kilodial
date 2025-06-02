"""The decision a sample buys: the interval a group is put on next.

A sample outcome on its own is a statistic. What the shop cares about is what it
does to the group's test interval, and that is a step along a fixed ladder from
whatever the group is on now. Passing moves up one, failing moves down one, and
failing at the bottom is not an interval at all but an instruction to pull the
whole group.

The decision carries its own date and the whole working. A decision that cannot
be reconstructed three years later is a decision the utility will lose an
argument about, and three years is well inside the first interval.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from kilodial.errors import RuleError
from kilodial.sampling.plan import INTERVAL_LADDER, SampleOutcome, step_interval
from kilodial.units.span import add_months, parse_date
from kilodial.units.text import optional

MASS_TEST = "mass test"


@dataclass(frozen=True)
class Decision:
    """What a group's sample did to its interval."""

    group_code: str
    decided_on: date
    previous_months: int
    interval_months: int | None
    outcome: SampleOutcome
    note: str | None

    @property
    def passed(self) -> bool:
        return self.outcome.passed

    @property
    def is_mass_test(self) -> bool:
        """True when the group has run out of ladder and has to be pulled."""
        return self.interval_months is None

    @property
    def moved(self) -> str:
        months = self.interval_months
        if months is None:
            return MASS_TEST
        if months == self.previous_months:
            return "held"
        return "up" if months > self.previous_months else "down"

    def next_due(self) -> date | None:
        """When the group is next sampled, or nothing on a mass test."""
        if self.interval_months is None:
            return None
        return add_months(self.decided_on, self.interval_months)

    def reasons(self) -> tuple[str, ...]:
        return self.outcome.reasons

    def show(self) -> str:
        where = MASS_TEST if self.is_mass_test else f"{self.interval_months} months"
        return (
            f"{self.group_code} {self.decided_on.isoformat()}: "
            f"{'passed' if self.passed else 'failed'}, {self.previous_months} to {where}"
        )

    def __str__(self) -> str:
        return self.show()


def decide(
    group_code: str,
    outcome: SampleOutcome,
    *,
    on: object,
    current_months: int,
    note: object = None,
) -> Decision:
    """Turn a sample outcome into the group's next interval."""
    if current_months not in INTERVAL_LADDER:
        raise RuleError(
            f"group {group_code} is on {current_months} months, which is not a step "
            f"on the ladder {', '.join(str(m) for m in INTERVAL_LADDER)}"
        )
    return Decision(
        group_code=group_code.strip().upper(),
        decided_on=parse_date(on),
        previous_months=current_months,
        interval_months=step_interval(current_months, passed=outcome.passed),
        outcome=outcome,
        note=optional(note, "decision note", 240),
    )


def interval_after(decisions: list[Decision], *, start: int = INTERVAL_LADDER[0]) -> int:
    """Replay a group's decisions to get the interval it is on now.

    Replaying rather than storing the current interval is deliberate. The stored
    value and the history can disagree, and when they do it is always the stored
    value that is wrong, because the history is what the decisions were made on.
    """
    months = start
    for decision in sorted(decisions, key=lambda d: d.decided_on):
        if decision.interval_months is None:
            months = INTERVAL_LADDER[0]
            continue
        months = decision.interval_months
    return months


def decimal_or_zero(value: object) -> Decimal:
    """Read a stored statistic, treating a missing one as zero."""
    return Decimal(0) if value is None else Decimal(str(value))


__all__ = ["MASS_TEST", "Decision", "decide", "decimal_or_zero", "interval_after"]
