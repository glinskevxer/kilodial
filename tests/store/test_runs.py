from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from kilodial.errors import DuplicateError, NotFoundError, RuleError
from kilodial.model.bench import Bench, ReferenceStandard
from kilodial.model.device import DeviceType
from kilodial.model.form import Technology
from kilodial.model.meter import Meter
from kilodial.model.run import BenchPoint, BenchRun, PointKind, RunKind
from kilodial.store.benches import BenchRepository, StandardRepository
from kilodial.store.book import Book, open_migrated
from kilodial.store.devices import DeviceRepository
from kilodial.store.meters import MeterRepository
from kilodial.store.runs import RunRepository


@pytest.fixture
def book(tmp_path: Path) -> Iterator[Book]:
    opened = open_migrated(tmp_path / "shop.sqlite3", create=True)
    DeviceRepository(opened.connection).add(
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
    MeterRepository(opened.connection).add(
        Meter.receive("84-119302", "Halvern/R4S", acquired="2019-04-02")
    )
    StandardRepository(opened.connection).add(
        ReferenceStandard.build(
            "RS-5511",
            maker="Radian",
            model_code="RD-23",
            certificate="NVLAP-88214",
            certified_on="2024-11-04",
            certificate_due="2025-11-04",
            uncertainty="0.02",
        )
    )
    BenchRepository(opened.connection).add(
        Bench.build(
            "B2",
            "north wall",
            positions=8,
            standard_serial="RS-5511",
            max_amperes="100",
            max_volts="480",
            polyphase=True,
            installed="2018-03-01",
        )
    )
    yield opened
    opened.close()


@pytest.fixture
def repo(book: Book) -> RunRepository:
    return RunRepository(book.connection)


def run(reference: str = "TR-1", **over: object) -> BenchRun:
    args: dict[str, object] = {
        "meter_serial": "84-119302",
        "bench_code": "B2",
        "standard_serial": "RS-5511",
        "kind": RunKind.AS_FOUND,
        "tested_on": "2025-03-04",
        "technician": "R Ellis",
        "points": [
            BenchPoint.build("FL", amperes="30", volts="240", registration="100.12"),
            BenchPoint.build("LL", amperes="3", volts="240", registration="99.60"),
            BenchPoint.build("CR", amperes="0", volts="264", crept=False),
        ],
    }
    args.update(over)
    return BenchRun.build(reference, **args)  # type: ignore[arg-type]


def test_a_run_round_trips_with_its_points(repo: RunRepository) -> None:
    repo.add(run())
    got = repo.get("tr-1")
    assert got == run()
    assert [p.kind for p in got.points] == [
        PointKind.FULL_LOAD,
        PointKind.LIGHT_LOAD,
        PointKind.CREEP,
    ]
    assert repo.count() == 1


def test_point_order_survives(repo: RunRepository) -> None:
    reordered = run(
        points=[
            BenchPoint.build("LL", amperes="3", volts="240", registration="99.60"),
            BenchPoint.build("FL", amperes="30", volts="240", registration="100.12"),
        ]
    )
    repo.add(reordered)
    assert [p.kind for p in repo.get("TR-1").points] == [
        PointKind.LIGHT_LOAD,
        PointKind.FULL_LOAD,
    ]


def test_the_same_reference_twice(repo: RunRepository) -> None:
    repo.add(run())
    with pytest.raises(DuplicateError, match="bench run"):
        repo.add(run())


def test_a_run_naming_things_that_are_not_on_the_book(repo: RunRepository) -> None:
    with pytest.raises(RuleError, match="meter 84-000000"):
        repo.add(run(meter_serial="84-000000"))
    with pytest.raises(RuleError, match="bench B9"):
        repo.add(run(bench_code="B9"))
    with pytest.raises(RuleError, match="reference standard RS-0000"):
        repo.add(run(standard_serial="RS-0000"))


def test_the_reference_check_can_be_skipped(repo: RunRepository) -> None:
    repo.add(run(meter_serial="84-000000"), check_references=False)
    assert repo.get("TR-1").meter_serial == "84-000000"


def test_nothing_is_left_behind_when_a_write_fails(repo: RunRepository, book: Book) -> None:
    repo.add(run())
    before = book.connection.execute("SELECT COUNT(*) FROM bench_point").fetchone()[0]
    with pytest.raises(DuplicateError):
        repo.add(run())
    after = book.connection.execute("SELECT COUNT(*) FROM bench_point").fetchone()[0]
    assert before == after == 3


def test_a_run_that_is_not_there(repo: RunRepository) -> None:
    with pytest.raises(NotFoundError, match="bench run"):
        repo.get("TR-1")
    assert repo.find("TR-1") is None


def test_runs_for_one_meter_come_back_oldest_first(repo: RunRepository) -> None:
    repo.add(run("TR-3", tested_on="2025-05-01"))
    repo.add(run("TR-1", tested_on="2025-01-01"))
    repo.add(run("TR-2", tested_on="2025-03-01"))
    assert [r.reference for r in repo.for_meter("84-119302")] == ["TR-1", "TR-2", "TR-3"]


def test_the_latest_run_and_the_latest_of_a_kind(repo: RunRepository) -> None:
    repo.add(run("TR-1", tested_on="2025-01-01", kind=RunKind.AS_FOUND))
    repo.add(run("TR-2", tested_on="2025-03-01", kind=RunKind.AS_LEFT))
    latest = repo.latest_for("84-119302")
    assert latest is not None
    assert latest.reference == "TR-2"
    found = repo.latest_for("84-119302", RunKind.AS_FOUND)
    assert found is not None
    assert found.reference == "TR-1"
    assert repo.latest_for("84-000000") is None
    assert repo.latest_for("84-119302", RunKind.REFEREE) is None


def test_windows_and_days(repo: RunRepository) -> None:
    repo.add(run("TR-1", tested_on="2025-01-01"))
    repo.add(run("TR-2", tested_on="2025-03-01"))
    repo.add(run("TR-3", tested_on="2025-05-01"))
    assert [r.reference for r in repo.on_day("2025-03-01")] == ["TR-2"]
    assert [r.reference for r in repo.between("2025-02-01", "2025-06-01")] == ["TR-2", "TR-3"]
    assert repo.on_day("2025-02-02") == []
    with pytest.raises(RuleError, match="cannot end before"):
        repo.between("2025-06-01", "2025-01-01")


def test_filtering_by_kind_and_bench(repo: RunRepository) -> None:
    repo.add(run("TR-1", kind=RunKind.AS_FOUND))
    repo.add(run("TR-2", kind=RunKind.AS_LEFT, tested_on="2025-03-05"))
    assert [r.reference for r in repo.by_kind(RunKind.AS_LEFT)] == ["TR-2"]
    assert [r.reference for r in repo.on_bench("b2")] == ["TR-1", "TR-2"]
    assert repo.on_bench("B9") == []


def test_deleting_a_run_takes_its_points(repo: RunRepository, book: Book) -> None:
    repo.add(run())
    repo.delete("TR-1")
    assert repo.count() == 0
    assert book.connection.execute("SELECT COUNT(*) FROM bench_point").fetchone()[0] == 0
    with pytest.raises(NotFoundError):
        repo.delete("TR-1")


def test_the_measured_demand_interval_round_trips(repo: RunRepository) -> None:
    demand = BenchPoint.build("DM", amperes="30", volts="240", registration="100.10")
    repo.add(
        run(
            "TR-1",
            points=[
                BenchPoint.build("FL", amperes="30", volts="240", registration="100.12"),
                demand,
            ],
            demand_seconds="900",
        )
    )
    assert repo.get("TR-1").demand_seconds is not None
    assert str(repo.get("TR-1").demand_seconds) == "900"


def test_a_run_with_no_demand_interval_reads_back_as_none(repo: RunRepository) -> None:
    repo.add(run())
    assert repo.get("TR-1").demand_seconds is None
