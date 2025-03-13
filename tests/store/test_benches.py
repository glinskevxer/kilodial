from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from kilodial.errors import DuplicateError, NotFoundError, RuleError
from kilodial.model.bench import Bench, ReferenceStandard
from kilodial.store.benches import BenchRepository, StandardRepository
from kilodial.store.book import Book, open_migrated


@pytest.fixture
def book(tmp_path: Path) -> Iterator[Book]:
    opened = open_migrated(tmp_path / "shop.sqlite3", create=True)
    yield opened
    opened.close()


@pytest.fixture
def standards(book: Book) -> StandardRepository:
    return StandardRepository(book.connection)


@pytest.fixture
def benches(book: Book) -> BenchRepository:
    return BenchRepository(book.connection)


def standard(serial: str = "RS-5511", **over: object) -> ReferenceStandard:
    args: dict[str, object] = {
        "maker": "Radian",
        "model_code": "RD-23",
        "certificate": "NVLAP-88214",
        "certified_on": "2024-11-04",
        "certificate_due": "2025-11-04",
        "uncertainty": "0.02",
    }
    args.update(over)
    return ReferenceStandard.build(serial, **args)


def bench(code: str = "B2", **over: object) -> Bench:
    args: dict[str, object] = {
        "positions": 8,
        "standard_serial": "RS-5511",
        "max_amperes": "100",
        "max_volts": "480",
        "polyphase": True,
        "installed": "2018-03-01",
    }
    args.update(over)
    return Bench.build(code, "north wall", **args)  # type: ignore[arg-type]


def test_standards_round_trip(standards: StandardRepository) -> None:
    added = standards.add(standard())
    assert standards.get("rs-5511") == added
    assert standards.count() == 1


def test_a_standard_added_twice(standards: StandardRepository) -> None:
    standards.add(standard())
    with pytest.raises(DuplicateError, match="reference standard"):
        standards.add(standard())


def test_a_standard_that_is_not_there(standards: StandardRepository) -> None:
    with pytest.raises(NotFoundError, match="reference standard"):
        standards.get("RS-5511")
    with pytest.raises(NotFoundError):
        standards.save(standard())


def test_recertifying_a_standard(standards: StandardRepository) -> None:
    standards.add(standard())
    standards.save(standard(certified_on="2025-11-01", certificate_due="2026-11-01"))
    assert standards.get("RS-5511").certificate_due.isoformat() == "2026-11-01"


def test_which_standards_were_valid_on_a_day(standards: StandardRepository) -> None:
    standards.add(standard("RS-5511"))
    standards.add(standard("RS-7002", certified_on="2025-06-01", certificate_due="2026-06-01"))
    assert [s.serial for s in standards.valid_on("2025-03-04")] == ["RS-5511"]
    assert [s.serial for s in standards.valid_on("2025-08-01")] == ["RS-5511", "RS-7002"]
    assert standards.valid_on("2027-01-01") == []


def test_standards_coming_due(standards: StandardRepository) -> None:
    standards.add(standard("RS-5511"))
    standards.add(standard("RS-7002", certified_on="2025-06-01", certificate_due="2026-06-01"))
    assert [s.serial for s in standards.due_within("2025-10-20", 30)] == ["RS-5511"]
    assert standards.due_within("2025-01-01", 30) == []
    with pytest.raises(RuleError, match="cannot look backwards"):
        standards.due_within("2025-01-01", -1)


def test_expired_standards(standards: StandardRepository) -> None:
    standards.add(standard("RS-5511"))
    assert standards.expired_on("2025-11-04") == []
    assert [s.serial for s in standards.expired_on("2025-11-05")] == ["RS-5511"]


def test_a_bench_needs_a_standard_on_the_book(benches: BenchRepository) -> None:
    with pytest.raises(RuleError, match="not on the book"):
        benches.add(bench())


def test_benches_round_trip(standards: StandardRepository, benches: BenchRepository) -> None:
    standards.add(standard())
    added = benches.add(bench())
    assert benches.get("b2") == added
    assert benches.count() == 1
    with pytest.raises(DuplicateError, match="bench"):
        benches.add(bench())


def test_a_bench_that_is_not_there(benches: BenchRepository) -> None:
    with pytest.raises(NotFoundError, match="bench"):
        benches.get("B2")
    with pytest.raises(NotFoundError):
        benches.save(bench())


def test_moving_a_standard_onto_another_bench(
    standards: StandardRepository, benches: BenchRepository
) -> None:
    standards.add(standard("RS-5511"))
    standards.add(standard("RS-7002"))
    benches.add(bench("B2"))
    assert benches.standard_for("B2").serial == "RS-5511"
    benches.save(bench("B2", standard_serial="RS-7002"))
    assert benches.standard_for("B2").serial == "RS-7002"
    assert [b.code for b in benches.using("RS-7002")] == ["B2"]
    assert benches.using("RS-5511") == []


def test_benches_available_on_a_day(
    standards: StandardRepository, benches: BenchRepository
) -> None:
    standards.add(standard())
    benches.add(bench("B1", removed="2020-12-31"))
    benches.add(bench("B2"))
    assert [b.code for b in benches.available_on("2025-01-01")] == ["B2"]
    assert [b.code for b in benches.available_on("2019-01-01")] == ["B1", "B2"]


def test_all_benches_come_back_sorted(
    standards: StandardRepository, benches: BenchRepository
) -> None:
    standards.add(standard())
    for code in ("B7", "B1", "B4"):
        benches.add(bench(code))
    assert [b.code for b in benches.all()] == ["B1", "B4", "B7"]
