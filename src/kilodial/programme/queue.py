"""Filling the benches for a day.

The due list says which meters want testing and the work orders say who owns
each job. Neither says which bench a meter can actually go on, and that is not a
detail: a three element meter cannot go on a single phase bench, a class 480
meter cannot go on a bench that tops out at a hundred amps, and a bench whose
standard is out of certificate on the day cannot produce a usable result at all.

So the queue is a placement problem with hard constraints and it is solved the
dull way: orders in due date order, each one into the first bench that can hold
it and has a position free. That is not optimal and it does not need to be,
because the shop has four benches. What it does need to be is explainable, and
"the first bench that could take it" is explainable at a bench on a Monday
morning in a way that anything cleverer is not.

An order that cannot be placed is reported with the reason rather than dropped.
A meter nothing in the shop can test is a purchasing decision, and it only turns
into one if somebody sees it.
"""

from __future__ import annotations

from dataclasses import dataclass

from kilodial.errors import RuleError
from kilodial.model.bench import Bench
from kilodial.orders.order import OrderKind, Priority, WorkOrder
from kilodial.store.shop import Shop
from kilodial.units.span import parse_date


@dataclass(frozen=True)
class Slot:
    """One meter on one bench position for a day."""

    bench_code: str
    position: int
    order_reference: str
    meter_serial: str
    priority: Priority

    def __str__(self) -> str:
        return f"{self.bench_code}/{self.position} {self.meter_serial} ({self.order_reference})"


@dataclass(frozen=True)
class Day:
    """A day's bench plan."""

    on: str
    slots: tuple[Slot, ...]
    unplaced: tuple[tuple[str, str], ...]
    benches: tuple[str, ...]

    @property
    def placed(self) -> int:
        return len(self.slots)

    def on_bench(self, code: str) -> list[Slot]:
        wanted = code.strip().upper()
        return [slot for slot in self.slots if slot.bench_code == wanted]

    def load(self) -> dict[str, int]:
        """How many positions each bench has taken."""
        found = dict.fromkeys(self.benches, 0)
        for slot in self.slots:
            found[slot.bench_code] += 1
        return found

    def show(self) -> str:
        return (
            f"{self.on}: {self.placed} placed across {len(self.benches)} benches, "
            f"{len(self.unplaced)} left"
        )

    def __str__(self) -> str:
        return self.show()


def usable_benches(shop: Shop, on: object) -> list[tuple[Bench, str | None]]:
    """Every bench on the book with the reason it cannot be used, or nothing."""
    when = parse_date(on)
    found = []
    for bench in shop.benches.all():
        why: str | None = None
        if not bench.is_available_on(when):
            why = "out of service"
        else:
            standard = shop.standards.find(bench.standard_serial)
            if standard is None:
                why = f"names standard {bench.standard_serial}, which is not on the book"
            elif not standard.is_valid_on(when):
                why = f"standard {standard.serial} is out of certificate"
        found.append((bench, why))
    return found


def waiting(shop: Shop) -> list[WorkOrder]:
    """Live test orders, most urgent by due date first."""
    orders = [o for o in shop.orders.live() if o.kind is OrderKind.TEST]
    return sorted(orders, key=lambda o: (o.due_on, o.reference))


def plan_day(shop: Shop, *, on: object, orders: list[WorkOrder] | None = None) -> Day:
    """Place the waiting test orders onto the benches for a day."""
    when = parse_date(on)
    queue = waiting(shop) if orders is None else list(orders)
    benches = usable_benches(shop, when)
    live = [bench for bench, why in benches if why is None]
    if not live:
        raise RuleError(f"no bench can be used on {when.isoformat()}")
    taken = dict.fromkeys((b.code for b in live), 0)
    slots: list[Slot] = []
    unplaced: list[tuple[str, str]] = []
    for order in queue:
        meter = shop.meters.find(order.meter_serial)
        if meter is None:
            unplaced.append((order.reference, f"meter {order.meter_serial} is not on the book"))
            continue
        device = shop.devices.find(meter.device_key)
        if device is None:
            unplaced.append((order.reference, f"type {meter.device_key} is not catalogued"))
            continue
        placed = False
        reasons: list[str] = []
        for bench in live:
            if taken[bench.code] >= bench.positions:
                reasons.append(f"{bench.code} is full")
                continue
            if not bench.can_hold(device):
                reasons.append(f"{bench.code} cannot hold a {device.key}")
                continue
            taken[bench.code] += 1
            slots.append(
                Slot(bench.code, taken[bench.code], order.reference, meter.serial, order.priority)
            )
            placed = True
            break
        if not placed:
            unplaced.append((order.reference, "; ".join(reasons)))
    return Day(
        on=when.isoformat(),
        slots=tuple(slots),
        unplaced=tuple(unplaced),
        benches=tuple(b.code for b in live),
    )


def capacity(shop: Shop, on: object) -> int:
    """How many meters the shop could bench on a day if nothing got in the way."""
    return sum(bench.positions for bench, why in usable_benches(shop, on) if why is None)


__all__ = ["Day", "Slot", "capacity", "plan_day", "usable_benches", "waiting"]
