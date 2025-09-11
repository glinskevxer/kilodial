from __future__ import annotations

from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path

import pytest

from kilodial.complaint.service import answer, log
from kilodial.model.meter import Meter
from kilodial.model.run import BenchPoint, BenchRun, RunKind
from kilodial.report import commission as report
from kilodial.sampling.group import Group
from kilodial.store.shop import Shop, open_shop
from kilodial.tools.smoke import stand_up
from kilodial.units.span import DateSpan

YEAR = DateSpan("2025-01-01", "2025-12-31")


@pytest.fixture
def shop(tmp_path: Path) -> Iterator[Shop]:
    opened = open_shop(tmp_path / "shop.sqlite3", create=True)
    stand_up(opened)
    yield opened
    opened.close()


def stock(shop: Shop, serial: str) -> None:
    shop.meters.add(Meter.receive(serial, "Halvern/R4S", acquired="2015-01-01"))


def bench(
    shop: Shop,
    reference: str,
    serial: str,
    pct: str,
    on: str = "2025-03-04",
    kind: RunKind = RunKind.AS_FOUND,
) -> None:
    shop.runs.add(
        BenchRun.build(
            reference,
            meter_serial=serial,
            bench_code="B2",
            standard_serial="RS-5511",
            kind=kind,
            tested_on=on,
            technician="R Ellis",
            points=[
                BenchPoint.build("FL", amperes="30", volts="240", registration=pct),
                BenchPoint.build("LL", amperes="3", volts="240", registration=pct),
            ],
        )
    )


def test_a_group_with_no_tests(shop: Shop) -> None:
    year = report.group_year(shop, "G1", YEAR)
    assert year.population == 1
    assert year.tested == 0
    assert not year.met_the_sample
    assert year.share_tested == Decimal("0.00")


def test_a_group_tested_whole(shop: Shop) -> None:
    bench(shop, "TR-1", "84-119302", "100.10")
    year = report.group_year(shop, "G1", YEAR)
    assert year.tested == 1
    assert year.inside == 1
    assert year.met_the_sample
    assert year.share_tested == Decimal("100.00")


def test_fast_and_slow_are_counted_apart(shop: Shop) -> None:
    stock(shop, "84-119303")
    bench(shop, "TR-1", "84-119302", "104.00")
    bench(shop, "TR-2", "84-119303", "96.00")
    year = report.group_year(shop, "G1", YEAR)
    assert year.fast == 1
    assert year.slow == 1
    assert year.inside == 0


def test_a_meter_benched_twice_counts_once(shop: Shop) -> None:
    bench(shop, "TR-1", "84-119302", "100.10", "2025-03-04")
    bench(shop, "TR-2", "84-119302", "100.20", "2025-06-04")
    assert report.group_year(shop, "G1", YEAR).tested == 1


def test_runs_outside_the_year_are_not_counted(shop: Shop) -> None:
    bench(shop, "TR-1", "84-119302", "100.10", "2024-03-04")
    assert report.group_year(shop, "G1", YEAR).tested == 0


def test_as_left_runs_are_not_counted(shop: Shop) -> None:
    bench(shop, "TR-1", "84-119302", "100.10", kind=RunKind.AS_LEFT)
    assert report.group_year(shop, "G1", YEAR).tested == 0


def test_the_grid_has_a_row_per_group(shop: Shop) -> None:
    shop.groups.add(Group.build("G2", "everything else"))
    grid = report.group_grid(shop, YEAR)
    assert [row["group"] for row in grid.dicts()] == ["G1", "G2"]
    assert grid.headings == tuple(report.HEADINGS)


def test_the_filing_names_the_period(shop: Shop) -> None:
    doc = report.build(shop, first="2025-01-01", last="2025-12-31")
    assert "2025-01-01 to 2025-12-31" in doc.title


def test_a_group_short_of_its_sample_is_a_finding(shop: Shop) -> None:
    for n in range(60):
        stock(shop, f"84-2{n:05d}")
    bench(shop, "TR-1", "84-119302", "100.10")
    doc = report.build(shop, first="2025-01-01", last="2025-12-31")
    groups = doc.sections[0]
    assert dict(groups.facts)["groups short of their sample"] == "1"
    assert "tested 1 of a required 25" in groups.notes[0]


def test_meters_outside_every_group_are_counted(shop: Shop) -> None:
    from kilodial.model.device import DeviceType
    from kilodial.model.form import Technology

    shop.devices.add(
        DeviceType.build(
            "Vantage",
            "SM3",
            form_code="16S",
            class_code="320",
            voltage="277",
            kh="1.0",
            technology=Technology.SOLID_STATE,
            introduced="2018-01-01",
        )
    )
    shop.meters.add(Meter.receive("84-119999", "Vantage/SM3", acquired="2019-01-01"))
    doc = report.build(shop, first="2025-01-01", last="2025-12-31")
    assert dict(doc.sections[1].facts)["meters"] == "1"


def test_the_customer_request_section(shop: Shop) -> None:
    log(shop, "CR-0", "SP-1042", on="2024-01-01", by="M Okafor")
    log(shop, "CR-1", "SP-1042", on="2025-03-04", by="M Okafor")
    bench(shop, "TR-9", "84-119302", "104.00", "2025-03-14", RunKind.REFEREE)
    answer(shop, "CR-1", run_reference="TR-9", on="2025-03-14")
    facts = dict(report.build(shop, first="2025-01-01", last="2025-12-31").sections[2].facts)
    assert facts["requested"] == "1"
    assert facts["answered"] == "1"
    assert facts["meters found outside tolerance"] == "1"


def test_an_open_request_from_the_period_is_reported(shop: Shop) -> None:
    log(shop, "CR-1", "SP-1042", on="2025-03-04", by="M Okafor")
    facts = dict(report.build(shop, first="2025-01-01", last="2025-12-31").sections[2].facts)
    assert facts["still open from the period"] == "1"
    assert facts["answered"] == "0"


def test_the_filing_writes_out_as_csv(shop: Shop) -> None:
    doc = report.build(shop, first="2025-01-01", last="2025-12-31")
    assert doc.as_csv().startswith("group,name,in service")
