from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from kilodial.errors import ConfigError, DuplicateError, NotFoundError, RuleError
from kilodial.model.device import DeviceType
from kilodial.model.form import Technology
from kilodial.model.meter import Meter
from kilodial.orders.order import Disposition, OrderKind, OrderState, WorkOrder
from kilodial.store.book import Book, open_migrated
from kilodial.store.devices import DeviceRepository
from kilodial.store.meters import MeterRepository
from kilodial.store.orders import OrderRepository


@pytest.fixture
def repo(tmp_path: Path) -> Iterator[OrderRepository]:
    book: Book = open_migrated(tmp_path / "shop.sqlite3", create=True)
    DeviceRepository(book.connection).add(
        DeviceType.build(
            "Halvern",
            "R4S",
            form_code="2S",
            class_code="200",
            voltage="240",
            kh="7.2",
            technology=Technology.INDUCTION,
            register_ratio="100",
            introduced="2004-05-01",
        )
    )
    MeterRepository(book.connection).add(
        Meter.receive("84-119302", "Halvern/R4S", acquired="2015-01-01")
    )
    yield OrderRepository(book.connection)
    book.close()


def order(reference: str = "WO-1", kind: object = "test", **over: object) -> WorkOrder:
    args: dict[str, object] = {"raised_on": "2025-03-04"}
    args.update(over)
    return WorkOrder.raise_order(
        reference, kind, str(args.pop("meter_serial", "84-119302")), **args
    )


def test_orders_round_trip(repo: OrderRepository) -> None:
    added = repo.add(order(priority="urgent", point_code="SP-1042", note="pulled"))
    assert repo.get("wo-1") == added
    assert repo.count() == 1


def test_the_same_reference_twice(repo: OrderRepository) -> None:
    repo.add(order())
    with pytest.raises(DuplicateError, match="work order"):
        repo.add(order())


def test_an_order_on_a_meter_nobody_has(repo: OrderRepository) -> None:
    with pytest.raises(RuleError, match="not on the book"):
        repo.add(order(meter_serial="84-000000"))


def test_a_receiving_order_may_come_first(repo: OrderRepository) -> None:
    repo.add(order("WO-1", "receive", meter_serial="84-000000"))
    assert repo.get("WO-1").meter_serial == "84-000000"


def test_an_order_that_is_not_there(repo: OrderRepository) -> None:
    with pytest.raises(NotFoundError, match="work order"):
        repo.get("WO-1")
    with pytest.raises(NotFoundError):
        repo.save(order())


def test_assigning_and_closing_survive_a_round_trip(repo: OrderRepository) -> None:
    repo.add(order())
    repo.save(repo.get("WO-1").assigned("R Ellis"))
    assert repo.get("WO-1").state is OrderState.ASSIGNED
    repo.save(repo.get("WO-1").done(on="2025-03-14", run_reference="TR-1"))
    closed = repo.get("WO-1")
    assert closed.state is OrderState.DONE
    assert closed.run_reference == "TR-1"


def test_a_repair_disposition_survives(repo: OrderRepository) -> None:
    repo.add(order("WO-2", "repair"))
    repo.save(repo.get("WO-2").done(on="2025-03-14", disposition="scrapped"))
    assert repo.get("WO-2").disposition is Disposition.SCRAPPED


def test_the_live_list_leaves_out_the_closed(repo: OrderRepository) -> None:
    repo.add(order("WO-1"))
    repo.add(order("WO-2", "receive"))
    repo.save(repo.get("WO-2").done(on="2025-03-14"))
    assert [o.reference for o in repo.live()] == ["WO-1"]


def test_late_orders(repo: OrderRepository) -> None:
    repo.add(order("WO-1", priority="urgent"))
    repo.add(order("WO-2", priority="low"))
    assert [o.reference for o in repo.late_on("2025-03-10")] == ["WO-1"]
    assert [o.reference for o in repo.late_on("2025-07-01")] == ["WO-1", "WO-2"]
    assert repo.late_on("2025-03-05") == []


def test_filtering(repo: OrderRepository) -> None:
    repo.add(order("WO-1", "test"))
    repo.add(order("WO-2", "repair"))
    repo.save(repo.get("WO-2").assigned("R Ellis"))
    assert [o.reference for o in repo.by_kind(OrderKind.REPAIR)] == ["WO-2"]
    assert [o.reference for o in repo.assigned_to("R Ellis")] == ["WO-2"]
    assert [o.reference for o in repo.for_meter("84-119302")] == ["WO-1", "WO-2"]
    assert repo.assigned_to("Nobody") == []


def test_counts_by_state(repo: OrderRepository) -> None:
    repo.add(order("WO-1"))
    repo.add(order("WO-2", "receive"))
    repo.save(repo.get("WO-2").done(on="2025-03-14"))
    counts = repo.counts_by_state()
    assert set(counts) == set(OrderState)
    assert counts[OrderState.OPEN] == 1
    assert counts[OrderState.DONE] == 1
    assert counts[OrderState.CANCELLED] == 0


def test_a_row_holding_a_kind_nobody_raises(repo: OrderRepository) -> None:
    repo.add(order())
    repo._conn.execute("UPDATE work_order SET kind = 'DANCE'")
    with pytest.raises(ConfigError, match="not a work order kind"):
        repo.get("WO-1")


def test_a_row_holding_a_state_nobody_uses(repo: OrderRepository) -> None:
    repo.add(order())
    repo._conn.execute("UPDATE work_order SET state = 'MAYBE'")
    with pytest.raises(ConfigError, match="not a work order state"):
        repo.get("WO-1")
