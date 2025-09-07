from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from kilodial.model.meter import MeterState
from kilodial.report import shop as report
from kilodial.store.shop import Shop, open_shop
from kilodial.tools.smoke import stand_up


@pytest.fixture
def shop(tmp_path: Path) -> Iterator[Shop]:
    opened = open_shop(tmp_path / "shop.sqlite3", create=True)
    stand_up(opened)
    yield opened
    opened.close()


def test_the_fleet_grid_lists_every_state(shop: Shop) -> None:
    grid = report.fleet_grid(shop)
    assert [row[0] for row in grid.rows] == [s.value for s in MeterState]
    assert dict(grid.dicts()[0])["state"] == "received"


def test_the_fleet_grid_follows_the_meters(shop: Shop) -> None:
    shop.meters.move("84-119302", MeterState.STOCK)
    counts = {row["state"]: row["meters"] for row in report.fleet_grid(shop).dicts()}
    assert counts["stock"] == "1"
    assert counts["received"] == "0"


def test_the_run_grid_is_empty_before_any_runs(shop: Shop) -> None:
    rows = report.run_grid(shop).dicts()
    assert all(row["passed"] == "0" for row in rows)


def test_the_standards_grid_says_how_long_is_left(shop: Shop) -> None:
    rows = report.standards_grid(shop, "2034-11-04").dicts()
    assert rows[0]["standard"] == "RS-5511"
    assert rows[0]["state"] == "due"
    assert report.standards_grid(shop, "2020-01-01").dicts()[0]["state"] == "current"
    assert report.standards_grid(shop, "2036-01-01").dicts()[0]["state"] == "expired"


def test_the_report_names_the_day(shop: Shop) -> None:
    doc = report.build(shop, on="2025-06-30")
    assert doc.title == "Meter shop report as at 2025-06-30"
    assert doc.render().startswith("Meter shop report as at 2025-06-30")


def test_the_report_has_every_section(shop: Shop) -> None:
    titles = [s.title for s in report.build(shop, on="2025-06-30").sections]
    assert titles == [
        "Overview",
        "Fleet",
        "Bench runs",
        "Reference standards",
        "Periodic programme",
        "Work orders",
        "Customer requests",
        "Book",
    ]


def test_the_overview_carries_the_row_counts(shop: Shop) -> None:
    doc = report.build(shop, on="2025-06-30")
    facts = dict(doc.sections[0].facts)
    assert facts["meters"] == "1"
    assert facts["billed months"] == "6"


def test_a_clean_book_reports_no_faults(shop: Shop) -> None:
    doc = report.build(shop, on="2025-06-30")
    book = doc.sections[-1]
    assert dict(book.facts)["faults"] == "0"
    assert book.notes == []


def test_a_broken_book_is_reported(shop: Shop) -> None:
    shop.book.connection.execute(
        "UPDATE meter SET device_key = 'Nowhere/X1' WHERE serial = '84-119302'"
    )
    book = report.build(shop, on="2025-06-30").sections[-1]
    assert dict(book.facts)["faults"] != "0"
    assert book.notes


def test_the_report_renders_to_json_and_csv(shop: Shop) -> None:
    doc = report.build(shop, on="2025-06-30")
    assert '"title"' in doc.as_json()
    assert doc.as_csv().startswith("state,meters")


def test_the_programme_section_counts_the_due(shop: Shop) -> None:
    facts = dict(report.build(shop, on="2025-06-30").sections[4].facts)
    assert set(facts) == {"current", "due", "overdue", "ungrouped"}
    assert facts["ungrouped"] == "0"
