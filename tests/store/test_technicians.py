from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from kilodial.errors import ConfigError, DuplicateError, NotFoundError, RuleError
from kilodial.model.technician import Grade, Technician
from kilodial.store.book import Book, open_migrated
from kilodial.store.technicians import TechnicianRepository


@pytest.fixture
def repo(tmp_path: Path) -> Iterator[TechnicianRepository]:
    book: Book = open_migrated(tmp_path / "shop.sqlite3", create=True)
    yield TechnicianRepository(book.connection)
    book.close()


def person(badge: str = "T-441", **over: object) -> Technician:
    args: dict[str, object] = {
        "grade": Grade.BENCH,
        "certified_on": "2023-01-01",
        "certificate_due": "2026-01-01",
    }
    args.update(over)
    return Technician.build(badge, str(args.pop("name", "R Ellis")), **args)


def test_technicians_round_trip(repo: TechnicianRepository) -> None:
    added = repo.add(person(note="recert course"))
    assert repo.get("t-441") == added
    assert repo.count() == 1
    with pytest.raises(DuplicateError, match="technician"):
        repo.add(person())


def test_somebody_who_is_not_there(repo: TechnicianRepository) -> None:
    with pytest.raises(NotFoundError, match="technician"):
        repo.get("T-441")
    assert repo.find("T-441") is None
    assert repo.find(None) is None
    with pytest.raises(NotFoundError):
        repo.save(person())


def test_recertifying_replaces_the_window(repo: TechnicianRepository) -> None:
    repo.add(person())
    repo.save(person(certified_on="2026-01-01", certificate_due="2029-01-01"))
    assert repo.get("T-441").certificate_due.isoformat() == "2029-01-01"


def test_promotion(repo: TechnicianRepository) -> None:
    repo.add(person())
    repo.save(person(grade=Grade.SUPERVISOR))
    assert repo.get("T-441").grade is Grade.SUPERVISOR


def test_who_was_certified_on_a_day(repo: TechnicianRepository) -> None:
    repo.add(person("T-441"))
    repo.add(person("T-902", certified_on="2026-06-01", certificate_due="2029-06-01"))
    assert [t.badge for t in repo.certified_on("2025-03-04")] == ["T-441"]
    assert [t.badge for t in repo.certified_on("2026-07-01")] == ["T-902"]
    assert repo.certified_on("2030-01-01") == []


def test_filtering_by_grade(repo: TechnicianRepository) -> None:
    repo.add(person("T-441", grade=Grade.BENCH))
    repo.add(person("T-902", grade=Grade.SUPERVISOR))
    assert [t.badge for t in repo.by_grade(Grade.SUPERVISOR)] == ["T-902"]
    assert repo.by_grade(Grade.POLYPHASE) == []


def test_certifications_coming_due(repo: TechnicianRepository) -> None:
    repo.add(person("T-441"))
    assert [t.badge for t in repo.due_within("2025-12-01", 60)] == ["T-441"]
    assert repo.due_within("2024-01-01", 60) == []
    with pytest.raises(RuleError, match="cannot look backwards"):
        repo.due_within("2025-12-01", -1)


def test_lapsed_certifications(repo: TechnicianRepository) -> None:
    repo.add(person("T-441"))
    assert repo.lapsed_on("2026-01-01") == []
    assert [t.badge for t in repo.lapsed_on("2026-01-02")] == ["T-441"]


def test_a_row_holding_a_grade_nobody_awards(repo: TechnicianRepository) -> None:
    repo.add(person())
    repo._conn.execute("UPDATE technician SET grade = 'WIZARD'")
    with pytest.raises(ConfigError, match="not a certification grade"):
        repo.get("T-441")


def test_all_comes_back_sorted(repo: TechnicianRepository) -> None:
    for badge in ("T-902", "T-441", "T-663"):
        repo.add(person(badge))
    assert [t.badge for t in repo.all()] == ["T-441", "T-663", "T-902"]
