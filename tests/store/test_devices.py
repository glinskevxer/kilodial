from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from kilodial.errors import BadInputError, DuplicateError, NotFoundError
from kilodial.model.device import DeviceType
from kilodial.model.form import MeterClass, Technology
from kilodial.store.book import Book, open_migrated
from kilodial.store.devices import DeviceRepository, split_key


@pytest.fixture
def repo(tmp_path: Path) -> Iterator[DeviceRepository]:
    book: Book = open_migrated(tmp_path / "shop.sqlite3", create=True)
    yield DeviceRepository(book.connection)
    book.close()


def device(maker: str = "Halvern", model: str = "R4S", **over: object) -> DeviceType:
    args: dict[str, object] = {
        "form_code": "2S",
        "class_code": "200",
        "voltage": "240",
        "kh": "7.2",
        "technology": Technology.INDUCTION,
        "register_ratio": "100",
        "introduced": "2004-05-01",
    }
    args.update(over)
    return DeviceType.build(maker, model, **args)  # type: ignore[arg-type]


def test_split_key() -> None:
    assert split_key("Halvern/R4S") == ("Halvern", "R4S")
    assert split_key(" Halvern / R4S ") == ("Halvern", "R4S")


@pytest.mark.parametrize("bad", ["Halvern", "a/b/c", "/R4S", "Halvern/", None, 4])
def test_bad_keys(bad: object) -> None:
    with pytest.raises(BadInputError):
        split_key(bad)


def test_add_and_get(repo: DeviceRepository) -> None:
    added = repo.add(device())
    assert repo.get("Halvern/R4S") == added
    assert repo.exists("Halvern/R4S")
    assert repo.count() == 1


def test_adding_the_same_key_twice(repo: DeviceRepository) -> None:
    repo.add(device())
    with pytest.raises(DuplicateError, match="already on the book"):
        repo.add(device(kh="14.4"))


def test_getting_something_that_is_not_there(repo: DeviceRepository) -> None:
    with pytest.raises(NotFoundError, match="device type"):
        repo.get("Halvern/R4S")
    assert repo.find("Halvern/R4S") is None
    assert not repo.exists("Halvern/R4S")


def test_replace_overwrites(repo: DeviceRepository) -> None:
    repo.add(device())
    changed = repo.replace(device(retired="2016-12-31", kh="14.4"))
    assert repo.get("Halvern/R4S") == changed
    assert repo.count() == 1


def test_replacing_something_that_is_not_there(repo: DeviceRepository) -> None:
    with pytest.raises(NotFoundError):
        repo.replace(device())


def test_all_comes_back_sorted(repo: DeviceRepository) -> None:
    repo.add(device("Vantage", "SM3", technology=Technology.SOLID_STATE, register_ratio=None))
    repo.add(device("Halvern", "R4S"))
    repo.add(device("Halvern", "A2"))
    assert [d.key for d in repo.all()] == ["Halvern/A2", "Halvern/R4S", "Vantage/SM3"]


def test_filtering_by_class(repo: DeviceRepository) -> None:
    repo.add(device("Halvern", "R4S", class_code="200"))
    repo.add(device("Halvern", "R9S", form_code="9S", class_code="20"))
    assert [d.key for d in repo.by_class(MeterClass.CL20)] == ["Halvern/R9S"]
    assert [d.key for d in repo.by_class(MeterClass.CL320)] == []


def test_filtering_by_technology(repo: DeviceRepository) -> None:
    repo.add(device("Halvern", "R4S"))
    repo.add(device("Vantage", "SM3", technology=Technology.SOLID_STATE, register_ratio=None))
    assert [d.key for d in repo.by_technology(Technology.SOLID_STATE)] == ["Vantage/SM3"]
    assert [d.key for d in repo.by_technology(Technology.INDUCTION)] == ["Halvern/R4S"]


def test_types_current_on_a_day(repo: DeviceRepository) -> None:
    repo.add(device("Halvern", "R4S", introduced="2004-01-01", retired="2012-12-31"))
    repo.add(
        device(
            "Vantage",
            "SM3",
            introduced="2014-01-01",
            technology=Technology.SOLID_STATE,
            register_ratio=None,
        )
    )
    assert [d.key for d in repo.current_on("2010-06-01")] == ["Halvern/R4S"]
    assert [d.key for d in repo.current_on("2020-06-01")] == ["Vantage/SM3"]
    assert repo.current_on("2013-06-01") == []


def test_a_round_trip_keeps_every_field(repo: DeviceRepository) -> None:
    original = device(demand_capable=True, retired="2016-12-31", voltage="277")
    repo.add(original)
    assert repo.get(original.key) == original
