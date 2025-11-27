from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from kilodial.errors import ConfigError, DuplicateError, NotFoundError, RuleError
from kilodial.model.device import DeviceType
from kilodial.model.form import Technology
from kilodial.model.meter import Meter
from kilodial.model.repair import Fault, Repair
from kilodial.store.book import Book, open_migrated
from kilodial.store.devices import DeviceRepository
from kilodial.store.meters import MeterRepository
from kilodial.store.repairs import RepairRepository
from kilodial.units.money import Money


@pytest.fixture
def repo(tmp_path: Path) -> Iterator[RepairRepository]:
    book: Book = open_migrated(tmp_path / "shop.sqlite3", create=True)
    devices = DeviceRepository(book.connection)
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
    devices.add(
        DeviceType.build(
            "Vantage",
            "SM3",
            form_code="16S",
            class_code="320",
            voltage="277",
            kh="1.8",
            technology=Technology.SOLID_STATE,
            introduced="2014-05-01",
        )
    )
    meters = MeterRepository(book.connection)
    meters.add(Meter.receive("84-119302", "Halvern/R4S", acquired="2015-01-01"))
    meters.add(Meter.receive("84-119303", "Halvern/R4S", acquired="2015-01-01"))
    meters.add(Meter.receive("84-220001", "Vantage/SM3", acquired="2019-01-01"))
    yield RepairRepository(book.connection)
    book.close()


def repair(reference: str = "RP-1", serial: str = "84-119302", **over: object) -> Repair:
    args: dict[str, object] = {
        "repaired_on": "2025-03-14",
        "by": "R Ellis",
        "hours": "1.5",
        "parts": "12.40",
        "replacement_cost": "184.00",
    }
    args.update(over)
    return Repair.build(reference, serial, args.pop("fault", Fault.BEARING), **args)


def test_repairs_round_trip(repo: RepairRepository) -> None:
    added = repo.add(repair(note="jewel replaced"))
    assert repo.get("rp-1") == added
    assert repo.count() == 1
    with pytest.raises(DuplicateError, match="repair"):
        repo.add(repair())


def test_a_meter_nobody_has(repo: RepairRepository) -> None:
    with pytest.raises(RuleError, match="not on the book"):
        repo.add(repair(serial="84-000000"))


def test_a_repair_that_is_not_there(repo: RepairRepository) -> None:
    with pytest.raises(NotFoundError, match="repair"):
        repo.get("RP-1")
    assert repo.find("RP-1") is None
    assert repo.find(None) is None


def test_repairs_for_one_meter(repo: RepairRepository) -> None:
    repo.add(repair("RP-1", "84-119302"))
    repo.add(repair("RP-2", "84-119303"))
    assert [r.reference for r in repo.for_meter("84-119302")] == ["RP-1"]
    assert repo.for_meter("84-000000") == []


def test_filtering_by_fault(repo: RepairRepository) -> None:
    repo.add(repair("RP-1", fault=Fault.BEARING))
    repo.add(repair("RP-2", "84-119303", fault=Fault.REGISTER))
    assert [r.reference for r in repo.by_fault(Fault.REGISTER)] == ["RP-2"]
    assert repo.by_fault(Fault.COIL) == []


def test_a_window(repo: RepairRepository) -> None:
    repo.add(repair("RP-1", repaired_on="2025-01-05"))
    repo.add(repair("RP-2", "84-119303", repaired_on="2025-06-30"))
    assert [r.reference for r in repo.between("2025-05-01", "2025-12-31")] == ["RP-2"]
    with pytest.raises(RuleError, match="cannot end before"):
        repo.between("2025-12-31", "2025-01-01")


def test_counts_by_fault_lists_every_fault(repo: RepairRepository) -> None:
    repo.add(repair("RP-1", fault=Fault.BEARING))
    repo.add(repair("RP-2", "84-119303", fault=Fault.BEARING))
    counts = repo.counts_by_fault()
    assert set(counts) == set(Fault)
    assert counts[Fault.BEARING] == 2
    assert counts[Fault.COIL] == 0


def test_the_fault_breakdown_for_a_device_type(repo: RepairRepository) -> None:
    repo.add(repair("RP-1", "84-119302", fault=Fault.BEARING))
    repo.add(repair("RP-2", "84-220001", fault=Fault.BOARD))
    halvern = repo.counts_for_device("Halvern/R4S")
    assert halvern[Fault.BEARING] == 1
    assert halvern[Fault.BOARD] == 0
    assert repo.counts_for_device("Vantage/SM3")[Fault.BOARD] == 1


def test_what_the_shop_spent(repo: RepairRepository) -> None:
    repo.add(repair("RP-1", hours="1", parts="10.00"))
    repo.add(repair("RP-2", "84-119303", hours="1", parts="10.00"))
    assert repo.spent_between("2025-01-01", "2025-12-31") == Money("156.00")
    assert repo.spent_between("2024-01-01", "2024-12-31").is_zero


def test_repairs_that_were_not_worth_it(repo: RepairRepository) -> None:
    repo.add(repair("RP-1", hours="0.5", parts="4.00"))
    repo.add(repair("RP-2", "84-119303", hours="2", parts="40.00"))
    repo.add(repair("RP-3", "84-220001", fault=Fault.NONE_FOUND, hours="3", parts="0"))
    assert [r.reference for r in repo.not_worth_it()] == ["RP-2"]


def test_a_row_holding_a_fault_nobody_records(repo: RepairRepository) -> None:
    repo.add(repair())
    repo._conn.execute("UPDATE repair SET fault = 'GREMLINS'")
    with pytest.raises(ConfigError, match="not a repair fault"):
        repo.get("RP-1")
