from __future__ import annotations

from collections.abc import Iterator
from datetime import date
from pathlib import Path

import pytest

from kilodial.complaint.request import Charge, Reason, Request
from kilodial.errors import ConfigError, DuplicateError, NotFoundError, RuleError, StateError
from kilodial.install.point import ServicePoint
from kilodial.model.form import Service
from kilodial.store.book import Book, open_migrated
from kilodial.store.complaints import ComplaintRepository
from kilodial.store.installs import ServicePointRepository
from kilodial.units.money import Money


@pytest.fixture
def repo(tmp_path: Path) -> Iterator[ComplaintRepository]:
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
    yield ComplaintRepository(book.connection)
    book.close()


def request(reference: str = "CR-1", **over: object) -> Request:
    args: dict[str, object] = {
        "requested_on": "2025-03-04",
        "requested_by": "M Okafor",
        "reason": Reason.HIGH_BILL,
    }
    args.update(over)
    return Request.build(reference, str(args.pop("point_code", "SP-1042")), **args)


def test_opening_a_request(repo: ComplaintRepository) -> None:
    opened = repo.open_request(request())
    assert opened.is_open
    assert opened.reference == "CR-1"
    assert repo.count() == 1
    assert [c.reference for c in repo.open_ones()] == ["CR-1"]


def test_a_point_nobody_has(repo: ComplaintRepository) -> None:
    with pytest.raises(RuleError, match="SP-9999 is not on the book"):
        repo.open_request(request(point_code="SP-9999"))


def test_the_same_reference_twice(repo: ComplaintRepository) -> None:
    repo.open_request(request())
    with pytest.raises(DuplicateError, match="complaint request"):
        repo.open_request(request())


def test_a_request_that_is_not_there(repo: ComplaintRepository) -> None:
    with pytest.raises(NotFoundError, match="complaint request"):
        repo.get("CR-1")


def test_closing_a_request(repo: ComplaintRepository) -> None:
    repo.open_request(request())
    closed = repo.close(
        "cr-1",
        run_reference="tr-9",
        charge=Charge.CHARGED,
        fee=Money("28.00"),
        on="2025-03-14",
    )
    assert not closed.is_open
    assert closed.run_reference == "TR-9"
    assert closed.charge is Charge.CHARGED
    assert closed.fee == Money("28.00")
    assert closed.closed_on == date(2025, 3, 14)
    assert repo.open_ones() == []


def test_closing_a_closed_request(repo: ComplaintRepository) -> None:
    repo.open_request(request())
    repo.close(
        "CR-1", run_reference="TR-9", charge=Charge.CHARGED, fee=Money("28.00"), on="2025-03-14"
    )
    with pytest.raises(StateError, match="was closed on"):
        repo.close(
            "CR-1", run_reference="TR-9", charge=Charge.CHARGED, fee=Money("28.00"), on="2025-04-01"
        )


def test_a_waived_fee_is_stored_as_zero(repo: ComplaintRepository) -> None:
    repo.open_request(request())
    closed = repo.close(
        "CR-1",
        run_reference="TR-9",
        charge=Charge.WAIVED_ACCURACY,
        fee=Money.zero(),
        on="2025-03-14",
    )
    assert closed.fee is not None
    assert closed.fee.is_zero
    assert closed.charge is Charge.WAIVED_ACCURACY


def test_requests_for_a_point(repo: ComplaintRepository) -> None:
    repo.open_request(request("CR-2", requested_on="2025-06-01"))
    repo.open_request(request("CR-1", requested_on="2025-03-04"))
    assert [c.reference for c in repo.for_point("sp-1042")] == ["CR-1", "CR-2"]
    assert repo.for_point("SP-9999") == []


def test_when_the_customer_last_asked(repo: ComplaintRepository) -> None:
    repo.open_request(request("CR-1", requested_on="2023-01-05"))
    repo.open_request(request("CR-2", requested_on="2024-06-01"))
    assert repo.previous_for("SP-1042", "2025-03-04") == date(2024, 6, 1)
    assert repo.previous_for("SP-1042", "2023-01-05") is None
    assert repo.previous_for("SP-9999", "2025-03-04") is None


def test_overdue_requests(repo: ComplaintRepository) -> None:
    repo.open_request(request("CR-1", requested_on="2025-03-04"))
    repo.open_request(request("CR-2", requested_on="2025-06-01"))
    assert [c.reference for c in repo.overdue("2025-06-15")] == ["CR-1"]
    assert repo.overdue("2025-03-10") == []


def test_a_closed_request_is_not_overdue(repo: ComplaintRepository) -> None:
    repo.open_request(request("CR-1", requested_on="2025-03-04"))
    repo.close(
        "CR-1", run_reference="TR-9", charge=Charge.CHARGED, fee=Money("28.00"), on="2025-03-14"
    )
    assert repo.overdue("2025-06-15") == []


def test_a_row_holding_a_reason_nobody_files(repo: ComplaintRepository) -> None:
    repo.open_request(request())
    repo._conn.execute("UPDATE complaint_request SET reason = 'angry'")
    with pytest.raises(ConfigError, match="not a complaint reason"):
        repo.get("CR-1")


def test_a_row_holding_a_charge_nobody_makes(repo: ComplaintRepository) -> None:
    repo.open_request(request())
    repo.close(
        "CR-1", run_reference="TR-9", charge=Charge.CHARGED, fee=Money("28.00"), on="2025-03-14"
    )
    repo._conn.execute("UPDATE complaint_request SET charge = 'MAYBE'")
    with pytest.raises(ConfigError, match="not a charge decision"):
        repo.get("CR-1")


def test_str_says_open_or_closed(repo: ComplaintRepository) -> None:
    opened = repo.open_request(request())
    assert str(opened).endswith("open")
    closed = repo.close(
        "CR-1", run_reference="TR-9", charge=Charge.CHARGED, fee=Money("28.00"), on="2025-03-14"
    )
    assert "closed 2025-03-14" in str(closed)
