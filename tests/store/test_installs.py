from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from kilodial.errors import DuplicateError, NotFoundError, RuleError
from kilodial.install.point import MeterSet, ServicePoint
from kilodial.model.form import Service
from kilodial.store.book import Book, open_migrated
from kilodial.store.installs import InstallRepository, ServicePointRepository
from kilodial.units.span import DateSpan


@pytest.fixture
def book(tmp_path: Path) -> Iterator[Book]:
    opened = open_migrated(tmp_path / "shop.sqlite3", create=True)
    yield opened
    opened.close()


@pytest.fixture
def points(book: Book) -> ServicePointRepository:
    return ServicePointRepository(book.connection)


@pytest.fixture
def installs(book: Book, points: ServicePointRepository) -> InstallRepository:
    points.add(point())
    return InstallRepository(book.connection)


def point(code: str = "SP-1042", **over: object) -> ServicePoint:
    args: dict[str, object] = {
        "account": "44-9021",
        "address": "18 Fenwick Row",
        "service": Service.SINGLE_PHASE_3W,
        "voltage": "240",
        "rate_code": "R1",
        "energised": "2011-06-14",
    }
    args.update(over)
    return ServicePoint.build(code, **args)  # type: ignore[arg-type]


def a_set(serial: str = "84-119302", **over: object) -> MeterSet:
    args: dict[str, object] = {"programmed_multiplier": "1", "set_on": "2019-05-02"}
    args.update(over)
    return MeterSet.build(str(args.pop("point_code", "SP-1042")), serial, **args)


def test_service_points_round_trip(points: ServicePointRepository) -> None:
    added = points.add(point())
    assert points.get("sp-1042") == added
    assert points.count() == 1
    with pytest.raises(DuplicateError, match="service point"):
        points.add(point())


def test_a_point_that_is_not_there(points: ServicePointRepository) -> None:
    with pytest.raises(NotFoundError, match="service point"):
        points.get("SP-1042")
    with pytest.raises(NotFoundError):
        points.save(point())


def test_disconnecting_a_point(points: ServicePointRepository) -> None:
    points.add(point())
    points.save(point(disconnected="2024-02-01"))
    assert [p.code for p in points.live_on("2024-06-01")] == []
    assert [p.code for p in points.live_on("2023-06-01")] == ["SP-1042"]


def test_points_by_account(points: ServicePointRepository) -> None:
    points.add(point("SP-1042", account="44-9021"))
    points.add(point("SP-1043", account="44-9022"))
    assert [p.code for p in points.by_account("44-9022")] == ["SP-1043"]
    assert points.by_account("44-0000") == []


def test_setting_a_meter(installs: InstallRepository) -> None:
    installs.set_meter(a_set())
    standing = installs.current("SP-1042")
    assert standing is not None
    assert standing.meter_serial == "84-119302"
    assert installs.count() == 1


def test_a_set_on_a_point_nobody_has(installs: InstallRepository) -> None:
    with pytest.raises(RuleError, match="SP-9999 is not on the book"):
        installs.set_meter(a_set(point_code="SP-9999"))


def test_two_meters_cannot_stand_at_one_point(installs: InstallRepository) -> None:
    installs.set_meter(a_set("84-119302"))
    with pytest.raises(RuleError, match="already set at SP-1042"):
        installs.set_meter(a_set("84-119303", set_on="2021-01-01"))


def test_one_meter_cannot_stand_at_two_points(
    installs: InstallRepository, points: ServicePointRepository
) -> None:
    points.add(point("SP-1043"))
    installs.set_meter(a_set("84-119302"))
    with pytest.raises(RuleError, match="already set at SP-1042"):
        installs.set_meter(a_set("84-119302", point_code="SP-1043", set_on="2021-01-01"))


def test_a_replacement_after_the_first_was_pulled(installs: InstallRepository) -> None:
    installs.set_meter(a_set("84-119302"))
    installs.pull("SP-1042", "2023-08-14")
    installs.set_meter(a_set("84-119303", set_on="2023-08-15"))
    standing = installs.current("SP-1042")
    assert standing is not None
    assert standing.meter_serial == "84-119303"
    assert [s.meter_serial for s in installs.history("SP-1042")] == [
        "84-119302",
        "84-119303",
    ]


def test_a_replacement_set_the_same_day_still_overlaps(installs: InstallRepository) -> None:
    installs.set_meter(a_set("84-119302"))
    installs.pull("SP-1042", "2023-08-14")
    with pytest.raises(RuleError, match="already set at"):
        installs.set_meter(a_set("84-119303", set_on="2023-08-14"))


def test_pulling_nothing(installs: InstallRepository) -> None:
    with pytest.raises(RuleError, match="nothing is set at SP-1042"):
        installs.pull("SP-1042", "2023-08-14")


def test_what_was_standing_on_a_day(installs: InstallRepository) -> None:
    installs.set_meter(a_set("84-119302"))
    installs.pull("SP-1042", "2023-08-14")
    installs.set_meter(a_set("84-119303", set_on="2023-08-15"))
    first = installs.on_day("SP-1042", "2020-01-01")
    assert first is not None
    assert first.meter_serial == "84-119302"
    second = installs.on_day("SP-1042", "2024-01-01")
    assert second is not None
    assert second.meter_serial == "84-119303"
    assert installs.on_day("SP-1042", "2015-01-01") is None


def test_history_for_one_meter(installs: InstallRepository) -> None:
    installs.set_meter(a_set("84-119302"))
    assert [s.point_code for s in installs.for_meter("84-119302")] == ["SP-1042"]
    assert installs.for_meter("84-000000") == []
    assert installs.current_for_meter("84-000000") is None


def test_sets_using_a_transformer(installs: InstallRepository) -> None:
    installs.set_meter(a_set("84-119302", ct_serial="CT-8841", programmed_multiplier="40"))
    assert [s.meter_serial for s in installs.using_transformer("ct-8841")] == ["84-119302"]
    assert installs.using_transformer("CT-0000") == []


def test_sets_covering_a_period(installs: InstallRepository) -> None:
    installs.set_meter(a_set("84-119302"))
    installs.pull("SP-1042", "2023-08-14")
    installs.set_meter(a_set("84-119303", set_on="2023-08-15"))
    covering = installs.covering("SP-1042", DateSpan("2023-01-01", "2023-12-31"))
    assert [s.meter_serial for s in covering] == ["84-119302", "84-119303"]
    older = installs.covering("SP-1042", DateSpan("2020-01-01", "2020-12-31"))
    assert [s.meter_serial for s in older] == ["84-119302"]
