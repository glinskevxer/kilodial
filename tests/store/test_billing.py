from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from kilodial.adjust.compute import BilledMonth
from kilodial.errors import DuplicateError, NotFoundError, RuleError
from kilodial.install.point import ServicePoint
from kilodial.model.form import Service
from kilodial.store.billing import BillingRepository
from kilodial.store.book import Book, open_migrated
from kilodial.store.installs import ServicePointRepository
from kilodial.units.money import Money
from kilodial.units.span import DateSpan


@pytest.fixture
def repo(tmp_path: Path) -> Iterator[BillingRepository]:
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
    yield BillingRepository(book.connection)
    book.close()


def month(index: int, amount: str = "100.00") -> BilledMonth:
    last = {1: 31, 2: 28, 3: 31, 4: 30, 5: 31, 6: 30}[index]
    return BilledMonth.of(f"2025-{index:02d}-01", f"2025-{index:02d}-{last}", amount)


def test_billed_months_round_trip(repo: BillingRepository) -> None:
    repo.add("sp-1042", month(1))
    got = repo.get("SP-1042", "2025-01-01")
    assert got.amount == Money("100.00")
    assert got.span.end is not None
    assert repo.count() == 1


def test_a_point_nobody_has(repo: BillingRepository) -> None:
    with pytest.raises(RuleError, match="SP-9999 is not on the book"):
        repo.add("SP-9999", month(1))


def test_an_overlapping_period_is_refused(repo: BillingRepository) -> None:
    repo.add("SP-1042", month(1))
    with pytest.raises(DuplicateError, match="billed month"):
        repo.add("SP-1042", BilledMonth.of("2025-01-15", "2025-02-14", "100.00"))


def test_an_open_ended_billing_period(repo: BillingRepository) -> None:
    with pytest.raises(RuleError, match="have an end"):
        repo.add("SP-1042", BilledMonth(DateSpan("2025-01-01"), Money("100.00")))


def test_months_come_back_in_order(repo: BillingRepository) -> None:
    for index in (3, 1, 2):
        repo.add("SP-1042", month(index))
    assert [m.span.start.month for m in repo.for_point("SP-1042")] == [1, 2, 3]


def test_covering_a_window(repo: BillingRepository) -> None:
    for index in range(1, 5):
        repo.add("SP-1042", month(index))
    found = repo.covering("SP-1042", DateSpan("2025-02-15", "2025-03-15"))
    assert [m.span.start.month for m in found] == [2, 3]


def test_the_total_over_a_window_is_prorated(repo: BillingRepository) -> None:
    repo.add("SP-1042", BilledMonth.of("2025-01-01", "2025-01-31", "310.00"))
    repo.add("SP-1042", month(2))
    assert repo.total_for("SP-1042", DateSpan("2025-01-01", "2025-02-28")) == Money("410.00")
    assert repo.total_for("SP-1042", DateSpan("2025-01-17", "2025-01-31")) == Money("150.00")
    assert repo.total_for("SP-1042", DateSpan("2024-01-01", "2024-12-31")).is_zero


def test_energy_is_kept_alongside_the_money(repo: BillingRepository) -> None:
    repo.add("SP-1042", month(1), kwh="912.4")
    assert repo.kwh_for("SP-1042", "2025-01-01") == "912.4"
    repo.add("SP-1042", month(2))
    assert repo.kwh_for("SP-1042", "2025-02-01") is None


def test_something_that_is_not_there(repo: BillingRepository) -> None:
    with pytest.raises(NotFoundError, match="billed month"):
        repo.get("SP-1042", "2025-01-01")
    with pytest.raises(NotFoundError):
        repo.kwh_for("SP-1042", "2025-01-01")
    with pytest.raises(NotFoundError):
        repo.delete("SP-1042", "2025-01-01")


def test_deleting_a_month(repo: BillingRepository) -> None:
    repo.add("SP-1042", month(1))
    repo.delete("SP-1042", "2025-01-01")
    assert repo.count() == 0


def test_deleting_the_point_takes_the_history(repo: BillingRepository, tmp_path: Path) -> None:
    repo.add("SP-1042", month(1))
    repo._conn.execute("DELETE FROM service_point WHERE code = 'SP-1042'")
    assert repo.count() == 0
