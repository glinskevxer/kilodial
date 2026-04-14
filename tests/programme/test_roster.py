from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from kilodial.model.bench import Bench, ReferenceStandard
from kilodial.model.device import DeviceType
from kilodial.model.form import Technology
from kilodial.model.meter import Meter, MeterState
from kilodial.model.run import BenchPoint, BenchRun, RunKind
from kilodial.programme import roster
from kilodial.programme.roster import UNGROUPED, build, clock_start, group_of
from kilodial.programme.schedule import DueState
from kilodial.sampling.decision import decide
from kilodial.sampling.group import Group
from kilodial.sampling.plan import assess
from kilodial.store.shop import Shop, open_shop
from kilodial.units.registration import Registration


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
            certified_on="2019-01-01",
            certificate_due="2027-01-01",
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


def stock(shop: Shop, serial: str, acquired: str = "2015-01-01") -> Meter:
    return shop.meters.add(Meter.receive(serial, "Halvern/R4S", acquired=acquired))


def record(
    shop: Shop, reference: str, serial: str, on: str, kind: RunKind = RunKind.AS_FOUND
) -> BenchRun:
    return shop.runs.add(
        BenchRun.build(
            reference,
            meter_serial=serial,
            bench_code="B2",
            standard_serial="RS-5511",
            kind=kind,
            tested_on=on,
            technician="R Ellis",
            points=[
                BenchPoint.build("FL", amperes="30", volts="240", registration="100.10"),
                BenchPoint.build("LL", amperes="3", volts="240", registration="99.80"),
            ],
        )
    )


def test_an_ungrouped_meter_is_still_on_the_list(shop: Shop) -> None:
    stock(shop, "84-119302")
    roster = build(shop, on="2025-01-01")
    assert len(roster) == 1
    assert roster.lines[0].group_code == UNGROUPED
    assert roster.lines[0].interval_months == 48
    assert roster.ungrouped()


def test_a_meter_falls_into_its_group(shop: Shop) -> None:
    shop.groups.add(Group.build("G1", "Halvern", device_keys=["Halvern/R4S"]))
    stock(shop, "84-119302")
    assert group_of(shop, shop.meters.get("84-119302")) == "G1"
    assert build(shop, on="2025-01-01").for_group("g1")


def test_the_group_interval_moves_the_due_date(shop: Shop) -> None:
    shop.groups.add(Group.build("G1", "Halvern", device_keys=["Halvern/R4S"]))
    stock(shop, "84-119302")
    record(shop, "TR-1", "84-119302", "2019-06-30")
    assert build(shop, on="2025-01-01").overdue()
    shop.plans.record(
        decide(
            "G1",
            assess([Registration("100.10")] * 30, population=150),
            on="2020-01-01",
            current_months=48,
        )
    )
    shop.plans.record(
        decide(
            "G1",
            assess([Registration("100.10")] * 30, population=150),
            on="2021-01-01",
            current_months=72,
        )
    )
    assert build(shop, on="2025-01-01").counts()[DueState.CURRENT] == 1


def test_the_clock_starts_at_the_last_usable_run(shop: Shop) -> None:
    stock(shop, "84-119302")
    record(shop, "TR-1", "84-119302", "2019-06-30")
    record(shop, "TR-2", "84-119302", "2021-06-30", RunKind.AS_LEFT)
    assert clock_start(shop, "84-119302") == ("2019-06-30", RunKind.AS_FOUND)


def test_a_void_run_does_not_start_the_clock(shop: Shop) -> None:
    stock(shop, "84-119302")
    record(shop, "TR-1", "84-119302", "2028-06-30")
    assert clock_start(shop, "84-119302") is None


def test_a_meter_that_was_never_tested_dates_from_delivery(shop: Shop) -> None:
    stock(shop, "84-119302", acquired="2015-01-01")
    line = build(shop, on="2025-01-01").lines[0]
    assert line.never_tested
    assert line.due.isoformat() == "2019-01-01"
    assert line.state is DueState.OVERDUE


def test_scrapped_meters_leave_the_programme(shop: Shop) -> None:
    stock(shop, "84-119302")
    shop.meters.move("84-119302", MeterState.STOCK)
    shop.meters.move("84-119302", MeterState.SCRAP, on="2024-01-01")
    assert len(build(shop, on="2025-01-01")) == 0


def test_the_list_comes_back_in_due_date_order(shop: Shop) -> None:
    stock(shop, "84-119304", acquired="2020-01-01")
    stock(shop, "84-119302", acquired="2015-01-01")
    stock(shop, "84-119303", acquired="2018-01-01")
    assert [line.serial for line in build(shop, on="2025-01-01").lines] == [
        "84-119302",
        "84-119303",
        "84-119304",
    ]


def test_counts_and_filters(shop: Shop) -> None:
    stock(shop, "84-119302", acquired="2015-01-01")
    stock(shop, "84-119303", acquired="2024-01-01")
    roster = build(shop, on="2025-01-01")
    counts = roster.counts()
    assert counts[DueState.OVERDUE] == 1
    assert counts[DueState.CURRENT] == 1
    assert len(roster.needing_work()) == 1
    assert roster.due() == []


def test_the_grace_period_moves_the_boundary(shop: Shop) -> None:
    stock(shop, "84-119302", acquired="2015-01-01")
    record(shop, "TR-1", "84-119302", "2021-01-01")
    assert build(shop, on="2025-02-01").due()
    assert build(shop, on="2025-02-01", grace_days=0).overdue()


def test_a_group_grace_period_beats_the_rosters(shop: Shop) -> None:
    shop.groups.add(Group.build("G1", "Halvern", device_keys=["Halvern/R4S"], grace_days=0))
    stock(shop, "84-119302")
    record(shop, "TR-1", "84-119302", "2021-01-15")
    assert roster.grace_for(shop, "G1", 90) == 0
    assert build(shop, on="2025-02-01").overdue()
    assert build(shop, on="2025-02-01", grace_days=200).overdue()


def test_a_group_with_no_grace_period_takes_the_rosters(shop: Shop) -> None:
    shop.groups.add(Group.build("G1", "Halvern", device_keys=["Halvern/R4S"]))
    stock(shop, "84-119302")
    record(shop, "TR-1", "84-119302", "2021-01-15")
    assert roster.grace_for(shop, "G1", 90) == 90
    assert build(shop, on="2025-02-01").due()
    assert build(shop, on="2025-02-01", grace_days=0).overdue()


def test_an_ungrouped_meter_takes_the_rosters(shop: Shop) -> None:
    stock(shop, "84-119302")
    assert roster.grace_for(shop, UNGROUPED, 90) == 90
