"""A customer asking for their meter to be tested.

This is a small module with a lot of tariff in it, and every rule in it exists
because somebody argued about a bill.

The utility has thirty days from the request to run the test. Miss it and the
fee is waived whatever the meter turns out to be, because the delay is the
utility's and a customer should not pay for it.

The fee is charged only if the meter is found inside tolerance. A meter found
outside it was the utility's problem all along and the customer was right to
ask.

A customer gets one chargeable free test every two years. Ask again inside that
window and, if the meter is accurate again, the fee stands. Ask again after it
and the clock has reset. The window runs from the last test the customer
requested, not from any test the shop happened to do.

The run that answers a complaint has to be a referee run. An ordinary as found
run made for the periodic programme is not an answer, even if it happens to have
been done in the right week, because the customer is entitled to a test made in
response to their request and to be told when it will happen.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from kilodial.errors import BadInputError, RuleError
from kilodial.units.money import Money
from kilodial.units.span import add_months, parse_date
from kilodial.units.text import key, optional, tidy

RESPONSE_DAYS = 30
FREE_TEST_MONTHS = 24
STANDARD_FEE = Money("28.00")


class Reason(enum.Enum):
    """Why the customer says the meter is wrong."""

    HIGH_BILL = "high bill"
    LOW_BILL = "low bill"
    NO_USAGE = "no usage"
    SUSPECTED_TAMPER = "suspected tamper"
    OTHER = "other"

    def __str__(self) -> str:
        return self.value


class Charge(enum.Enum):
    """What the customer ends up owing for the test."""

    CHARGED = "charged"
    WAIVED_ACCURACY = "waived, meter outside tolerance"
    WAIVED_LATE = "waived, tested past the deadline"
    WAIVED_FREE = "waived, first test in the free window"

    @property
    def payable(self) -> bool:
        return self is Charge.CHARGED

    def __str__(self) -> str:
        return self.value


def reason_named(text: object) -> Reason:
    """Read a complaint reason by name, taking either spelling of the enum."""
    if isinstance(text, Reason):
        return text
    if not isinstance(text, str):
        raise BadInputError(f"cannot read a complaint reason from {type(text).__name__}")
    wanted = text.strip().lower().replace("_", " ")
    for member in Reason:
        if member.value == wanted:
            return member
    raise BadInputError(f"{text!r} is not a complaint reason")


@dataclass(frozen=True)
class Request:
    """One customer request, from the day it was made."""

    reference: str
    point_code: str
    requested_on: date
    requested_by: str
    reason: Reason
    note: str | None
    previous_request_on: date | None

    @classmethod
    def build(
        cls,
        reference: object,
        point_code: object,
        *,
        requested_on: object,
        requested_by: object,
        reason: object = Reason.OTHER,
        note: object = None,
        previous_request_on: object = None,
    ) -> Request:
        made = parse_date(requested_on)
        previous = None if previous_request_on is None else parse_date(previous_request_on)
        if previous is not None and previous > made:
            raise RuleError("a previous request cannot be later than this one")
        return cls(
            reference=key(reference, "request reference", 24),
            point_code=key(point_code, "service point code", 16),
            requested_on=made,
            requested_by=tidy(requested_by, "requester", 60),
            reason=reason_named(reason),
            note=optional(note, "request note", 240),
            previous_request_on=previous,
        )

    @property
    def due_by(self) -> date:
        """The last day the utility may run the test without waiving the fee."""
        return _plus_days(self.requested_on, RESPONSE_DAYS)

    @property
    def free_window_ends(self) -> date | None:
        """When the customer's free test entitlement comes back."""
        if self.previous_request_on is None:
            return None
        return add_months(self.previous_request_on, FREE_TEST_MONTHS)

    def in_free_window(self) -> bool:
        """True when this request is the customer's free one."""
        ends = self.free_window_ends
        return ends is None or self.requested_on > ends

    def was_late(self, tested_on: object) -> bool:
        return parse_date(tested_on) > self.due_by

    def days_taken(self, tested_on: object) -> int:
        return (parse_date(tested_on) - self.requested_on).days

    def __str__(self) -> str:
        return f"{self.reference} {self.point_code} {self.requested_on.isoformat()} ({self.reason})"


def _plus_days(day: date, days: int) -> date:
    return day + timedelta(days=days)


def charge_for(
    request: Request,
    *,
    tested_on: object,
    within_tolerance: bool,
    fee: Money = STANDARD_FEE,
) -> tuple[Charge, Money]:
    """Decide what the customer owes, in the order the tariff applies the rules.

    The order matters and it is the customer's order: accuracy first, because a
    bad meter waives the fee whatever else happened; then lateness, because a
    late test waives it even on a good meter; then the free window.
    """
    if fee.cents < 0:
        raise BadInputError("a complaint test fee cannot be negative")
    if not within_tolerance:
        return (Charge.WAIVED_ACCURACY, Money.zero())
    if request.was_late(tested_on):
        return (Charge.WAIVED_LATE, Money.zero())
    if request.in_free_window():
        return (Charge.WAIVED_FREE, Money.zero())
    return (Charge.CHARGED, fee)


def fee_share(fee: Money, charged: Charge) -> Decimal:
    """How much of the fee is actually payable, as a fraction. Zero or one."""
    if fee.is_zero:
        return Decimal(0)
    return Decimal(1) if charged.payable else Decimal(0)


__all__ = [
    "FREE_TEST_MONTHS",
    "RESPONSE_DAYS",
    "STANDARD_FEE",
    "Charge",
    "Reason",
    "Request",
    "charge_for",
    "fee_share",
    "reason_named",
]
