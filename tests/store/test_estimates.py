from __future__ import annotations

from collections.abc import Iterator
from datetime import date
from pathlib import Path

import pytest

from kilodial.errors import ConfigError, DuplicateError, NotFoundError, RuleError
from kilodial.estimate.basis import Basis, declared
from kilodial.install.point import ServicePoint
from kilodial.model.form import Service
from kilodial.store.book import Book, open_migrated
from kilodial.store.estimates import EstimateRepository
from kilodial.store.installs import ServicePointRepository
from kilodial.units.money import Money
from kilodial.units.span import DateSpan

GAP = DateSpan("2025-03-01", "2025-05-31")


@pytest.fixture
def repo(tmp_path: Path) -> Iterator[EstimateRepository]:
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
    yield EstimateRepository(book.connection)
    book.close()


def test_settling_an_estimate(repo: EstimateRepository) -> None:
    settled = repo.settle(
        "es-1",
        declared("SP-1042", GAP, "412.50", note="agreed at the hearing"),
        on="2025-06-30",
        by="  M  Okafor ",
    )
    assert settled.reference == "ES-1"
    assert settled.settled_by == "M Okafor"
    assert settled.settled_on == date(2025, 6, 30)
    assert repo.get("es-1") == settled
    assert repo.count() == 1


def test_the_same_reference_twice(repo: EstimateRepository) -> None:
    estimate = declared("SP-1042", GAP, "412.50")
    repo.settle("ES-1", estimate, on="2025-06-30", by="M Okafor")
    with pytest.raises(DuplicateError, match="estimate"):
        repo.settle("ES-1", estimate, on="2025-06-30", by="M Okafor")


def test_a_point_nobody_has(repo: EstimateRepository) -> None:
    with pytest.raises(RuleError, match="SP-9999 is not on the book"):
        repo.settle("ES-1", declared("SP-9999", GAP, "1.00"), on="2025-06-30", by="M")


def test_an_open_ended_estimate(repo: EstimateRepository) -> None:
    open_gap = declared("SP-1042", DateSpan("2025-03-01"), "412.50")
    with pytest.raises(RuleError, match="a period with an end"):
        repo.settle("ES-1", open_gap, on="2025-06-30", by="M Okafor")


def test_an_estimate_that_is_not_there(repo: EstimateRepository) -> None:
    with pytest.raises(NotFoundError, match="estimate"):
        repo.get("ES-1")
    assert not repo.exists("ES-1")


def test_everything_survives_a_round_trip(repo: EstimateRepository) -> None:
    original = declared("SP-1042", GAP, "412.50", note="agreed at the hearing")
    repo.settle("ES-1", original, on="2025-06-30", by="M Okafor")
    got = repo.get("ES-1").estimate
    assert got.basis is Basis.DECLARED
    assert got.amount == Money("412.50")
    assert got.working == "agreed rather than calculated"
    assert got.note == "agreed at the hearing"
    assert got.span.days == GAP.days


def test_estimates_for_a_point(repo: EstimateRepository) -> None:
    repo.settle("ES-2", declared("SP-1042", GAP, "100.00"), on="2025-06-30", by="M")
    repo.settle(
        "ES-1",
        declared("SP-1042", DateSpan("2025-01-01", "2025-01-31"), "50.00"),
        on="2025-06-30",
        by="M",
    )
    assert [s.reference for s in repo.for_point("sp-1042")] == ["ES-1", "ES-2"]
    assert repo.total_for("SP-1042") == Money("150.00")
    assert repo.total_for("SP-9999").is_zero


def test_estimates_covering_a_window(repo: EstimateRepository) -> None:
    repo.settle("ES-1", declared("SP-1042", GAP, "100.00"), on="2025-06-30", by="M")
    assert repo.covering("SP-1042", DateSpan("2025-04-01", "2025-04-30"))
    assert repo.covering("SP-1042", DateSpan("2024-01-01", "2024-12-31")) == []


def test_a_row_holding_a_basis_nobody_uses(repo: EstimateRepository) -> None:
    repo.settle("ES-1", declared("SP-1042", GAP, "100.00"), on="2025-06-30", by="M")
    repo._conn.execute("UPDATE estimate SET basis = 'GUESSWORK'")
    with pytest.raises(ConfigError, match="not a estimate basis"):
        repo.get("ES-1")


def test_all_comes_back_in_settling_order(repo: EstimateRepository) -> None:
    repo.settle("ES-1", declared("SP-1042", GAP, "100.00"), on="2025-06-30", by="M")
    repo.settle(
        "ES-2",
        declared("SP-1042", DateSpan("2024-01-01", "2024-01-31"), "50.00"),
        on="2025-01-05",
        by="M",
    )
    assert [s.reference for s in repo.all()] == ["ES-2", "ES-1"]


def test_str_names_the_settler(repo: EstimateRepository) -> None:
    settled = repo.settle(
        "ES-1", declared("SP-1042", GAP, "412.50"), on="2025-06-30", by="M Okafor"
    )
    assert "settled by M Okafor" in str(settled)
    assert settled != "ES-1"
