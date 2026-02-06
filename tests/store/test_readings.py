from __future__ import annotations

from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path

import pytest

from kilodial.errors import ConfigError, DuplicateError, NotFoundError, RuleError
from kilodial.install.point import ServicePoint
from kilodial.model.form import Service
from kilodial.model.reading import Reading, ReadingKind
from kilodial.store.book import Book, open_migrated
from kilodial.store.installs import ServicePointRepository
from kilodial.store.readings import ReadingRepository
from kilodial.units.span import DateSpan


@pytest.fixture
def repo(tmp_path: Path) -> Iterator[ReadingRepository]:
    book: Book = open_migrated(tmp_path / "shop.sqlite3", create=True)
    ServicePointRepository(book.connection).add(
        ServicePoint.build(
            "SP-1042",
            account="44-9021",
            address="18 Fenwick Row",
            service=Service.SINGLE_PHASE_3W,
            voltage="240",
            rate_code="R1",
            energised="2011-06-14",
        )
    )
    yield ReadingRepository(book.connection)
    book.close()


def reading(value: int, on: str, **over: object) -> Reading:
    args: dict[str, object] = {"dials": 5, "value": value, "read_on": on}
    args.update(over)
    return Reading.build(
        str(args.pop("point_code", "SP-1042")),
        str(args.pop("meter_serial", "84-119302")),
        **args,
    )


def test_readings_round_trip(repo: ReadingRepository) -> None:
    added = repo.add(reading(41_200, "2025-01-01", note="under the porch"))
    assert repo.get("sp-1042", "84-119302", "2025-01-01") == added
    assert repo.count() == 1


def test_the_same_meter_read_twice_on_one_day(repo: ReadingRepository) -> None:
    repo.add(reading(41_200, "2025-01-01"))
    with pytest.raises(DuplicateError, match="reading"):
        repo.add(reading(41_210, "2025-01-01"))


def test_a_point_nobody_has(repo: ReadingRepository) -> None:
    with pytest.raises(RuleError, match="SP-9999 is not on the book"):
        repo.add(reading(100, "2025-01-01", point_code="SP-9999"))


def test_a_reading_that_is_not_there(repo: ReadingRepository) -> None:
    with pytest.raises(NotFoundError, match="reading"):
        repo.get("SP-1042", "84-119302", "2025-01-01")
    assert not repo.exists("SP-1042", "84-119302", "2025-01-01")


def test_readings_come_back_in_date_order(repo: ReadingRepository) -> None:
    repo.add(reading(41_480, "2025-02-01"))
    repo.add(reading(41_200, "2025-01-01"))
    assert [r.value for r in repo.for_point("SP-1042")] == [41_200, 41_480]
    assert [r.value for r in repo.for_meter("84-119302")] == [41_200, 41_480]


def test_the_latest_reading(repo: ReadingRepository) -> None:
    assert repo.latest("SP-1042") is None
    repo.add(reading(41_200, "2025-01-01"))
    repo.add(reading(41_480, "2025-02-01"))
    latest = repo.latest("SP-1042")
    assert latest is not None
    assert latest.value == 41_480


def test_readings_covering_a_window(repo: ReadingRepository) -> None:
    for month, value in ((1, 41_200), (2, 41_480), (3, 41_760)):
        repo.add(reading(value, f"2025-{month:02d}-01"))
    found = repo.covering("SP-1042", DateSpan("2025-01-15", "2025-03-31"))
    assert [r.value for r in found] == [41_480, 41_760]


def test_consumption_over_a_window(repo: ReadingRepository) -> None:
    repo.add(reading(41_200, "2025-01-01"))
    repo.add(reading(41_480, "2025-02-01"))
    found = repo.consumption_over("SP-1042", DateSpan("2025-01-01", "2025-02-01"))
    assert found.units == 280
    assert found.billed_units == Decimal("280.000")


def test_consumption_with_a_multiplier(repo: ReadingRepository) -> None:
    repo.add(reading(41_200, "2025-01-01"))
    repo.add(reading(41_480, "2025-02-01"))
    found = repo.consumption_over("SP-1042", DateSpan("2025-01-01", "2025-02-01"), multiplier="40")
    assert found.billed_units == Decimal("11200.000")


def test_a_window_with_one_reading_in_it(repo: ReadingRepository) -> None:
    repo.add(reading(41_200, "2025-01-01"))
    with pytest.raises(RuleError, match="has 1 readings"):
        repo.consumption_over("SP-1042", DateSpan("2025-01-01", "2025-02-01"))


def test_a_window_that_spans_a_meter_change(repo: ReadingRepository) -> None:
    repo.add(reading(41_900, "2025-02-01", kind=ReadingKind.FINAL))
    repo.add(reading(0, "2025-02-02", meter_serial="84-119303", kind=ReadingKind.INITIAL))
    with pytest.raises(RuleError, match="changed meter between"):
        repo.consumption_over("SP-1042", DateSpan("2025-01-01", "2025-03-01"))


def test_a_row_holding_a_kind_nobody_reads(repo: ReadingRepository) -> None:
    repo.add(reading(41_200, "2025-01-01"))
    repo._conn.execute("UPDATE reading SET kind = 'guessed'")
    with pytest.raises(ConfigError, match="not a reading kind"):
        repo.get("SP-1042", "84-119302", "2025-01-01")


def test_deleting_the_point_takes_the_readings(repo: ReadingRepository) -> None:
    repo.add(reading(41_200, "2025-01-01"))
    repo._conn.execute("DELETE FROM service_point WHERE code = 'SP-1042'")
    assert repo.count() == 0
