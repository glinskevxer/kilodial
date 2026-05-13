from __future__ import annotations

from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path

import pytest

from kilodial.adjust.compute import BilledMonth
from kilodial.errors import RuleError
from kilodial.estimate.basis import Basis
from kilodial.estimate.service import (
    daily_metered,
    estimate_point,
    gap_for,
    options_for,
)
from kilodial.store.shop import Shop, open_shop
from kilodial.tamper.event import Finding
from kilodial.tools.smoke import LAST_DAY, stand_up
from kilodial.units.money import Money
from kilodial.units.span import DateSpan

GAP = DateSpan("2025-03-01", "2025-05-31")


@pytest.fixture
def shop(tmp_path: Path) -> Iterator[Shop]:
    opened = open_shop(tmp_path / "shop.sqlite3", create=True)
    stand_up(opened)
    yield opened
    opened.close()


def bill_year(shop: Shop, year: int, amount: str = "100.00") -> None:
    for index in range(1, 13):
        last = LAST_DAY.get(index, 30 if index in (9, 11) else 31)
        shop.billing.add(
            "SP-1042",
            BilledMonth.of(f"{year}-{index:02d}-01", f"{year}-{index:02d}-{last}", amount),
        )


def confirm(shop: Shop, since: str = "2025-03-01", found: str = "2025-05-31") -> None:
    shop.tamper.add(
        Finding.raise_finding("TF-1", "SP-1042", "bypass", found_on=found, found_by="R Ellis")
    )
    shop.tamper.save(shop.tamper.get("TF-1").confirmed(on=found, since=since, evidence="jumper"))


def test_the_gap_comes_off_the_confirmed_findings(shop: Shop) -> None:
    confirm(shop)
    span = gap_for(shop, "sp-1042", on="2025-12-31")
    assert span.start.isoformat() == "2025-03-01"
    assert span.end is not None
    assert span.end.isoformat() == "2025-05-31"


def test_a_point_with_nothing_confirmed(shop: Shop) -> None:
    with pytest.raises(RuleError, match="nothing is confirmed"):
        gap_for(shop, "SP-1042", on="2025-12-31")


def test_a_gap_is_clipped_to_the_days_a_meter_was_set(shop: Shop) -> None:
    confirm(shop, since="2015-01-01", found="2025-05-31")
    span = gap_for(shop, "SP-1042", on="2025-12-31")
    assert span.start.isoformat() == "2019-05-02"


def test_a_gap_with_no_meter_on_it(shop: Shop) -> None:
    shop.installs.pull("SP-1042", "2019-06-01")
    confirm(shop)
    with pytest.raises(RuleError, match="no meter was set"):
        gap_for(shop, "SP-1042", on="2025-12-31")


def test_both_bases_are_offered_when_the_history_supports_them(shop: Shop) -> None:
    bill_year(shop, 2024)
    for month in shop.billing.for_point("SP-1042"):
        if month.span.start.year == 2025 and month.span.start.month in (3, 4, 5):
            shop.billing.delete("SP-1042", month.span.start)
    found = options_for(shop, "SP-1042", GAP)
    assert found.has_any
    assert [e.basis for e in found.offered] == [Basis.LAST_YEAR, Basis.NEIGHBOURS]
    assert [basis for basis, _ in found.refused] == [Basis.METERED]
    assert "2 bases, 1 refused" in found.show()


def test_the_strongest_basis_comes_first(shop: Shop) -> None:
    bill_year(shop, 2024, "500.00")
    found = options_for(shop, "SP-1042", GAP)
    assert found.best().basis is Basis.LAST_YEAR
    assert found.best().amount == Money("1500.00")


def test_a_basis_the_history_cannot_support_is_refused(shop: Shop) -> None:
    found = options_for(shop, "SP-1042", GAP)
    reasons = dict(found.refused)
    assert set(reasons) == {Basis.METERED, Basis.LAST_YEAR}
    assert "last year is no basis" in reasons[Basis.LAST_YEAR]


def test_nothing_at_all_refuses_rather_than_inventing(shop: Shop) -> None:
    for month in shop.billing.for_point("SP-1042"):
        shop.billing.delete("SP-1042", month.span.start)
    found = options_for(shop, "SP-1042", GAP)
    assert not found.has_any
    assert len(found.refused) == 3
    with pytest.raises(RuleError, match="nothing on the book supports"):
        found.best()


def test_the_spread_between_the_offers(shop: Shop) -> None:
    bill_year(shop, 2024, "500.00")
    found = options_for(shop, "SP-1042", GAP)
    assert found.spread().cents > 0
    assert options_for(shop, "SP-1042", DateSpan("2030-01-01", "2030-03-31")).spread().is_zero


def test_estimating_a_point_end_to_end(shop: Shop) -> None:
    bill_year(shop, 2024)
    confirm(shop)
    found = estimate_point(shop, "SP-1042", on="2025-12-31", note="pulled 2025-05-31")
    assert found.has_any
    assert found.best().note == "pulled 2025-05-31"
    assert found.span.start.isoformat() == "2025-03-01"


def take(shop: Shop, value: int, on: str, serial: str = "84-119302") -> None:
    from kilodial.model.reading import Reading

    shop.readings.add(Reading.build("SP-1042", serial, read_on=on, dials=5, value=value))


def test_the_metered_basis_needs_a_rate(shop: Shop) -> None:
    found = options_for(shop, "SP-1042", GAP)
    reasons = dict(found.refused)
    assert "no energy rate was given" in reasons[Basis.METERED]


def test_the_metered_basis_needs_readings_either_side(shop: Shop) -> None:
    found = options_for(shop, "SP-1042", GAP, rate_per_kwh="0.12")
    assert any("not enough to meter either side" in why for _, why in found.refused)


def test_the_metered_basis_when_the_book_supports_it(shop: Shop) -> None:
    take(shop, 41_200, "2025-01-01")
    take(shop, 41_800, "2025-06-30")
    found = options_for(shop, "SP-1042", GAP, rate_per_kwh="0.12")
    assert found.best().basis is Basis.METERED
    assert found.best().amount.cents > 0


def test_the_daily_metered_figure(shop: Shop) -> None:
    take(shop, 41_200, "2025-01-01")
    take(shop, 41_380, "2025-01-31")
    assert daily_metered(shop, "SP-1042", GAP) == Decimal("6.000")


def test_readings_off_two_meters_do_not_pair(shop: Shop) -> None:
    take(shop, 41_200, "2025-01-01")
    shop.meters.add(
        __import__("kilodial.model.meter", fromlist=["Meter"]).Meter.receive(
            "84-119303", "Halvern/R4S", acquired="2015-01-01"
        )
    )
    take(shop, 100, "2025-06-30", "84-119303")
    with pytest.raises(RuleError, match="off different meters"):
        daily_metered(shop, "SP-1042", GAP)


def test_readings_on_the_same_day(shop: Shop) -> None:
    take(shop, 41_200, "2025-01-01")
    shop.meters.add(
        __import__("kilodial.model.meter", fromlist=["Meter"]).Meter.receive(
            "84-119303", "Halvern/R4S", acquired="2015-01-01"
        )
    )
    with pytest.raises(RuleError, match="not enough to meter either side"):
        daily_metered(shop, "SP-1042", GAP)
