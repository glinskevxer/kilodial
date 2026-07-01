from __future__ import annotations

from decimal import Decimal

import pytest

from kilodial.errors import RuleError
from kilodial.sampling.attribute import PLANS, assess, comparable, plan_for


@pytest.mark.parametrize(
    ("lot", "tested", "accept"),
    [(0, 0, 0), (25, 25, 0), (26, 13, 0), (90, 20, 1), (150, 32, 2), (40000, 500, 21)],
)
def test_the_plan_table(lot: int, tested: int, accept: int) -> None:
    plan = plan_for(lot)
    assert plan.tested == tested
    assert plan.accept == accept


def test_a_small_lot_is_inspected_whole() -> None:
    plan = plan_for(20)
    assert plan.whole_lot
    assert plan.tested == 20
    assert plan.accept == 0
    assert plan.reject == 1


def test_the_rejection_number_is_one_above_acceptance() -> None:
    for ceiling, _, _ in PLANS:
        plan = plan_for(ceiling)
        assert plan.reject == plan.accept + 1


def test_a_negative_lot() -> None:
    with pytest.raises(RuleError, match="negative number of meters"):
        plan_for(-1)


def test_the_tolerated_share_climbs_with_the_lot() -> None:
    assert plan_for(20).allowed_share == Decimal("0.00")
    assert plan_for(150).allowed_share > Decimal("0")
    assert plan_for(0).allowed_share == Decimal("0.00")


def test_a_clean_sample_passes() -> None:
    found = assess(lot=150, tested=32, failed=0)
    assert found.passed
    assert found.share == Decimal("0.00")
    assert str(found).startswith("passed")


def test_a_sample_at_the_acceptance_number_passes() -> None:
    assert assess(lot=150, tested=32, failed=2).passed


def test_one_more_rejects() -> None:
    found = assess(lot=150, tested=32, failed=3)
    assert not found.passed
    assert "rejects on 3" in found.reasons[0]
    assert "3 of 32 failed" in found.show()


def test_a_short_sample_fails_on_its_own() -> None:
    found = assess(lot=150, tested=10, failed=0)
    assert not found.passed
    assert "calls for 32" in found.reasons[0]


def test_a_short_sample_and_a_rejection_are_both_reported() -> None:
    found = assess(lot=150, tested=10, failed=5)
    assert len(found.reasons) == 2


def test_more_failures_than_tests() -> None:
    with pytest.raises(RuleError, match="more than were tested"):
        assess(lot=150, tested=10, failed=11)


def test_more_tests_than_meters() -> None:
    with pytest.raises(RuleError, match="out of a lot of"):
        assess(lot=10, tested=11, failed=0)


def test_negative_counts() -> None:
    with pytest.raises(RuleError, match="cannot be negative"):
        assess(lot=150, tested=-1, failed=0)


def test_the_failure_share_of_nothing() -> None:
    assert assess(lot=0, tested=0, failed=0).share == Decimal(0)


def test_what_a_group_would_be_told_to_do() -> None:
    tested, allowed = comparable(150)
    assert tested == 32
    assert allowed > Decimal(0)
    assert comparable(20) == (20, Decimal("0.00"))


def test_the_plan_prints_its_numbers() -> None:
    assert str(plan_for(150)) == "lot 150: test 32, accept on 2, reject on 3"
