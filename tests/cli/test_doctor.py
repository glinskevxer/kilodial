from __future__ import annotations

from pathlib import Path

import pytest

from kilodial.cli.doctor import Level, examine, worst
from kilodial.model.technician import Grade, Technician
from kilodial.store.shop import open_shop
from kilodial.tools.smoke import stand_up
from tests.cli.conftest import Invoke


@pytest.fixture
def stocked(invoke: Invoke, book: Path) -> Invoke:
    invoke("init")
    with open_shop(book) as shop:
        stand_up(shop)
    return invoke


def test_the_levels_are_ordered() -> None:
    assert Level.STOP.rank > Level.WARN.rank > Level.NOTE.rank
    assert str(Level.WARN) == "warn"


def test_worst_of_nothing_is_nothing() -> None:
    assert worst([]) is None


def test_a_fresh_book_has_nothing_to_report(started: Invoke) -> None:
    result = started("doctor", "--on", "2025-06-30")
    assert "nothing to report" in result.output


def test_an_overdue_fleet_is_a_warning(stocked: Invoke) -> None:
    result = stocked("doctor", "--on", "2026-06-30", expect=1)
    assert "overdue" in result.output
    assert "warn" in result.output


def test_a_broken_reference_stops(stocked: Invoke, book: Path) -> None:
    with open_shop(book) as shop:
        shop.book.connection.execute(
            "UPDATE meter SET device_key = 'Nowhere/X1' WHERE serial = '84-119302'"
        )
    result = stocked("doctor", "--on", "2025-06-30", expect=2)
    assert "stop" in result.output
    assert "Nowhere/X1" in result.output


def test_an_expired_standard_stops(stocked: Invoke) -> None:
    result = stocked("doctor", "--on", "2036-01-01", expect=2)
    assert "ran out of certificate" in result.output


def test_a_standard_coming_due_only_warns(stocked: Invoke) -> None:
    result = stocked("doctor", "--on", "2034-12-15", expect=1)
    assert "days left" in result.output
    assert "stop" not in result.output


def test_a_lapsed_technician_warns(stocked: Invoke, book: Path) -> None:
    with open_shop(book) as shop:
        shop.technicians.add(
            Technician.build(
                "T-441",
                "R Ellis",
                grade=Grade.BENCH,
                certified_on="2019-01-01",
                certificate_due="2022-01-01",
            )
        )
    result = stocked("doctor", "--on", "2025-06-30", expect=1)
    assert "no longer certified" in result.output


def test_an_ungrouped_meter_is_only_a_note(stocked: Invoke, book: Path) -> None:
    with open_shop(book) as shop:
        shop.groups.delete("G1")
        findings = examine(shop, "2025-06-30")
    assert any(f.level is Level.NOTE for f in findings)
    assert any("no sampling group" in f.detail for f in findings)


def test_quiet_leaves_the_notes_out(stocked: Invoke, book: Path) -> None:
    with open_shop(book) as shop:
        shop.groups.delete("G1")
    assert "no sampling group" in stocked("doctor", "--on", "2025-06-30", expect=1).output
    quiet = stocked("doctor", "--on", "2025-06-30", "--quiet", expect=1)
    assert "no sampling group" not in quiet.output


def test_findings_come_back_worst_first(stocked: Invoke, book: Path) -> None:
    with open_shop(book) as shop:
        shop.book.connection.execute("UPDATE meter SET device_key = 'Nowhere/X1'")
        findings = examine(shop, "2026-06-30")
    assert findings[0].level is Level.STOP
    assert worst(findings) is Level.STOP
    assert str(findings[0]).startswith("stop:")


def test_an_unusable_run_is_a_warning(stocked: Invoke) -> None:
    stocked(
        "run",
        "record",
        "TR-1",
        "--meter",
        "84-119302",
        "--bench",
        "B2",
        "--on",
        "2036-06-30",
        "--by",
        "R Ellis",
        "--fl",
        "100.10",
        "--ll",
        "99.80",
    )
    result = stocked("doctor", "--on", "2025-06-30", expect=1)
    assert "cannot be relied on" in result.output


def test_an_overdue_complaint_stops(stocked: Invoke) -> None:
    stocked("complaint", "open", "CR-1", "SP-1042", "--on", "2025-01-04", "--by", "M Okafor")
    result = stocked("doctor", "--on", "2025-06-30", expect=2)
    assert "past their thirty days" in result.output


def test_a_late_work_order_warns(stocked: Invoke) -> None:
    stocked("work", "raise", "WO-1", "test", "84-119302", "--on", "2025-01-04")
    result = stocked("doctor", "--on", "2025-06-30", expect=1)
    assert "past due" in result.output
