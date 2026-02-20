from __future__ import annotations

from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path

import pytest

from kilodial.model.run import RunKind
from kilodial.model.technician import Grade, Technician
from kilodial.report import bench as report
from kilodial.store.shop import Shop, open_shop
from kilodial.testing.record import Readings, build_run
from kilodial.testing.verdict import Outcome
from kilodial.tools.smoke import stand_up
from kilodial.units.span import DateSpan

YEAR = DateSpan("2025-01-01", "2025-12-31")


@pytest.fixture
def shop(tmp_path: Path) -> Iterator[Shop]:
    opened = open_shop(tmp_path / "shop.sqlite3", create=True)
    stand_up(opened)
    opened.technicians.add(
        Technician.build(
            "T-441",
            "R Ellis",
            grade=Grade.SUPERVISOR,
            certified_on="2020-01-01",
            certificate_due="2030-01-01",
        )
    )
    yield opened
    opened.close()


def run(
    shop: Shop,
    reference: str,
    reading: str,
    on: str = "2025-03-04",
    badge: str | None = "T-441",
    who: str = "R Ellis",
) -> None:
    shop.runs.add(
        build_run(
            reference,
            device=shop.device_for("84-119302"),
            meter_serial="84-119302",
            bench_code="B2",
            standard_serial="RS-5511",
            kind=RunKind.AS_FOUND,
            tested_on=on,
            technician=who,
            badge=badge,
            readings=Readings.of(full_load=reading, light_load=reading),
        )
    )


def test_nobody_benched_anything(shop: Shop) -> None:
    assert report.workers(shop, YEAR) == []


def test_one_technician_with_a_pass_and_a_failure(shop: Shop) -> None:
    run(shop, "TR-1", "100.10")
    run(shop, "TR-2", "104.00", on="2025-04-04")
    found = report.workers(shop, YEAR)
    assert len(found) == 1
    assert found[0].runs == 2
    assert found[0].outcomes[Outcome.PASSED] == 1
    assert found[0].outcomes[Outcome.FAILED] == 1
    assert found[0].void_rate == Decimal("0.0")
    assert str(found[0]) == "R Ellis (T-441) 2 runs"


def test_an_unsigned_run_is_kept_apart(shop: Shop) -> None:
    run(shop, "TR-1", "100.10", badge=None)
    found = report.workers(shop, YEAR)
    assert found[0].badge == report.UNSIGNED


def test_a_void_run_shows_as_void_rather_than_a_failure(shop: Shop) -> None:
    run(shop, "TR-1", "100.10", on="2036-03-04")
    found = report.workers(shop, DateSpan("2036-01-01", "2036-12-31"))
    assert found[0].outcomes[Outcome.VOID] == 1
    assert found[0].outcomes[Outcome.FAILED] == 0
    assert found[0].void_rate == Decimal("100.0")


def test_the_busiest_technician_comes_first(shop: Shop) -> None:
    run(shop, "TR-1", "100.10")
    run(shop, "TR-2", "100.10", on="2025-04-04")
    run(shop, "TR-3", "100.10", on="2025-05-04", badge=None, who="M Okafor")
    found = report.workers(shop, YEAR)
    assert [w.name for w in found] == ["R Ellis", "M Okafor"]


def test_runs_outside_the_window(shop: Shop) -> None:
    run(shop, "TR-1", "100.10", on="2024-03-04")
    assert report.workers(shop, YEAR) == []


def test_the_grid(shop: Shop) -> None:
    run(shop, "TR-1", "100.10")
    grid = report.grid(report.workers(shop, YEAR))
    assert grid.headings == tuple(report.HEADINGS)
    assert grid.dicts()[0]["badge"] == "T-441"


def test_the_kind_grid_covers_every_kind(shop: Shop) -> None:
    run(shop, "TR-1", "100.10")
    grid = report.kind_grid(report.workers(shop, YEAR))
    kinds = {row["kind"] for row in grid.dicts()}
    assert kinds == {k.value for k in RunKind}
    assert next(r for r in grid.dicts() if r["kind"] == "as found")["runs"] == "1"


def test_the_report_notes_a_void_rate(shop: Shop) -> None:
    run(shop, "TR-1", "100.10", on="2036-03-04")
    doc = report.build(shop, first="2036-01-01", last="2036-12-31")
    assert "void rate" in doc.sections[0].notes[0]
    assert dict(doc.sections[0].facts)["void"] == "1"


def test_the_report_counts_unsigned_runs(shop: Shop) -> None:
    run(shop, "TR-1", "100.10", badge=None)
    doc = report.build(shop, first="2025-01-01", last="2025-12-31")
    assert dict(doc.sections[0].facts)["unsigned runs"] == "1"


def test_the_report_renders(shop: Shop) -> None:
    run(shop, "TR-1", "100.10")
    doc = report.build(shop, first="2025-01-01", last="2025-12-31")
    assert "Bench report" in doc.title
    assert doc.as_csv().startswith("technician,badge,runs")
