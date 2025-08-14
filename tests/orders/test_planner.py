from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from kilodial.errors import RuleError
from kilodial.model.bench import Bench, ReferenceStandard
from kilodial.model.device import DeviceType
from kilodial.model.form import Technology
from kilodial.model.meter import Meter
from kilodial.model.run import BenchPoint, BenchRun, RunKind
from kilodial.orders.order import OrderKind, OrderState, Priority
from kilodial.orders.planner import (
    has_live_order,
    next_reference,
    open_work,
    plan,
    raise_orders,
)
from kilodial.store.shop import Shop, open_shop


@pytest.fixture
def shop(tmp_path: Path) -> Iterator[Shop]:
    opened = open_shop(tmp_path / "shop.sqlite3", create=True)
    opened.devices.add(
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
    opened.standards.add(
        ReferenceStandard.build(
            "RS-5511",
            maker="Radian",
            model_code="RD-23",
            certificate="NVLAP-88214",
            certified_on="2015-01-01",
            certificate_due="2035-01-01",
            uncertainty="0.02",
        )
    )
    opened.benches.add(
        Bench.build(
            "B2",
            "north wall",
            positions=8,
            standard_serial="RS-5511",
            max_amperes="100",
            max_volts="480",
            polyphase=True,
            installed="2010-01-01",
        )
    )
    yield opened
    opened.close()


def stock(shop: Shop, serial: str, acquired: str = "2015-01-01") -> None:
    shop.meters.add(Meter.receive(serial, "Halvern/R4S", acquired=acquired))


def bench(shop: Shop, reference: str, serial: str, on: str) -> None:
    shop.runs.add(
        BenchRun.build(
            reference,
            meter_serial=serial,
            bench_code="B2",
            standard_serial="RS-5511",
            kind=RunKind.AS_FOUND,
            tested_on=on,
            technician="R Ellis",
            points=[
                BenchPoint.build("FL", amperes="30", volts="240", registration="100.10"),
                BenchPoint.build("LL", amperes="3", volts="240", registration="99.80"),
            ],
        )
    )


def test_a_plan_raises_nothing_on_a_current_fleet(shop: Shop) -> None:
    stock(shop, "84-119302", acquired="2024-01-01")
    planned = plan(shop, on="2025-01-01")
    assert planned.count == 0
    assert planned.show() == "0 orders, 0 meters skipped"


def test_an_overdue_meter_gets_a_high_priority_order(shop: Shop) -> None:
    stock(shop, "84-119302", acquired="2015-01-01")
    bench(shop, "TR-1", "84-119302", "2020-06-30")
    planned = plan(shop, on="2024-11-01")
    assert planned.count == 1
    assert planned.orders[0].priority is Priority.HIGH
    assert planned.orders[0].kind is OrderKind.TEST


def test_a_long_overdue_meter_is_urgent(shop: Shop) -> None:
    stock(shop, "84-119302", acquired="2010-01-01")
    planned = plan(shop, on="2025-01-01")
    assert planned.orders[0].priority is Priority.URGENT


def test_a_merely_due_meter_is_normal(shop: Shop) -> None:
    stock(shop, "84-119302", acquired="2015-01-01")
    bench(shop, "TR-1", "84-119302", "2021-01-15")
    planned = plan(shop, on="2025-02-01")
    assert planned.orders[0].priority is Priority.NORMAL


def test_the_note_says_why_the_order_exists(shop: Shop) -> None:
    stock(shop, "84-119302", acquired="2015-01-01")
    note = plan(shop, on="2025-01-01").orders[0].note
    assert note is not None
    assert "overdue since 2019-01-01" in note


def test_planning_does_not_write_anything(shop: Shop) -> None:
    stock(shop, "84-119302", acquired="2015-01-01")
    plan(shop, on="2025-01-01")
    assert shop.orders.count() == 0


def test_raising_writes_them(shop: Shop) -> None:
    stock(shop, "84-119302", acquired="2015-01-01")
    raised = raise_orders(shop, on="2025-01-01")
    assert shop.orders.count() == raised.count == 1
    assert shop.orders.all()[0].reference == "WO-2025-0001"


def test_references_do_not_collide_within_one_run(shop: Shop) -> None:
    for n in range(3):
        stock(shop, f"84-11930{n}", acquired="2015-01-01")
    raised = raise_orders(shop, on="2025-01-01")
    assert [o.reference for o in raised.orders] == [
        "WO-2025-0001",
        "WO-2025-0002",
        "WO-2025-0003",
    ]


def test_references_do_not_collide_across_runs(shop: Shop) -> None:
    stock(shop, "84-119302", acquired="2015-01-01")
    raise_orders(shop, on="2025-01-01")
    stock(shop, "84-119303", acquired="2015-01-01")
    raised = raise_orders(shop, on="2025-01-01")
    assert raised.orders[0].reference == "WO-2025-0002"


def test_a_meter_with_a_live_order_is_skipped(shop: Shop) -> None:
    stock(shop, "84-119302", acquired="2015-01-01")
    raise_orders(shop, on="2025-01-01")
    assert has_live_order(shop, "84-119302")
    second = plan(shop, on="2025-02-01")
    assert second.count == 0
    assert second.skipped == (("84-119302", "already has a live test order"),)


def test_a_closed_order_does_not_block_a_new_one(shop: Shop) -> None:
    stock(shop, "84-119302", acquired="2015-01-01")
    raise_orders(shop, on="2025-01-01")
    order = shop.orders.get("WO-2025-0001")
    shop.orders.save(order.done(on="2025-01-15", run_reference="TR-1"))
    assert not has_live_order(shop, "84-119302")
    assert plan(shop, on="2025-02-01").count == 1


def test_the_limit_caps_a_run(shop: Shop) -> None:
    for n in range(4):
        stock(shop, f"84-11930{n}", acquired="2015-01-01")
    raised = raise_orders(shop, on="2025-01-01", limit=2)
    assert raised.count == 2
    assert len(raised.skipped) == 2
    assert raised.skipped[0][1] == "over the limit for this run"


def test_a_daft_limit(shop: Shop) -> None:
    with pytest.raises(RuleError, match="positive number of orders"):
        plan(shop, on="2025-01-01", limit=0)


def test_the_priority_breakdown(shop: Shop) -> None:
    stock(shop, "84-119302", acquired="2010-01-01")
    stock(shop, "84-119303", acquired="2015-01-01")
    bench(shop, "TR-1", "84-119303", "2021-01-15")
    counts = plan(shop, on="2025-02-01").by_priority()
    assert counts[Priority.URGENT] == 1
    assert counts[Priority.NORMAL] == 1
    assert counts[Priority.LOW] == 0


def test_open_work_counts_every_state(shop: Shop) -> None:
    stock(shop, "84-119302", acquired="2015-01-01")
    raise_orders(shop, on="2025-01-01")
    counts = open_work(shop)
    assert counts[OrderState.OPEN] == 1
    assert set(counts) == set(OrderState)


def test_the_reference_generator_skips_what_is_taken(shop: Shop) -> None:
    stock(shop, "84-119302", acquired="2015-01-01")
    raise_orders(shop, on="2025-01-01")
    assert next_reference(shop, "2025-01-01", {"WO-2025-0002"}) == "WO-2025-0003"
