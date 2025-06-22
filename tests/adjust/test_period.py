from __future__ import annotations

from datetime import date

import pytest

from kilodial.adjust.period import Boundary, period_for
from kilodial.errors import RuleError


def test_the_tariff_cap_usually_wins() -> None:
    p = period_for(found_on="2025-06-30", set_on="2010-01-01", cap_months=60)
    assert p.span.start == date(2020, 6, 30)
    assert p.span.end == date(2025, 6, 30)
    assert p.reason is Boundary.TARIFF_CAP
    assert "the tariff lookback" in p.explain()


def test_a_short_back_bill_lookback() -> None:
    p = period_for(found_on="2025-06-30", set_on="2010-01-01", cap_months=12)
    assert p.span.start == date(2024, 6, 30)
    assert p.days == 366


def test_the_day_the_meter_was_set_can_stop_it_sooner() -> None:
    p = period_for(found_on="2025-06-30", set_on="2023-04-01", cap_months=60)
    assert p.span.start == date(2023, 4, 1)
    assert p.reason is Boundary.METER_SET


def test_a_clean_test_stops_it_the_day_after() -> None:
    p = period_for(
        found_on="2025-06-30",
        set_on="2010-01-01",
        cap_months=60,
        last_clean_on="2022-09-14",
    )
    assert p.span.start == date(2022, 9, 15)
    assert p.reason is Boundary.CLEAN_TEST
    assert p.clean_at == date(2022, 9, 14)


def test_an_old_clean_test_does_not_extend_the_cap() -> None:
    p = period_for(
        found_on="2025-06-30",
        set_on="2010-01-01",
        cap_months=60,
        last_clean_on="2015-01-01",
    )
    assert p.reason is Boundary.TARIFF_CAP
    assert p.span.start == date(2020, 6, 30)


def test_a_pulled_meter_ends_the_period_at_the_pull() -> None:
    p = period_for(
        found_on="2025-06-30",
        set_on="2010-01-01",
        cap_months=60,
        pulled_on="2025-05-14",
    )
    assert p.span.end == date(2025, 5, 14)


def test_a_pull_after_the_test_does_not_extend_the_period() -> None:
    p = period_for(
        found_on="2025-06-30",
        set_on="2010-01-01",
        cap_months=60,
        pulled_on="2025-08-01",
    )
    assert p.span.end == date(2025, 6, 30)


def test_a_meter_set_after_the_test_leaves_no_period() -> None:
    with pytest.raises(RuleError, match="no adjustment period"):
        period_for(found_on="2025-06-30", set_on="2025-07-01", cap_months=60)


def test_a_clean_test_on_the_day_of_the_pull_leaves_no_period() -> None:
    with pytest.raises(RuleError, match="no adjustment period"):
        period_for(
            found_on="2025-06-30",
            set_on="2010-01-01",
            cap_months=60,
            pulled_on="2025-05-14",
            last_clean_on="2025-05-14",
        )


def test_a_tie_names_the_most_informative_boundary() -> None:
    p = period_for(
        found_on="2025-06-30",
        set_on="2022-09-15",
        cap_months=60,
        last_clean_on="2022-09-14",
    )
    assert p.span.start == date(2022, 9, 15)
    assert p.reason is Boundary.CLEAN_TEST


def test_the_period_cuts_into_billing_months() -> None:
    p = period_for(found_on="2025-04-03", set_on="2025-01-15", cap_months=60)
    assert [str(m) for m in p.months] == [
        "2025-01-15 to 2025-01-31",
        "2025-02-01 to 2025-02-28",
        "2025-03-01 to 2025-03-31",
        "2025-04-01 to 2025-04-03",
    ]
    assert sum(m.days for m in p.months) == p.days


def test_a_daft_lookback() -> None:
    with pytest.raises(RuleError, match="positive month count"):
        period_for(found_on="2025-06-30", set_on="2010-01-01", cap_months=0)


def test_the_working_is_kept() -> None:
    p = period_for(found_on="2025-06-30", set_on="2023-04-01", cap_months=60)
    assert p.capped_at == date(2020, 6, 30)
    assert p.set_at == date(2023, 4, 1)
    assert p.clean_at is None
    assert str(p).startswith("2023-04-01 to 2025-06-30")
