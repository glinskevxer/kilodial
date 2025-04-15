from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from kilodial.errors import DuplicateError, NotFoundError
from kilodial.store.book import Book, open_migrated
from kilodial.store.transformers import TransformerRepository
from kilodial.xfmr.transformer import AccuracyClass, InstrumentTransformer, TransformerKind


@pytest.fixture
def repo(tmp_path: Path) -> Iterator[TransformerRepository]:
    book: Book = open_migrated(tmp_path / "shop.sqlite3", create=True)
    yield TransformerRepository(book.connection)
    book.close()


def ct(serial: str = "CT-8841", **over: object) -> InstrumentTransformer:
    args: dict[str, object] = {
        "kind": TransformerKind.CURRENT,
        "maker": "Ferrand",
        "marked_ratio": "40",
        "accuracy": "0.3",
        "rcf": "1.0020",
        "phase_minutes": "12",
        "burden": "B0.2",
        "tested_on": "2024-05-01",
    }
    args.update(over)
    return InstrumentTransformer.build(serial, **args)  # type: ignore[arg-type]


def test_add_and_get(repo: TransformerRepository) -> None:
    added = repo.add(ct())
    assert repo.get("ct-8841") == added
    assert repo.count() == 1


def test_adding_the_same_serial_twice(repo: TransformerRepository) -> None:
    repo.add(ct())
    with pytest.raises(DuplicateError, match="instrument transformer"):
        repo.add(ct())


def test_something_that_is_not_there(repo: TransformerRepository) -> None:
    with pytest.raises(NotFoundError, match="instrument transformer"):
        repo.get("CT-8841")
    assert repo.find("CT-8841") is None
    assert repo.find(None) is None
    with pytest.raises(NotFoundError):
        repo.save(ct())


def test_retesting_a_transformer(repo: TransformerRepository) -> None:
    repo.add(ct())
    repo.save(ct(rcf="1.0035", tested_on="2026-05-01"))
    got = repo.get("CT-8841")
    assert str(got.rcf) == "1.0035"
    assert got.tested_on.isoformat() == "2026-05-01"


def test_filtering_by_kind(repo: TransformerRepository) -> None:
    repo.add(ct("CT-8841"))
    repo.add(ct("VT-2201", kind=TransformerKind.VOLTAGE, marked_ratio="20"))
    assert [t.serial for t in repo.by_kind(TransformerKind.VOLTAGE)] == ["VT-2201"]
    assert [t.serial for t in repo.by_kind(TransformerKind.CURRENT)] == ["CT-8841"]


def test_filtering_by_accuracy_class(repo: TransformerRepository) -> None:
    repo.add(ct("CT-8841", accuracy="0.3"))
    repo.add(ct("CT-8842", accuracy="0.6"))
    assert [t.serial for t in repo.by_accuracy(AccuracyClass.C06)] == ["CT-8842"]
    assert repo.by_accuracy(AccuracyClass.C12) == []


def test_transformers_overdue_for_a_test(repo: TransformerRepository) -> None:
    repo.add(ct("CT-8841", tested_on="2018-01-01"))
    repo.add(ct("CT-8842", tested_on="2024-05-01"))
    overdue = repo.tested_before("2020-01-01")
    assert [t.serial for t in overdue] == ["CT-8841"]
    assert [t.serial for t in repo.tested_before("2026-01-01")] == ["CT-8841", "CT-8842"]


def test_all_comes_back_sorted(repo: TransformerRepository) -> None:
    for serial in ("CT-8843", "CT-8841", "CT-8842"):
        repo.add(ct(serial))
    assert [t.serial for t in repo.all()] == ["CT-8841", "CT-8842", "CT-8843"]
