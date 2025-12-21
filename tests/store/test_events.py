from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from kilodial.errors import BadInputError, RuleError
from kilodial.store.book import Book, open_migrated
from kilodial.store.events import EventRepository


@pytest.fixture
def repo(tmp_path: Path) -> Iterator[EventRepository]:
    book: Book = open_migrated(tmp_path / "shop.sqlite3", create=True)
    yield EventRepository(book.connection)
    book.close()


def test_recording_a_line(repo: EventRepository) -> None:
    event = repo.record("received", "meter 84-119302", detail="from the vendor")
    assert event.sequence == 1
    assert event.actor == "shop"
    assert event.action == "received"
    assert event.detail == "from the vendor"
    assert repo.count() == 1


def test_the_action_is_lower_cased_and_tidied(repo: EventRepository) -> None:
    event = repo.record("  RECEIVED  ", "meter 84-119302")
    assert event.action == "received"


def test_the_stamp_is_an_iso_time(repo: EventRepository) -> None:
    event = repo.record("received", "meter 84-119302")
    assert event.at.endswith("+00:00")
    assert len(event.day) == 10


def test_a_stamp_can_be_supplied(repo: EventRepository) -> None:
    event = repo.record("received", "x", at="2025-03-04T09:15:00+00:00")
    assert event.day == "2025-03-04"
    with pytest.raises(RuleError, match="cannot be blank"):
        repo.record("received", "x", at="  ")


def test_the_sequence_climbs(repo: EventRepository) -> None:
    for index in range(3):
        repo.record("received", f"meter {index}")
    assert [e.sequence for e in repo.all()] == [1, 2, 3]


def test_the_tail_of_the_log(repo: EventRepository) -> None:
    for index in range(5):
        repo.record("received", f"meter {index}")
    assert [e.subject for e in repo.all(limit=2)] == ["meter 3", "meter 4"]
    with pytest.raises(RuleError, match="positive number of lines"):
        repo.all(limit=0)


def test_everything_about_one_subject(repo: EventRepository) -> None:
    repo.record("received", "meter 84-119302")
    repo.record("moved", "meter 84-119302", detail="to stock")
    repo.record("received", "meter 84-119303")
    assert [e.action for e in repo.about("meter 84-119302")] == ["received", "moved"]
    assert repo.about("meter 84-000000") == []


def test_filtering_by_action_and_actor(repo: EventRepository) -> None:
    repo.record("received", "meter 1", actor="R Ellis")
    repo.record("moved", "meter 1", actor="M Okafor")
    assert [e.subject for e in repo.by_action("moved")] == ["meter 1"]
    assert [e.actor for e in repo.by_actor("R Ellis")] == ["R Ellis"]
    assert repo.by_actor("Nobody") == []


def test_a_day_of_the_log(repo: EventRepository) -> None:
    repo.record("received", "meter 1", at="2025-03-04T09:15:00+00:00")
    repo.record("moved", "meter 1", at="2025-03-05T09:15:00+00:00")
    assert [e.action for e in repo.on_day("2025-03-04")] == ["received"]
    assert repo.on_day("2025-03-06") == []


def test_counts_by_action(repo: EventRepository) -> None:
    repo.record("received", "meter 1")
    repo.record("received", "meter 2")
    repo.record("moved", "meter 1")
    assert repo.counts_by_action() == {"moved": 1, "received": 2}


def test_a_deleted_line_leaves_a_gap(repo: EventRepository) -> None:
    for index in range(3):
        repo.record("received", f"meter {index}")
    assert repo.gaps() == []
    repo._conn.execute("DELETE FROM event WHERE sequence = 2")
    assert repo.gaps() == [2]


def test_an_empty_log_has_no_gaps(repo: EventRepository) -> None:
    assert repo.gaps() == []
    assert repo.all() == []


def test_the_sequence_does_not_reuse_a_deleted_number(repo: EventRepository) -> None:
    repo.record("received", "meter 1")
    repo.record("received", "meter 2")
    repo._conn.execute("DELETE FROM event WHERE sequence = 2")
    assert repo.record("received", "meter 3").sequence == 3


@pytest.mark.parametrize("bad", ["", "   ", None])
def test_a_line_with_nothing_in_it(repo: EventRepository, bad: object) -> None:
    with pytest.raises(BadInputError):
        repo.record(bad, "meter 84-119302")


def test_str_reads_like_a_day_book(repo: EventRepository) -> None:
    event = repo.record(
        "moved", "meter 84-119302", detail="to stock", at="2025-03-04T09:15:00+00:00"
    )
    assert str(event) == "2025-03-04T09:15:00+00:00 shop moved meter 84-119302, to stock"
