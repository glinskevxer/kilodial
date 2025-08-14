"""Turning the due list into work orders somebody can be handed.

The due list says which meters are past their interval. It does not say what the
shop is going to do about it, and the gap between those two is where a periodic
programme quietly stops happening: everybody can see the list, nobody owns a row
on it.

So the planner raises a test order per meter, with a priority that follows how
late the meter is. An overdue meter gets a high priority order, a merely due one
gets a normal order, and a meter already carrying a live order gets nothing,
because raising a second order for the same job is how a shop ends up testing a
meter twice and reporting it once.

References are generated rather than asked for, because a season is a hundred
orders and nobody is typing a hundred references.
"""

from __future__ import annotations

from dataclasses import dataclass

from kilodial.errors import RuleError
from kilodial.orders.order import OrderKind, OrderState, Priority, WorkOrder
from kilodial.programme import roster
from kilodial.programme.schedule import DueMeter, DueState
from kilodial.store.shop import Shop

PREFIX = "WO"


@dataclass(frozen=True)
class Plan:
    """What a planning run would raise, before it raises anything."""

    orders: tuple[WorkOrder, ...]
    skipped: tuple[tuple[str, str], ...]

    @property
    def count(self) -> int:
        return len(self.orders)

    def by_priority(self) -> dict[Priority, int]:
        found = dict.fromkeys(Priority, 0)
        for order in self.orders:
            found[order.priority] += 1
        return found

    def show(self) -> str:
        return f"{self.count} orders, {len(self.skipped)} meters skipped"

    def __str__(self) -> str:
        return self.show()


def priority_for(line: DueMeter) -> Priority:
    """How urgent testing one meter is, from how far past due it is."""
    if line.state is DueState.OVERDUE:
        return Priority.HIGH if line.days_over < 365 else Priority.URGENT
    return Priority.NORMAL


def has_live_order(shop: Shop, serial: str) -> bool:
    """Whether somebody is already on the hook for testing this meter."""
    return any(
        order.kind is OrderKind.TEST and order.state.is_live
        for order in shop.orders.for_meter(serial)
    )


def next_reference(shop: Shop, on: object, taken: set[str]) -> str:
    """The next free order reference for a day, counting from one."""
    year = str(on)[:4]
    used = {o.reference for o in shop.orders.all()} | taken
    number = 1
    while f"{PREFIX}-{year}-{number:04d}" in used:
        number += 1
    return f"{PREFIX}-{year}-{number:04d}"


def plan(shop: Shop, *, on: object, limit: int | None = None) -> Plan:
    """Work out which test orders a season would raise, without raising them."""
    if limit is not None and limit <= 0:
        raise RuleError("a planning limit has to be a positive number of orders")
    built: list[WorkOrder] = []
    skipped: list[tuple[str, str]] = []
    taken: set[str] = set()
    for line in roster.build(shop, on=on).needing_work():
        if limit is not None and len(built) >= limit:
            skipped.append((line.serial, "over the limit for this run"))
            continue
        if has_live_order(shop, line.serial):
            skipped.append((line.serial, "already has a live test order"))
            continue
        reference = next_reference(shop, on, taken)
        taken.add(reference)
        built.append(
            WorkOrder.raise_order(
                reference,
                OrderKind.TEST,
                line.serial,
                raised_on=on,
                priority=priority_for(line),
                note=f"{line.state} since {line.due.isoformat()}, group {line.group_code}",
            )
        )
    return Plan(tuple(built), tuple(skipped))


def raise_orders(shop: Shop, *, on: object, limit: int | None = None) -> Plan:
    """Plan and then actually put the orders on the book."""
    planned = plan(shop, on=on, limit=limit)
    for order in planned.orders:
        shop.orders.add(order)
    return planned


def open_work(shop: Shop) -> dict[OrderState, int]:
    """A count of what is outstanding, for the planner's own output."""
    return shop.orders.counts_by_state()


__all__ = [
    "PREFIX",
    "Plan",
    "has_live_order",
    "next_reference",
    "open_work",
    "plan",
    "priority_for",
    "raise_orders",
]
