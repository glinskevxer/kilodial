from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from kilodial.errors import BadInputError
from kilodial.ingest import billing as ingest
from kilodial.install.point import ServicePoint
from kilodial.model.form import Service
from kilodial.store.shop import Shop, open_shop
from kilodial.units.money import Money

HEADER = "point,from,to,amount,kwh\n"
ROW = "SP-1042,2025-01-01,2025-01-31,104.22,912.4\n"


@pytest.fixture
def shop(tmp_path: Path) -> Iterator[Shop]:
    opened = open_shop(tmp_path / "shop.sqlite3", create=True)
    opened.points.add(
        ServicePoint.build(
            "SP-1042",
            account="44-9021",
            address="18 Fenwick Row",
            service=Service.SINGLE_PHASE_3W,
            voltage="240",
            rate_code="R1",
            energised="2011-06-14",
        )
    )
    yield opened
    opened.close()


def test_a_clean_import(shop: Shop) -> None:
    found = ingest.load_text(shop, HEADER + ROW)
    assert found.taken == 1
    assert found.clean
    month = shop.billing.get("SP-1042", "2025-01-01")
    assert month.amount == Money("104.22")
    assert shop.billing.kwh_for("SP-1042", "2025-01-01") == "912.4"


def test_a_missing_column_refuses_the_file(shop: Shop) -> None:
    with pytest.raises(BadInputError, match="missing amount"):
        ingest.load_text(shop, "point,from,to\nSP-1042,2025-01-01,2025-01-31\n")


def test_a_row_with_no_end_date_is_skipped(shop: Shop) -> None:
    found = ingest.load_text(shop, HEADER + "SP-1042,2025-02-01,,100.00,\n")
    assert found.taken == 0
    assert "to is empty" in found.skipped[0][1]


def test_a_row_for_a_point_nobody_has_is_skipped(shop: Shop) -> None:
    found = ingest.load_text(shop, HEADER + "SP-9999,2025-01-01,2025-01-31,100.00,\n")
    assert "not on the book" in found.skipped[0][1]


def test_an_amount_that_is_not_money_is_skipped(shop: Shop) -> None:
    found = ingest.load_text(shop, HEADER + "SP-1042,2025-01-01,2025-01-31,lots,\n")
    assert "not an amount of money" in found.skipped[0][1]


def test_the_billing_systems_own_formatting_is_accepted(shop: Shop) -> None:
    found = ingest.load_text(shop, HEADER + 'SP-1042,2025-01-01,2025-01-31,"$1,204.05",\n')
    assert found.taken == 1
    assert shop.billing.get("SP-1042", "2025-01-01").amount == Money("1204.05")


def test_a_credit_in_parentheses(shop: Shop) -> None:
    ingest.load_text(shop, HEADER + "SP-1042,2025-01-01,2025-01-31,(42.50),\n")
    assert shop.billing.get("SP-1042", "2025-01-01").amount == Money("-42.50")


def test_reloading_the_same_file_takes_nothing_new(shop: Shop) -> None:
    ingest.load_text(shop, HEADER + ROW)
    second = ingest.load_text(shop, HEADER + ROW)
    assert second.taken == 0
    assert "already on the book" in second.skipped[0][1]


def test_an_overlapping_period_is_reported_per_row(shop: Shop) -> None:
    text = HEADER + ROW + "SP-1042,2025-01-15,2025-02-14,100.00,\n"
    found = ingest.load_text(shop, text)
    assert found.taken == 1
    assert found.skipped[0][0] == 3


def test_a_row_out_of_order_still_lands(shop: Shop) -> None:
    text = HEADER + "SP-1042,2025-02-01,2025-02-28,100.00,\n" + ROW
    assert ingest.load_text(shop, text).taken == 2
    assert [m.span.start.month for m in shop.billing.for_point("SP-1042")] == [1, 2]


def test_a_period_that_ends_before_it_starts_is_skipped(shop: Shop) -> None:
    found = ingest.load_text(shop, HEADER + "SP-1042,2025-02-28,2025-02-01,100.00,\n")
    assert "cannot end" in found.skipped[0][1]


def test_the_total_loaded(shop: Shop) -> None:
    ingest.load_text(shop, HEADER + ROW + "SP-1042,2025-02-01,2025-02-28,95.78,\n")
    assert ingest.total_loaded(shop, "SP-1042") == Money("200.00")
    assert ingest.total_loaded(shop, "SP-9999").is_zero


def test_importing_off_disk(shop: Shop, tmp_path: Path) -> None:
    path = tmp_path / "billing.csv"
    path.write_text(HEADER + ROW)
    assert ingest.load_file(shop, path).taken == 1
