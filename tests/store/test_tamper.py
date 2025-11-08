from __future__ import annotations

from collections.abc import Iterator
from datetime import date
from pathlib import Path

import pytest

from kilodial.errors import ConfigError, DuplicateError, NotFoundError, RuleError
from kilodial.install.point import ServicePoint
from kilodial.model.form import Service
from kilodial.store.book import Book, open_migrated
from kilodial.store.installs import ServicePointRepository
from kilodial.store.tamper import TamperRepository
from kilodial.tamper.event import Finding, Standing, TamperKind


@pytest.fixture
def repo(tmp_path: Path) -> Iterator[TamperRepository]:
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
    yield TamperRepository(book.connection)
    book.close()


def finding(reference: str = "TF-1", kind: object = "seal cut", **over: object) -> Finding:
    args: dict[str, object] = {"found_on": "2025-06-30", "found_by": "R Ellis"}
    args.update(over)
    return Finding.raise_finding(reference, str(args.pop("point_code", "SP-1042")), kind, **args)


def test_findings_round_trip(repo: TamperRepository) -> None:
    added = repo.add(finding(evidence="seal wire hanging"))
    assert repo.get("tf-1") == added
    assert repo.count() == 1
    with pytest.raises(DuplicateError, match="tamper finding"):
        repo.add(finding())


def test_a_point_nobody_has(repo: TamperRepository) -> None:
    with pytest.raises(RuleError, match="SP-9999 is not on the book"):
        repo.add(finding(point_code="SP-9999"))


def test_a_finding_that_is_not_there(repo: TamperRepository) -> None:
    with pytest.raises(NotFoundError, match="tamper finding"):
        repo.get("TF-1")
    assert repo.find("TF-1") is None
    assert repo.find(None) is None
    with pytest.raises(NotFoundError):
        repo.save(finding())


def test_confirming_survives_a_round_trip(repo: TamperRepository) -> None:
    repo.add(finding("TF-1", "bypass"))
    repo.save(repo.get("TF-1").confirmed(on="2025-07-04", since="2024-01-01", evidence="jumper"))
    got = repo.get("TF-1")
    assert got.standing is Standing.CONFIRMED
    assert got.since == date(2024, 1, 1)
    assert got.kind is TamperKind.BYPASS


def test_the_open_list_leaves_out_the_settled(repo: TamperRepository) -> None:
    repo.add(finding("TF-1"))
    repo.add(finding("TF-2", found_on="2025-07-01"))
    repo.save(repo.get("TF-2").cleared(on="2025-07-04", why="tree crew"))
    assert [f.reference for f in repo.open_ones()] == ["TF-1"]


def test_only_confirmed_findings_are_returned(repo: TamperRepository) -> None:
    repo.add(finding("TF-1"))
    repo.add(finding("TF-2", "bypass"))
    repo.save(repo.get("TF-2").confirmed(on="2025-07-04", since="2024-01-01", evidence="jumper"))
    assert [f.reference for f in repo.confirmed_at("SP-1042", "2025-12-31")] == ["TF-2"]
    assert repo.confirmed_at("SP-1042", "2025-01-01") == []


def test_whether_the_meter_was_measuring(repo: TamperRepository) -> None:
    repo.add(finding("TF-1", "seal cut"))
    repo.save(repo.get("TF-1").confirmed(on="2025-07-04", since="2024-01-01", evidence="cut"))
    assert not repo.unmetered_at("SP-1042", "2025-12-31")
    repo.add(finding("TF-2", "bypass", found_on="2025-07-01"))
    repo.save(repo.get("TF-2").confirmed(on="2025-07-04", since="2023-01-01", evidence="jumper"))
    assert repo.unmetered_at("SP-1042", "2025-12-31")


def test_the_earliest_confirmed_start(repo: TamperRepository) -> None:
    repo.add(finding("TF-1", "bypass"))
    repo.save(repo.get("TF-1").confirmed(on="2025-07-04", since="2024-01-01", evidence="jumper"))
    repo.add(finding("TF-2", "reversed", found_on="2025-07-01"))
    repo.save(repo.get("TF-2").confirmed(on="2025-07-04", since="2023-05-01", evidence="reversed"))
    assert repo.since_at("SP-1042", "2025-12-31") == date(2023, 5, 1)
    assert repo.since_at("SP-1042", "2020-01-01") is None


def test_findings_in_a_window(repo: TamperRepository) -> None:
    repo.add(finding("TF-1", found_on="2025-01-05"))
    repo.add(finding("TF-2", found_on="2025-06-30"))
    assert [f.reference for f in repo.between("2025-05-01", "2025-12-31")] == ["TF-2"]


def test_a_row_holding_a_kind_nobody_finds(repo: TamperRepository) -> None:
    repo.add(finding())
    repo._conn.execute("UPDATE tamper_finding SET kind = 'VANDALISM'")
    with pytest.raises(ConfigError, match="not a tamper finding"):
        repo.get("TF-1")


def test_a_row_holding_a_standing_nobody_uses(repo: TamperRepository) -> None:
    repo.add(finding())
    repo._conn.execute("UPDATE tamper_finding SET standing = 'maybe'")
    with pytest.raises(ConfigError, match="not a tamper standing"):
        repo.get("TF-1")


def test_findings_for_a_point(repo: TamperRepository) -> None:
    repo.add(finding("TF-1"))
    assert [f.reference for f in repo.for_point("sp-1042")] == ["TF-1"]
    assert repo.for_point("SP-9999") == []
