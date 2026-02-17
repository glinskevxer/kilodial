from __future__ import annotations

from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path

import pytest

from kilodial.model.device import DeviceType
from kilodial.model.form import Technology
from kilodial.model.meter import Meter
from kilodial.model.repair import Fault, Repair
from kilodial.report import faults as report
from kilodial.store.shop import Shop, open_shop
from kilodial.tools.smoke import stand_up
from kilodial.units.money import Money
from kilodial.units.span import DateSpan

YEAR = DateSpan("2025-01-01", "2025-12-31")


@pytest.fixture
def shop(tmp_path: Path) -> Iterator[Shop]:
    opened = open_shop(tmp_path / "shop.sqlite3", create=True)
    stand_up(opened)
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
    for index in range(4):
        opened.meters.add(
            Meter.receive(f"84-2200{index:02d}", "Vantage/SM3", acquired="2019-01-01")
        )
    yield opened
    opened.close()


def repair(shop: Shop, reference: str, serial: str, fault: Fault, **over: object) -> None:
    args: dict[str, object] = {
        "repaired_on": "2025-03-14",
        "by": "R Ellis",
        "hours": "1",
        "parts": "12.40",
        "replacement_cost": "184.00",
    }
    args.update(over)
    shop.repairs.add(Repair.build(reference, serial, fault, **args))


def test_a_type_with_no_repairs(shop: Shop) -> None:
    found = report.for_type(shop, "Halvern/R4S", YEAR)
    assert found.meters == 1
    assert found.repairs == 0
    assert found.per_hundred == Decimal("0.0")
    assert found.a_meter.is_zero
    assert found.commonest is None


def test_the_rate_is_per_hundred_meters(shop: Shop) -> None:
    repair(shop, "RP-1", "84-220000", Fault.BOARD)
    found = report.for_type(shop, "Vantage/SM3", YEAR)
    assert found.meters == 4
    assert found.repairs == 1
    assert found.per_hundred == Decimal("25.0")


def test_the_spend_per_meter(shop: Shop) -> None:
    repair(shop, "RP-1", "84-220000", Fault.BOARD, hours="1", parts="0")
    found = report.for_type(shop, "Vantage/SM3", YEAR)
    assert found.spent == Money("68.00")
    assert found.a_meter == Money("17.00")


def test_the_commonest_fault(shop: Shop) -> None:
    repair(shop, "RP-1", "84-220000", Fault.BOARD)
    repair(shop, "RP-2", "84-220001", Fault.BOARD)
    repair(shop, "RP-3", "84-220002", Fault.BATTERY)
    assert report.for_type(shop, "Vantage/SM3", YEAR).commonest is Fault.BOARD


def test_repairs_outside_the_window_are_not_counted(shop: Shop) -> None:
    repair(shop, "RP-1", "84-220000", Fault.BOARD, repaired_on="2024-03-14")
    assert report.for_type(shop, "Vantage/SM3", YEAR).repairs == 0


def test_repairs_on_another_type_are_not_counted(shop: Shop) -> None:
    repair(shop, "RP-1", "84-119302", Fault.BEARING)
    assert report.for_type(shop, "Vantage/SM3", YEAR).repairs == 0
    assert report.for_type(shop, "Halvern/R4S", YEAR).repairs == 1


def test_wasteful_repairs_are_counted_apart(shop: Shop) -> None:
    repair(shop, "RP-1", "84-220000", Fault.BOARD, hours="2", parts="40.00")
    found = report.for_type(shop, "Vantage/SM3", YEAR)
    assert found.wasteful == 1


def test_nothing_found_is_not_wasteful(shop: Shop) -> None:
    repair(shop, "RP-1", "84-220000", Fault.NONE_FOUND, hours="3", parts="0")
    found = report.for_type(shop, "Vantage/SM3", YEAR)
    assert found.repairs == 1
    assert found.wasteful == 0


def test_the_grid_puts_the_worst_rate_first(shop: Shop) -> None:
    repair(shop, "RP-1", "84-119302", Fault.BEARING)
    rows = [report.for_type(shop, d.key, YEAR) for d in shop.devices.all()]
    assert report.grid(rows).dicts()[0]["type"] == "Halvern/R4S"


def test_the_family_grid_covers_every_family(shop: Shop) -> None:
    repair(shop, "RP-1", "84-220000", Fault.BOARD)
    rows = [report.for_type(shop, d.key, YEAR) for d in shop.devices.all()]
    grid = report.family_grid(rows)
    families = {row["family"] for row in grid.dicts()}
    assert "electronic" in families
    assert "mechanical" in families
    electronic = next(r for r in grid.dicts() if r["family"] == "electronic")
    assert electronic["repairs"] == "1"
    assert electronic["percent"] == "100.0"


def test_the_family_grid_of_nothing(shop: Shop) -> None:
    rows = [report.for_type(shop, d.key, YEAR) for d in shop.devices.all()]
    assert all(r["percent"] == "0.0" for r in report.family_grid(rows).dicts())


def test_the_report_names_the_worst_type(shop: Shop) -> None:
    repair(shop, "RP-1", "84-220000", Fault.BOARD)
    doc = report.build(shop, first="2025-01-01", last="2025-12-31")
    assert "Fault report" in doc.title
    assert dict(doc.sections[0].facts)["repairs"] == "1"
    assert "Vantage/SM3 is the worst" in doc.sections[0].notes[0]


def test_a_report_with_no_repairs_says_nothing_about_a_worst(shop: Shop) -> None:
    doc = report.build(shop, first="2025-01-01", last="2025-12-31")
    assert doc.sections[0].notes == []


def test_the_report_renders(shop: Shop) -> None:
    doc = report.build(shop, first="2025-01-01", last="2025-12-31")
    assert doc.as_csv().startswith("type,meters,repairs")
