from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from kilodial.errors import NotFoundError, RuleError
from kilodial.model.bench import Bench, ReferenceStandard
from kilodial.model.device import DeviceType
from kilodial.model.form import Technology
from kilodial.model.meter import Meter
from kilodial.model.run import BenchPoint, BenchRun, RunKind
from kilodial.programme.season import gather, run_sample
from kilodial.sampling.group import Group
from kilodial.store.shop import Shop, open_shop
from kilodial.units.span import DateSpan


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
    opened.groups.add(Group.build("G1", "Halvern", device_keys=["Halvern/R4S"]))
    yield opened
    opened.close()


def stock(shop: Shop, serial: str) -> Meter:
    return shop.meters.add(Meter.receive(serial, "Halvern/R4S", acquired="2015-01-01"))


def record(
    shop: Shop,
    reference: str,
    serial: str,
    on: str,
    pct: str = "100.10",
    kind: RunKind = RunKind.AS_FOUND,
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
                BenchPoint.build("FL", amperes="30", volts="240", registration=pct),
                BenchPoint.build("LL", amperes="3", volts="240", registration=pct),
            ],
        )
    )


def season_window() -> DateSpan:
    return DateSpan("2025-01-01", "2025-06-30")


def test_a_season_gathers_one_reading_per_meter(shop: Shop) -> None:
    for n in range(3):
        serial = f"84-11930{n}"
        stock(shop, serial)
        record(shop, f"TR-{n}", serial, "2025-03-04")
    season = gather(shop, "G1", season_window())
    assert season.tested == 3
    assert season.population == 3
    assert season.serials == ("84-119300", "84-119301", "84-119302")


def test_a_meter_benched_twice_votes_once(shop: Shop) -> None:
    stock(shop, "84-119302")
    record(shop, "TR-1", "84-119302", "2025-02-01", "100.10")
    record(shop, "TR-2", "84-119302", "2025-04-01", "101.00")
    season = gather(shop, "G1", season_window())
    assert season.tested == 1
    assert str(season.readings[0]) == "101.00%"


def test_as_left_runs_are_left_out(shop: Shop) -> None:
    stock(shop, "84-119302")
    record(shop, "TR-1", "84-119302", "2025-03-04", kind=RunKind.AS_LEFT)
    assert gather(shop, "G1", season_window()).tested == 0


def test_a_void_run_is_counted_as_skipped(shop: Shop) -> None:
    stock(shop, "84-119302")
    shop.standards.add(
        ReferenceStandard.build(
            "RS-0001",
            maker="Radian",
            model_code="RD-23",
            certificate="OLD",
            certified_on="2010-01-01",
            certificate_due="2011-01-01",
            uncertainty="0.02",
        )
    )
    shop.runs.add(
        BenchRun.build(
            "TR-1",
            meter_serial="84-119302",
            bench_code="B2",
            standard_serial="RS-0001",
            kind=RunKind.AS_FOUND,
            tested_on="2025-03-04",
            technician="R Ellis",
            points=[
                BenchPoint.build("FL", amperes="30", volts="240", registration="100.10"),
                BenchPoint.build("LL", amperes="3", volts="240", registration="99.80"),
            ],
        )
    )
    season = gather(shop, "G1", season_window())
    assert season.tested == 0
    assert season.skipped == (("TR-1", "void"),)
    assert "1 runs left out" in season.show()


def test_runs_outside_the_window_are_not_in_the_season(shop: Shop) -> None:
    stock(shop, "84-119302")
    record(shop, "TR-1", "84-119302", "2024-12-31")
    assert gather(shop, "G1", season_window()).tested == 0


def test_runs_on_meters_outside_the_group_are_not_in_it(shop: Shop) -> None:
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
    stock(shop, "84-119302")
    record(shop, "TR-1", "84-119999", "2025-03-04")
    season = gather(shop, "G1", season_window())
    assert season.population == 1
    assert season.tested == 0


def test_an_empty_group_cannot_be_sampled(shop: Shop) -> None:
    with pytest.raises(RuleError, match="has no meters in it"):
        gather(shop, "G1", season_window())


def test_a_group_nobody_has(shop: Shop) -> None:
    with pytest.raises(NotFoundError, match="sampling group"):
        gather(shop, "G9", season_window())


def test_a_small_group_tested_whole_passes_and_moves_up(shop: Shop) -> None:
    for n in range(5):
        serial = f"84-11930{n}"
        stock(shop, serial)
        record(shop, f"TR-{n}", serial, "2025-03-04", "100.10")
    season, decision = run_sample(shop, "G1", span=season_window(), on="2025-06-30")
    assert season.tested == 5
    assert decision.passed
    assert decision.interval_months == 72
    assert shop.plans.interval("G1") == 72


def test_a_scattered_group_moves_down(shop: Shop) -> None:
    for n in range(6):
        serial = f"84-11930{n}"
        stock(shop, serial)
        record(shop, f"TR-{n}", serial, "2025-03-04", "98.5" if n % 2 else "101.5")
    _, first = run_sample(shop, "G1", span=season_window(), on="2025-06-30")
    assert not first.passed
    assert first.is_mass_test


def test_a_second_season_starts_from_the_new_interval(shop: Shop) -> None:
    for n in range(5):
        serial = f"84-11930{n}"
        stock(shop, serial)
        record(shop, f"TR-{n}", serial, "2025-03-04", "100.10")
    run_sample(shop, "G1", span=season_window(), on="2025-06-30")
    for n in range(5):
        record(shop, f"TR-2-{n}", f"84-11930{n}", "2031-03-04", "100.10")
    _, second = run_sample(shop, "G1", span=DateSpan("2031-01-01", "2031-06-30"), on="2031-06-30")
    assert second.previous_months == 72
    assert second.interval_months == 96
