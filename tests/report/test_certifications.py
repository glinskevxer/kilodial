from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from kilodial.model.technician import Grade, Technician
from kilodial.report import certifications as report
from kilodial.store.shop import Shop, open_shop
from kilodial.tools.smoke import stand_up
from kilodial.xfmr.transformer import InstrumentTransformer, TransformerKind


@pytest.fixture
def shop(tmp_path: Path) -> Iterator[Shop]:
    opened = open_shop(tmp_path / "shop.sqlite3", create=True)
    stand_up(opened)
    opened.technicians.add(
        Technician.build(
            "T-441",
            "R Ellis",
            grade=Grade.BENCH,
            certified_on="2023-01-01",
            certificate_due="2026-01-01",
        )
    )
    opened.transformers.add(
        InstrumentTransformer.build(
            "CT-8841",
            kind=TransformerKind.CURRENT,
            maker="Ferrand",
            marked_ratio="40",
            accuracy="0.3",
            rcf="1.0000",
            tested_on="2020-05-01",
        )
    )
    yield opened
    opened.close()


def test_standing_from_days_left() -> None:
    assert report.standing_of(-1) is report.Standing.LAPSED
    assert report.standing_of(0) is report.Standing.DUE
    assert report.standing_of(90) is report.Standing.DUE
    assert report.standing_of(91) is report.Standing.CURRENT
    assert report.standing_of(91, warning=120) is report.Standing.DUE


def test_which_standings_need_work() -> None:
    assert not report.Standing.CURRENT.needs_work
    assert report.Standing.DUE.needs_work
    assert str(report.Standing.LAPSED) == "lapsed"


def test_all_three_kinds_are_tracked(shop: Shop) -> None:
    lines = report.lines_for(shop, "2025-06-30")
    kinds = {line.kind for line in lines}
    assert kinds == {"standard", "technician", "transformer"}


def test_the_soonest_to_expire_comes_first(shop: Shop) -> None:
    lines = report.lines_for(shop, "2025-06-30")
    assert [line.days_left for line in lines] == sorted(line.days_left for line in lines)
    assert lines[0].kind == "technician"


def test_a_transformer_is_dated_from_its_last_test(shop: Shop) -> None:
    line = next(x for x in report.lines_for(shop, "2025-06-30") if x.kind == "transformer")
    assert line.expires.isoformat() == "2028-05-01"
    assert line.standing is report.Standing.CURRENT


def test_a_lapsed_certification_is_reported(shop: Shop) -> None:
    lines = report.lines_for(shop, "2026-06-30")
    lapsed = [line for line in lines if line.standing is report.Standing.LAPSED]
    assert [line.reference for line in lapsed] == ["T-441"]
    assert str(lapsed[0]).startswith("technician T-441 lapsed")


def test_the_warning_window_moves_the_boundary(shop: Shop) -> None:
    on = "2025-08-01"
    assert all(
        line.standing is not report.Standing.DUE
        for line in report.lines_for(shop, on)
        if line.reference == "T-441"
    )
    wider = report.lines_for(shop, on, warning=180)
    assert any(line.standing is report.Standing.DUE for line in wider if line.reference == "T-441")


def test_the_grid_has_a_row_per_line(shop: Shop) -> None:
    lines = report.lines_for(shop, "2025-06-30")
    grid = report.grid(lines)
    assert len(grid.rows) == len(lines)
    assert grid.headings == tuple(report.HEADINGS)


def test_the_report_counts_each_standing(shop: Shop) -> None:
    doc = report.build(shop, on="2026-06-30")
    facts = dict(doc.sections[0].facts)
    assert facts["tracked"] == "3"
    assert facts["lapsed"] == "1"
    assert facts["warning window"] == "90 days"


def test_the_report_names_the_transformer_policy(shop: Shop) -> None:
    doc = report.build(shop, on="2025-06-30")
    assert dict(doc.sections[1].facts)["test interval"] == "96 months"
    assert doc.sections[1].notes


def test_the_report_renders(shop: Shop) -> None:
    doc = report.build(shop, on="2025-06-30")
    assert "Certification report as at 2025-06-30" in doc.render()
    assert doc.as_csv().startswith("kind,reference,detail")
