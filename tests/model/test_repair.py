from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from kilodial.errors import BadInputError, RuleError
from kilodial.model.repair import Fault, Repair, families, fault_named
from kilodial.units.money import Money


def repair(**over: object) -> Repair:
    args: dict[str, object] = {
        "repaired_on": "2025-03-14",
        "by": "R Ellis",
        "hours": "1.5",
        "parts": "12.40",
        "replacement_cost": "184.00",
    }
    args.update(over)
    return Repair.build(
        str(args.pop("reference", "RP-1")),
        str(args.pop("meter_serial", "84-119302")),
        args.pop("fault", Fault.BEARING),
        **args,
    )


def test_fault_lookup() -> None:
    assert fault_named("bearing") is Fault.BEARING
    assert fault_named("POTENTIAL_LINK") is Fault.POTENTIAL_LINK
    assert fault_named("none found") is Fault.NONE_FOUND
    assert fault_named(Fault.COIL) is Fault.COIL


@pytest.mark.parametrize("bad", ["gremlins", "", None, 4])
def test_a_fault_nobody_records(bad: object) -> None:
    with pytest.raises(BadInputError, match="not a fault"):
        fault_named(bad)


def test_faults_carry_a_family() -> None:
    assert Fault.BEARING.family == "mechanical"
    assert Fault.BOARD.family == "electronic"
    assert Fault.NONE_FOUND.family == "none"
    assert str(Fault.COVER) == "cover"


def test_nothing_found_is_not_a_fault() -> None:
    assert Fault.BEARING.is_a_fault
    assert not Fault.NONE_FOUND.is_a_fault


def test_the_families_group_every_fault() -> None:
    grouped = families()
    assert sum(len(v) for v in grouped.values()) == len(Fault)
    assert Fault.BEARING in grouped["mechanical"]


def test_a_repair_costs_labour_plus_parts() -> None:
    r = repair()
    assert r.labour == Money("102.00")
    assert r.cost == Money("114.40")
    assert r.repaired_on == date(2025, 3, 14)
    assert str(r) == "RP-1 84-119302 bearing $114.40"


def test_a_cheap_repair_is_worth_doing() -> None:
    r = repair(hours="0.5", parts="4.00")
    assert r.share_of_replacement < Decimal("0.60")
    assert r.was_worth_it
    assert "worth doing" in r.verdict()


def test_an_expensive_repair_was_not() -> None:
    r = repair(hours="2", parts="40.00")
    assert not r.was_worth_it
    assert "should have been scrapped" in r.verdict()


def test_the_boundary_is_inclusive() -> None:
    r = repair(hours="1", parts="42.40", replacement_cost="184.00")
    assert r.share_of_replacement == Decimal("0.6000")
    assert r.was_worth_it


def test_nothing_found_says_so() -> None:
    assert "nothing found" in repair(fault="none found").verdict()


@pytest.mark.parametrize("bad", ["0", "-1", "ages", "41"])
def test_bad_hours(bad: object) -> None:
    with pytest.raises(Exception, match="hours|no time|working week"):
        repair(hours=bad)


def test_negative_parts() -> None:
    with pytest.raises(BadInputError, match="less than nothing"):
        repair(parts="-1")


def test_a_replacement_price_of_nothing() -> None:
    with pytest.raises(RuleError, match="replacement price above zero"):
        repair(replacement_cost="0")


def test_notes_are_tidied() -> None:
    assert repair(note="  jewel   replaced ").note == "jewel replaced"
    assert repair(note="  ").note is None


def test_the_serial_and_reference_are_upper_cased() -> None:
    r = repair(reference=" rp-1 ", meter_serial=" 84-119302 ")
    assert r.reference == "RP-1"
    assert r.meter_serial == "84-119302"
