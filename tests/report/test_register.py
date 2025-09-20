from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from kilodial.adjust.compute import BilledMonth
from kilodial.install.point import MeterSet, ServicePoint
from kilodial.model.form import Service
from kilodial.model.meter import Meter
from kilodial.model.run import BenchPoint, BenchRun, RunKind
from kilodial.report import register as report
from kilodial.store.shop import Shop, open_shop
from kilodial.tools.smoke import LAST_DAY, stand_up
from kilodial.units.money import Money


@pytest.fixture
def shop(tmp_path: Path) -> Iterator[Shop]:
    opened = open_shop(tmp_path / "shop.sqlite3", create=True)
    stand_up(opened)
    yield opened
    opened.close()


def bench(shop: Shop, reference: str, serial: str, pct: str, on: str = "2025-06-30") -> None:
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
                BenchPoint.build("FL", amperes="30", volts="240", registration=pct),
                BenchPoint.build("LL", amperes="3", volts="240", registration=pct),
            ],
        )
    )


def second_point(shop: Shop, code: str = "SP-1043", serial: str = "84-119303") -> None:
    shop.meters.add(Meter.receive(serial, "Halvern/R4S", acquired="2015-01-01"))
    shop.points.add(
        ServicePoint.build(
            code,
            account="44-9022",
            address="20 Fenwick Row",
            service=Service.SINGLE_PHASE_3W,
            voltage="240",
            rate_code="R1",
            energised="2011-06-14",
        )
    )
    shop.installs.set_meter(
        MeterSet.build(code, serial, programmed_multiplier="1", set_on="2019-05-02")
    )
    for index in range(1, 7):
        shop.billing.add(
            code,
            BilledMonth.of(f"2025-{index:02d}-01", f"2025-{index:02d}-{LAST_DAY[index]}", "100.00"),
        )


def test_a_point_inside_tolerance_is_passed_over(shop: Shop) -> None:
    bench(shop, "TR-1", "84-119302", "100.10")
    found = report.gather(shop, on="2025-07-15")
    assert found.priced == ()
    assert "inside the" in found.passed_over[0][1]


def test_a_fast_meter_is_priced_as_a_refund(shop: Shop) -> None:
    bench(shop, "TR-1", "84-119302", "103.00")
    found = report.gather(shop, on="2025-07-15")
    assert len(found.priced) == 1
    assert len(found.refunds) == 1
    assert found.back_bills == []
    assert found.owed_to_customers().cents > 0
    assert found.owed_to_utility().is_zero
    assert found.net().cents > 0


def test_a_slow_meter_is_priced_as_a_back_bill(shop: Shop) -> None:
    bench(shop, "TR-1", "84-119302", "96.00")
    found = report.gather(shop, on="2025-07-15")
    assert len(found.back_bills) == 1
    assert found.net().cents < 0


def test_refunds_and_back_bills_net_off(shop: Shop) -> None:
    second_point(shop)
    bench(shop, "TR-1", "84-119302", "103.00")
    bench(shop, "TR-2", "84-119303", "97.00")
    found = report.gather(shop, on="2025-07-15")
    assert len(found.priced) == 2
    assert found.net() == found.owed_to_customers() - found.owed_to_utility()
    assert "2 priced" in found.show()


def test_a_meter_that_was_never_tested_is_passed_over(shop: Shop) -> None:
    found = report.gather(shop, on="2025-07-15")
    assert "no usable as found run" in found.passed_over[0][1]


def test_a_point_with_no_billed_history_is_passed_over(shop: Shop) -> None:
    second_point(shop, "SP-1044", "84-119304")
    for month in shop.billing.for_point("SP-1044"):
        shop.billing.delete("SP-1044", month.span.start)
    bench(shop, "TR-1", "84-119304", "103.00")
    found = report.gather(shop, on="2025-07-15")
    assert any("no billed history" in why for _, why in found.passed_over)


def test_the_money_grid(shop: Shop) -> None:
    bench(shop, "TR-1", "84-119302", "103.00")
    grid = report.money_grid(report.gather(shop, on="2025-07-15"))
    row = grid.dicts()[0]
    assert row["point"] == "SP-1042"
    assert row["direction"] == "refund"
    assert row["billed"] == "$600.00"


def test_the_passed_over_grid(shop: Shop) -> None:
    grid = report.passed_over_grid(report.gather(shop, on="2025-07-15"))
    assert grid.headings == ("point", "why")
    assert grid.dicts()[0]["point"] == "SP-1042"


def test_the_report_has_all_three_sections(shop: Shop) -> None:
    bench(shop, "TR-1", "84-119302", "103.00")
    doc = report.build(shop, on="2025-07-15")
    assert [s.title for s in doc.sections] == ["Priced", "Passed over", "Tariff"]
    facts = dict(doc.sections[0].facts)
    assert facts["refunds"] == "1"
    assert facts["owed to the utility"] == str(Money.zero())


def test_the_tariff_section_states_the_rules(shop: Shop) -> None:
    facts = dict(report.build(shop, on="2025-07-15").sections[2].facts)
    assert facts["refund lookback"] == "60 months"
    assert facts["back bill lookback"] == "12 months"


def test_the_report_renders(shop: Shop) -> None:
    bench(shop, "TR-1", "84-119302", "103.00")
    doc = report.build(shop, on="2025-07-15")
    assert "Adjustment register as at 2025-07-15" in doc.render()
    assert doc.as_csv().startswith("point,meter,direction")
