"""The tariff rules that decide whether there is an adjustment and how far back.

None of this is arithmetic. It is the set of choices a regulator has made, and
they are asymmetric on purpose, so writing them as one number would be wrong
even though it would be tidier.

A meter inside the in service tolerance is not adjusted at all. That is not
because the error is zero; it is because the tariff says a meter within
tolerance is deemed correct, and a utility that voluntarily refunded on a one
percent fast meter would be treating two customers differently for no reason
either of them could see.

The lookback is not symmetric. A meter that overbilled the customer is refunded
for up to five years. A meter that underbilled them is back billed for one. The
utility owns the meter, the utility tests it, and the customer had no way to
know, so the tariff puts the cost of a long undetected error on the utility.

A multiplier that was typed in wrong is not a meter error and is not covered by
the tolerance at all. It gets corrected in full in both directions, up to the
same five years, because there is no sense in which a customer billed at half
the right multiplier was billed correctly.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass
from decimal import Decimal

from kilodial.errors import BadInputError
from kilodial.install.multiplier import InstalledAccuracy


class Direction(enum.Enum):
    """Which way the money moves."""

    REFUND = "refund"
    BACK_BILL = "back bill"
    NONE = "none"

    @property
    def moves_money(self) -> bool:
        return self is not Direction.NONE

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class Tariff:
    """One jurisdiction's adjustment rules."""

    name: str
    tolerance: Decimal
    refund_months: int
    back_bill_months: int
    multiplier_months: int
    refund_interest: Decimal

    def __post_init__(self) -> None:
        if self.tolerance < 0:
            raise BadInputError("a tariff tolerance cannot be negative")
        for months in (self.refund_months, self.back_bill_months, self.multiplier_months):
            if months <= 0:
                raise BadInputError("a tariff lookback has to be a positive month count")
        if self.refund_interest < 0:
            raise BadInputError("a refund interest rate cannot be negative")

    def cap_for(self, direction: Direction, *, multiplier: bool) -> int:
        """How many months back the tariff lets an adjustment reach."""
        if multiplier:
            return self.multiplier_months
        if direction is Direction.REFUND:
            return self.refund_months
        return self.back_bill_months

    def __str__(self) -> str:
        return (
            f"{self.name}: +/-{self.tolerance} percent, refund {self.refund_months} months, "
            f"back bill {self.back_bill_months} months"
        )


# The rules this utility works under. A second jurisdiction would be a second
# constant here, not a branch through the code.
STATE_TARIFF = Tariff(
    name="state tariff 14.7",
    tolerance=Decimal("2.0"),
    refund_months=60,
    back_bill_months=12,
    multiplier_months=60,
    refund_interest=Decimal("0.06"),
)


def direction_of(accuracy: InstalledAccuracy) -> Direction:
    """Which way the money moves for an installation.

    A fast installation overbilled the customer, so the customer is refunded. A
    slow one underbilled them and the utility back bills. The reading used is
    the billed registration, which folds in a multiplier error, because that is
    what actually appeared on the bill.
    """
    reading = accuracy.billed_registration
    if reading.is_fast:
        return Direction.REFUND
    if reading.is_slow:
        return Direction.BACK_BILL
    return Direction.NONE


def is_adjustable(accuracy: InstalledAccuracy, tariff: Tariff = STATE_TARIFF) -> bool:
    """Whether the tariff calls for an adjustment at all."""
    if not accuracy.multiplier_is_right:
        return True
    return not accuracy.overall.within(tariff.tolerance)


def why_not(accuracy: InstalledAccuracy, tariff: Tariff = STATE_TARIFF) -> str | None:
    """The reason there is no adjustment, or nothing when there is one."""
    if is_adjustable(accuracy, tariff):
        return None
    return (
        f"{accuracy.overall} is inside the +/-{tariff.tolerance} percent "
        f"tolerance and the multiplier is right"
    )


def lookback_months(accuracy: InstalledAccuracy, tariff: Tariff = STATE_TARIFF) -> int:
    """How far back this particular installation's adjustment may reach."""
    return tariff.cap_for(direction_of(accuracy), multiplier=not accuracy.multiplier_is_right)


def error_share(accuracy: InstalledAccuracy) -> Decimal:
    """The fraction of what was billed that has to move, signed.

    Positive means the customer paid too much. A meter registering 103 percent
    billed 103 for every 100 that passed, so the customer is owed 3 divided by
    103 of what they paid, not 3 percent of it. Getting that denominator wrong
    is the classic error and it always favours the utility.
    """
    reading = accuracy.billed_registration
    if reading.percent == 0:
        raise BadInputError("an installation registering nothing has no error share")
    return ((reading.percent - Decimal(100)) / reading.percent).quantize(Decimal("0.00000001"))


__all__ = [
    "STATE_TARIFF",
    "Direction",
    "Tariff",
    "direction_of",
    "error_share",
    "is_adjustable",
    "lookback_months",
    "why_not",
]
