from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from kilodial.errors import DuplicateError, NotFoundError, RuleError
from kilodial.model.device import DeviceType
from kilodial.model.form import Technology
from kilodial.model.meter import Meter, MeterState
from kilodial.sampling.decision import decide
from kilodial.sampling.group import Group
from kilodial.sampling.plan import assess
from kilodial.store.book import Book, open_migrated
from kilodial.store.devices import DeviceRepository
from kilodial.store.groups import GroupRepository, PlanRepository
from kilodial.store.meters import MeterRepository
from kilodial.units.registration import Registration


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
    devices.add(
        DeviceType.build(
            "Vantage",
            "SM3",
            form_code="16S",
            class_code="320",
            voltage="277",
            kh="1.0",
            technology=Technology.SOLID_STATE,
            introduced="2018-01-01",
        )
    )
    yield opened
    opened.close()


@pytest.fixture
def groups(book: Book) -> GroupRepository:
    return GroupRepository(book.connection)


@pytest.fixture
def plans(book: Book, groups: GroupRepository) -> PlanRepository:
    groups.add(Group.build("G1", "Halvern R4S", device_keys=["Halvern/R4S"]))
    return PlanRepository(book.connection)


def stock(book: Book, serial: str, device_key: str = "Halvern/R4S") -> Meter:
    return MeterRepository(book.connection).add(
        Meter.receive(serial, device_key, acquired="2019-04-02")
    )


def tight_sample(population: int = 150) -> object:
    return assess([Registration("100.10")] * 30, population=population)


def test_groups_round_trip(groups: GroupRepository) -> None:
    group = Group.build(
        "G1",
        "Halvern R4S",
        device_keys=["Halvern/R4S"],
        class_code="200",
        technology=Technology.INDUCTION,
        form_codes=["2S"],
        acquired_from="2015-01-01",
    )
    groups.add(group)
    assert groups.get("g1") == group
    assert groups.count() == 1
    with pytest.raises(DuplicateError, match="sampling group"):
        groups.add(group)


def test_a_group_that_is_not_there(groups: GroupRepository) -> None:
    with pytest.raises(NotFoundError, match="sampling group"):
        groups.get("G1")
    with pytest.raises(NotFoundError):
        groups.save(Group.build("G1", "x"))
    with pytest.raises(NotFoundError):
        groups.delete("G1")


def test_editing_and_deleting_a_group(groups: GroupRepository) -> None:
    groups.add(Group.build("G1", "old name"))
    groups.save(Group.build("G1", "new name", class_code="200"))
    assert groups.get("G1").name == "new name"
    groups.delete("G1")
    assert groups.count() == 0


def test_membership_is_worked_out_from_the_criteria(book: Book, groups: GroupRepository) -> None:
    groups.add(Group.build("G1", "Halvern only", device_keys=["Halvern/R4S"]))
    stock(book, "84-119302")
    stock(book, "84-119303")
    stock(book, "84-119304", "Vantage/SM3")
    assert [m.serial for m in groups.members("G1")] == ["84-119302", "84-119303"]
    assert groups.population("G1") == 2


def test_membership_by_technology_needs_the_catalogue(book: Book, groups: GroupRepository) -> None:
    groups.add(Group.build("G2", "solid state", technology=Technology.SOLID_STATE))
    stock(book, "84-119302")
    stock(book, "84-119304", "Vantage/SM3")
    assert [m.serial for m in groups.members("G2")] == ["84-119304"]


def test_a_meter_whose_type_is_not_catalogued_is_left_out(
    book: Book, groups: GroupRepository
) -> None:
    groups.add(Group.build("G2", "class 200", class_code="200"))
    MeterRepository(book.connection).add(
        Meter.receive("84-119999", "Nowhere/X1", acquired="2019-04-02"),
        require_device=False,
    )
    assert groups.members("G2") == []


def test_a_scrapped_meter_leaves_the_population(book: Book, groups: GroupRepository) -> None:
    groups.add(Group.build("G1", "everything"))
    stock(book, "84-119302")
    MeterRepository(book.connection).move("84-119302", MeterState.STOCK)
    assert groups.population("G1") == 1
    MeterRepository(book.connection).move("84-119302", MeterState.SCRAP, on="2025-01-01")
    assert groups.population("G1") == 0


def test_which_groups_a_meter_falls_into(book: Book, groups: GroupRepository) -> None:
    groups.add(Group.build("G1", "Halvern", device_keys=["Halvern/R4S"]))
    groups.add(Group.build("G2", "induction", technology=Technology.INDUCTION))
    groups.add(Group.build("G3", "solid state", technology=Technology.SOLID_STATE))
    stock(book, "84-119302")
    assert [g.code for g in groups.group_for("84-119302")] == ["G1", "G2"]


def test_recording_a_decision(plans: PlanRepository) -> None:
    decision = decide("G1", tight_sample(), on="2025-06-30", current_months=48)  # type: ignore[arg-type]
    plans.record(decision)
    assert plans.count() == 1
    latest = plans.latest("G1")
    assert latest is not None
    assert latest.interval_months == 72
    assert plans.interval("G1") == 72


def test_a_decision_on_a_group_nobody_has(plans: PlanRepository) -> None:
    decision = decide("G9", tight_sample(), on="2025-06-30", current_months=48)  # type: ignore[arg-type]
    with pytest.raises(RuleError, match="G9 is not on the book"):
        plans.record(decision)


def test_two_decisions_on_the_same_day(plans: PlanRepository) -> None:
    decision = decide("G1", tight_sample(), on="2025-06-30", current_months=48)  # type: ignore[arg-type]
    plans.record(decision)
    with pytest.raises(DuplicateError, match="sample decision"):
        plans.record(decision)


def test_the_interval_is_replayed_from_the_history(plans: PlanRepository) -> None:
    plans.record(decide("G1", tight_sample(), on="2021-06-30", current_months=48))  # type: ignore[arg-type]
    plans.record(decide("G1", tight_sample(), on="2025-06-30", current_months=72))  # type: ignore[arg-type]
    assert plans.interval("G1") == 96
    assert [d.previous_months for d in plans.history("G1")] == [48, 72]


def test_a_group_with_no_decisions_is_on_the_bottom_step(plans: PlanRepository) -> None:
    assert plans.interval("G1") == 48
    assert plans.latest("G1") is None
    assert plans.next_due("G1") is None


def test_when_a_group_is_next_due(plans: PlanRepository) -> None:
    plans.record(decide("G1", tight_sample(), on="2025-06-30", current_months=48))  # type: ignore[arg-type]
    assert plans.next_due("G1") == "2031-06-30"


def test_groups_due_by_a_day_include_the_ones_never_sampled(
    plans: PlanRepository, groups: GroupRepository
) -> None:
    groups.add(Group.build("G2", "never sampled"))
    plans.record(decide("G1", tight_sample(), on="2025-06-30", current_months=48))  # type: ignore[arg-type]
    assert plans.due_by("2026-01-01") == ["G2"]
    assert sorted(plans.due_by("2032-01-01")) == ["G1", "G2"]


def test_deleting_a_group_takes_its_decisions(
    plans: PlanRepository, groups: GroupRepository
) -> None:
    plans.record(decide("G1", tight_sample(), on="2025-06-30", current_months=48))  # type: ignore[arg-type]
    groups.delete("G1")
    assert plans.count() == 0
