"""Work orders, and the rules about what closes one.

Everything else in this package describes what is true about a meter. A work
order is the only thing that says what somebody is going to do about it, which
makes it the record the shop supervisor actually looks at.

The rule worth spelling out is that different kinds of order close differently.
A test order is not done because a technician says so; it is done when there is
a run on the book, and the order carries that run's reference. A repair order
closes with a disposition, because the interesting question about a repair is
whether the meter went back to stock or to the scrap bin. Closing either one
without its evidence is the thing this module refuses.

Priority sets the due date and nothing else. A high priority order that is three
weeks old is not more urgent than it was; it is late, and the due date says so
in a way a priority label never does.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, replace
from datetime import date, timedelta

from kilodial.errors import BadInputError, RuleError, StateError
from kilodial.units.span import parse_date
from kilodial.units.text import key, optional, tidy


class OrderKind(enum.Enum):
    """What the order is asking somebody to do."""

    RECEIVE = ("receive", False, False)
    TEST = ("test", True, False)
    REPAIR = ("repair", False, True)
    SET = ("set", False, False)
    PULL = ("pull", False, False)
    SCRAP = ("scrap", False, False)

    def __init__(self, label: str, needs_run: bool, needs_disposition: bool) -> None:
        self.label = label
        self.needs_run = needs_run
        self.needs_disposition = needs_disposition

    def __str__(self) -> str:
        return self.label


class Priority(enum.Enum):
    """How long the shop has before the order is late."""

    URGENT = ("urgent", 2)
    HIGH = ("high", 7)
    NORMAL = ("normal", 30)
    LOW = ("low", 90)

    def __init__(self, label: str, days: int) -> None:
        self.label = label
        self.days = days

    def __str__(self) -> str:
        return self.label


class OrderState(enum.Enum):
    """Where the order is."""

    OPEN = "open"
    ASSIGNED = "assigned"
    DONE = "done"
    CANCELLED = "cancelled"

    @property
    def is_live(self) -> bool:
        return self in (OrderState.OPEN, OrderState.ASSIGNED)

    def __str__(self) -> str:
        return self.value


class Disposition(enum.Enum):
    """What became of a meter that went through repair."""

    RETURNED = "returned to stock"
    SCRAPPED = "scrapped"
    UNREPAIRABLE = "unrepairable, held"

    def __str__(self) -> str:
        return self.value


def order_kind(value: object) -> OrderKind:
    """Read an order kind by its label."""
    if isinstance(value, OrderKind):
        return value
    wanted = str(value).strip().lower()
    for member in OrderKind:
        if member.label == wanted:
            return member
    raise BadInputError(f"{value!r} is not a work order kind")


def priority_named(value: object) -> Priority:
    """Read a priority by its label."""
    if isinstance(value, Priority):
        return value
    wanted = str(value).strip().lower()
    for member in Priority:
        if member.label == wanted:
            return member
    raise BadInputError(f"{value!r} is not a work order priority")


def disposition_named(value: object) -> Disposition:
    """Read a repair disposition by its label."""
    if isinstance(value, Disposition):
        return value
    wanted = str(value).strip().lower()
    for member in Disposition:
        if member.value == wanted or member.name.lower() == wanted:
            return member
    raise BadInputError(f"{value!r} is not a repair disposition")


@dataclass(frozen=True)
class WorkOrder:
    """One job, from the day it was raised to the day it was closed."""

    reference: str
    kind: OrderKind
    meter_serial: str
    point_code: str | None
    priority: Priority
    raised_on: date
    state: OrderState
    assigned_to: str | None
    closed_on: date | None
    run_reference: str | None
    disposition: Disposition | None
    note: str | None

    @classmethod
    def raise_order(
        cls,
        reference: object,
        kind: object,
        meter_serial: object,
        *,
        raised_on: object,
        priority: object = Priority.NORMAL,
        point_code: object = None,
        note: object = None,
    ) -> WorkOrder:
        """Open a new order against a meter."""
        return cls(
            reference=key(reference, "work order reference", 24),
            kind=order_kind(kind),
            meter_serial=key(meter_serial, "meter serial", 24),
            point_code=None if point_code is None else key(point_code, "point code", 16),
            priority=priority_named(priority),
            raised_on=parse_date(raised_on),
            state=OrderState.OPEN,
            assigned_to=None,
            closed_on=None,
            run_reference=None,
            disposition=None,
            note=optional(note, "order note", 240),
        )

    @property
    def due_on(self) -> date:
        """The day the order goes late, from its priority."""
        return self.raised_on + timedelta(days=self.priority.days)

    @property
    def is_live(self) -> bool:
        return self.state.is_live

    def is_late_on(self, day: object) -> bool:
        """Whether the order is past its due date and still open."""
        return self.is_live and parse_date(day) > self.due_on

    def assigned(self, to: object) -> WorkOrder:
        """Put somebody's name on it."""
        if not self.is_live:
            raise StateError(f"work order {self.reference} is {self.state}")
        return replace(self, state=OrderState.ASSIGNED, assigned_to=tidy(to, "technician name", 40))

    def done(
        self,
        *,
        on: object,
        run_reference: object = None,
        disposition: object = None,
    ) -> WorkOrder:
        """Close the order, refusing to close one without its evidence."""
        if not self.is_live:
            raise StateError(f"work order {self.reference} is already {self.state}")
        when = parse_date(on)
        if when < self.raised_on:
            raise RuleError("a work order cannot be closed before it was raised")
        if self.kind.needs_run and run_reference is None:
            raise RuleError(f"a {self.kind} order closes with the run that answered it")
        if self.kind.needs_disposition and disposition is None:
            raise RuleError(f"a {self.kind} order closes with what became of the meter")
        if run_reference is not None and not self.kind.needs_run:
            raise RuleError(f"a {self.kind} order does not carry a run")
        if disposition is not None and not self.kind.needs_disposition:
            raise RuleError(f"a {self.kind} order does not carry a disposition")
        return replace(
            self,
            state=OrderState.DONE,
            closed_on=when,
            run_reference=None if run_reference is None else key(run_reference, "run", 24),
            disposition=None if disposition is None else disposition_named(disposition),
        )

    def cancelled(self, *, on: object, why: object) -> WorkOrder:
        """Close the order without doing it, which needs a reason."""
        if not self.is_live:
            raise StateError(f"work order {self.reference} is already {self.state}")
        reason = optional(why, "cancellation reason", 240)
        if reason is None:
            raise RuleError("cancelling a work order needs a reason")
        return replace(
            self,
            state=OrderState.CANCELLED,
            closed_on=parse_date(on),
            note=reason if self.note is None else f"{self.note}; {reason}",
        )

    def days_open(self, day: object) -> int:
        """How long it has been open, or was open before it closed."""
        end = self.closed_on if self.closed_on is not None else parse_date(day)
        return (end - self.raised_on).days

    def __str__(self) -> str:
        return f"{self.reference} {self.kind} {self.meter_serial} ({self.state})"


__all__ = [
    "Disposition",
    "OrderKind",
    "OrderState",
    "Priority",
    "WorkOrder",
    "disposition_named",
    "order_kind",
    "priority_named",
]
