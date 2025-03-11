from __future__ import annotations

from collections.abc import Iterator
from datetime import date
from pathlib import Path

import pytest

from kilodial.errors import DuplicateError, NotFoundError, RuleError, StateError
from kilodial.model.device import DeviceType
from kilodial.model.form import Technology
from kilodial.model.meter import Meter, MeterState
from kilodial.store.book import Book, open_migrated
from kilodial.store.devices import DeviceRepository
from kilodial.store.meters import MeterRepository


@pytest.fixture
def book(tmp_path: Path) -> Iterator[Book]:
    opened = open_migrated(tmp_path / "shop.sqlite3", create=True)
    devices = DeviceRepository(opened.connection)
    devices.add(
        DeviceType.build(
            "Halvern",
            "R4S",
            form_code="2S",
            class_code="200",
            voltage="240",
            kh="7.2",
            technology=Technology.INDUCTION,
            register_ratio="100",
            introduced="2004-05-01",
        )
    )
    yield opened
    opened.close()


@pytest.fixture
def repo(book: Book) -> MeterRepository:
    return MeterRepository(book.connection)


def meter(serial: str = "84-119302", **over: object) -> Meter:
    args: dict[str, object] = {"acquired": "2019-04-02"}
    args.update(over)
    return Meter.receive(serial, str(args.pop("device_key", "Halvern/R4S")), **args)  # type: ignore[arg-type]


def test_add_and_get(repo: MeterRepository) -> None:
    repo.add(meter())
    got = repo.get("84-119302")
    assert got.device_key == "Halvern/R4S"
    assert got.state is MeterState.RECEIVED
    assert repo.count() == 1


def test_lookups_normalise_the_serial(repo: MeterRepository) -> None:
    repo.add(meter())
    assert repo.exists(" 84-119302 ")
    assert repo.get("84-119302").serial == "84-119302"


def test_adding_the_same_serial_twice(repo: MeterRepository) -> None:
    repo.add(meter())
    with pytest.raises(DuplicateError, match="meter"):
        repo.add(meter())


def test_a_meter_naming_a_type_nobody_stocks(repo: MeterRepository) -> None:
    with pytest.raises(RuleError, match="not on the book"):
        repo.add(meter(device_key="Nowhere/X1"))


def test_receiving_may_skip_the_type_check(repo: MeterRepository) -> None:
    repo.add(meter(device_key="Nowhere/X1"), require_device=False)
    assert repo.get("84-119302").device_key == "Nowhere/X1"


def test_getting_something_that_is_not_there(repo: MeterRepository) -> None:
    with pytest.raises(NotFoundError, match="meter"):
        repo.get("84-119302")
    assert repo.find("84-119302") is None


def test_moving_a_meter_writes_it_down(repo: MeterRepository) -> None:
    repo.add(meter())
    repo.move("84-119302", MeterState.STOCK)
    repo.move("84-119302", MeterState.SET)
    assert repo.get("84-119302").state is MeterState.SET


def test_an_illegal_move_is_refused_and_nothing_is_written(repo: MeterRepository) -> None:
    repo.add(meter())
    with pytest.raises(StateError):
        repo.move("84-119302", MeterState.SET)
    assert repo.get("84-119302").state is MeterState.RECEIVED


def test_scrapping_records_the_day(repo: MeterRepository) -> None:
    repo.add(meter())
    repo.move("84-119302", MeterState.SCRAP, on="2025-06-01")
    assert repo.get("84-119302").retired_on == date(2025, 6, 1)


def test_resealing(repo: MeterRepository) -> None:
    repo.add(meter(seal="BX4471"))
    assert repo.reseal("84-119302", "CT9902").seal == "CT9902"
    assert repo.get("84-119302").seal == "CT9902"
    assert repo.reseal("84-119302", None).seal is None


def test_saving_something_that_is_not_there(repo: MeterRepository) -> None:
    with pytest.raises(NotFoundError):
        repo.save(meter())


def test_listing_by_state_and_by_device(repo: MeterRepository) -> None:
    repo.add(meter("84-119302"))
    repo.add(meter("84-119303"))
    repo.move("84-119303", MeterState.STOCK)
    assert [m.serial for m in repo.by_state(MeterState.STOCK)] == ["84-119303"]
    assert [m.serial for m in repo.by_device("Halvern/R4S")] == ["84-119302", "84-119303"]
    assert repo.by_device("Nowhere/X1") == []


def test_in_shop_leaves_out_the_field_and_the_scrap_bin(repo: MeterRepository) -> None:
    repo.add(meter("84-119302"))
    repo.add(meter("84-119303"))
    repo.add(meter("84-119304"))
    repo.move("84-119303", MeterState.STOCK)
    repo.move("84-119303", MeterState.SET)
    repo.move("84-119304", MeterState.SCRAP, on="2025-01-01")
    assert [m.serial for m in repo.in_shop()] == ["84-119302"]


def test_counts_by_state_lists_every_state(repo: MeterRepository) -> None:
    repo.add(meter("84-119302"))
    repo.add(meter("84-119303"))
    repo.move("84-119303", MeterState.STOCK)
    counts = repo.counts_by_state()
    assert set(counts) == set(MeterState)
    assert counts[MeterState.RECEIVED] == 1
    assert counts[MeterState.STOCK] == 1
    assert counts[MeterState.SCRAP] == 0


def test_all_comes_back_sorted(repo: MeterRepository) -> None:
    for serial in ("84-119304", "84-119302", "84-119303"):
        repo.add(meter(serial))
    assert [m.serial for m in repo.all()] == ["84-119302", "84-119303", "84-119304"]
