from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from kilodial.errors import RuleError
from kilodial.model.bench import Bench, ReferenceStandard
from kilodial.model.device import DeviceType
from kilodial.model.form import Technology
from kilodial.model.meter import Meter
from kilodial.orders.order import OrderKind, WorkOrder
from kilodial.programme.queue import capacity, plan_day, usable_benches, waiting
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
    opened.devices.add(
        DeviceType.build(
            "Vantage",
            "SM3",
            form_code="16S",
            class_code="320",
            voltage="277",
            kh="1.8",
            technology=Technology.SOLID_STATE,
            introduced="2014-05-01",
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
            "B1",
            "single phase row",
            positions=2,
            standard_serial="RS-5511",
            max_amperes="100",
            max_volts="480",
            installed="2010-01-01",
        )
    )
    yield opened
    opened.close()


def poly_bench(shop: Shop) -> None:
    shop.benches.add(
        Bench.build(
            "B2",
            "north wall",
            positions=2,
            standard_serial="RS-5511",
            max_amperes="100",
            max_volts="480",
            polyphase=True,
            installed="2010-01-01",
        )
    )


def stock(shop: Shop, serial: str, key: str = "Halvern/R4S") -> None:
    shop.meters.add(Meter.receive(serial, key, acquired="2015-01-01"))


def order(shop: Shop, reference: str, serial: str, **over: object) -> WorkOrder:
    args: dict[str, object] = {"raised_on": "2025-03-04"}
    args.update(over)
    return shop.orders.add(WorkOrder.raise_order(reference, OrderKind.TEST, serial, **args))


def test_every_bench_is_usable_on_a_good_day(shop: Shop) -> None:
    assert [why for _, why in usable_benches(shop, "2025-03-04")] == [None]
    assert capacity(shop, "2025-03-04") == 2


def test_a_bench_out_of_service(shop: Shop) -> None:
    shop.benches.save(
        Bench.build(
            "B1",
            "single phase row",
            positions=2,
            standard_serial="RS-5511",
            max_amperes="100",
            max_volts="480",
            installed="2010-01-01",
            removed="2024-01-01",
        )
    )
    assert usable_benches(shop, "2025-03-04")[0][1] == "out of service"
    assert capacity(shop, "2025-03-04") == 0


def test_a_bench_whose_standard_has_lapsed(shop: Shop) -> None:
    assert "out of certificate" in str(usable_benches(shop, "2036-01-01")[0][1])


def test_a_bench_whose_standard_is_gone(shop: Shop) -> None:
    shop.book.connection.execute("DELETE FROM reference_standard")
    assert "not on the book" in str(usable_benches(shop, "2025-03-04")[0][1])


def test_the_queue_is_live_test_orders_in_due_order(shop: Shop) -> None:
    stock(shop, "84-119302")
    stock(shop, "84-119303")
    order(shop, "WO-2", "84-119302", priority="low")
    order(shop, "WO-1", "84-119303", priority="urgent")
    shop.orders.add(
        WorkOrder.raise_order("WO-3", OrderKind.REPAIR, "84-119302", raised_on="2025-03-04")
    )
    assert [o.reference for o in waiting(shop)] == ["WO-1", "WO-2"]


def test_a_simple_day(shop: Shop) -> None:
    stock(shop, "84-119302")
    order(shop, "WO-1", "84-119302")
    day = plan_day(shop, on="2025-03-04")
    assert day.placed == 1
    assert day.slots[0].bench_code == "B1"
    assert day.slots[0].position == 1
    assert day.unplaced == ()
    assert "1 placed across 1 benches" in day.show()


def test_a_full_bench_takes_no_more(shop: Shop) -> None:
    for n in range(3):
        stock(shop, f"84-11930{n}")
        order(shop, f"WO-{n}", f"84-11930{n}")
    day = plan_day(shop, on="2025-03-04")
    assert day.placed == 2
    assert day.unplaced[0][1] == "B1 is full"
    assert day.load() == {"B1": 2}


def test_a_polyphase_meter_needs_a_polyphase_bench(shop: Shop) -> None:
    stock(shop, "84-220001", "Vantage/SM3")
    order(shop, "WO-1", "84-220001")
    day = plan_day(shop, on="2025-03-04")
    assert day.placed == 0
    assert "cannot hold a Vantage/SM3" in day.unplaced[0][1]
    poly_bench(shop)
    day = plan_day(shop, on="2025-03-04")
    assert day.placed == 1
    assert day.slots[0].bench_code == "B2"


def test_meters_go_on_the_first_bench_that_can_take_them(shop: Shop) -> None:
    poly_bench(shop)
    stock(shop, "84-119302")
    order(shop, "WO-1", "84-119302")
    day = plan_day(shop, on="2025-03-04")
    assert day.slots[0].bench_code == "B1"
    assert day.on_bench("b1")
    assert day.on_bench("B2") == []


def test_an_order_on_a_meter_that_is_gone(shop: Shop) -> None:
    stock(shop, "84-119302")
    order(shop, "WO-1", "84-119302")
    shop.book.connection.execute("DELETE FROM meter WHERE serial = '84-119302'")
    day = plan_day(shop, on="2025-03-04")
    assert "is not on the book" in day.unplaced[0][1]


def test_an_order_on_an_uncatalogued_type(shop: Shop) -> None:
    shop.meters.add(
        Meter.receive("84-119999", "Nowhere/X1", acquired="2015-01-01"),
        require_device=False,
    )
    order(shop, "WO-1", "84-119999")
    day = plan_day(shop, on="2025-03-04")
    assert "is not catalogued" in day.unplaced[0][1]


def test_a_day_with_no_usable_bench(shop: Shop) -> None:
    with pytest.raises(RuleError, match="no bench can be used"):
        plan_day(shop, on="2036-01-01")


def test_a_day_can_be_planned_from_a_given_list(shop: Shop) -> None:
    stock(shop, "84-119302")
    made = order(shop, "WO-1", "84-119302")
    day = plan_day(shop, on="2025-03-04", orders=[made])
    assert day.placed == 1
    assert plan_day(shop, on="2025-03-04", orders=[]).placed == 0


def test_the_slot_prints_where_it_is(shop: Shop) -> None:
    stock(shop, "84-119302")
    order(shop, "WO-1", "84-119302")
    slot = plan_day(shop, on="2025-03-04").slots[0]
    assert str(slot) == "B1/1 84-119302 (WO-1)"
