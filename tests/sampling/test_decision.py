from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from kilodial.errors import RuleError
from kilodial.sampling.decision import decide, decimal_or_zero, interval_after
from kilodial.sampling.plan import SampleOutcome, assess
from kilodial.units.registration import Registration


def outcome(values: list[str], population: int = 150) -> SampleOutcome:
    return assess([Registration(v) for v in values], population=population)


def tight() -> SampleOutcome:
    return outcome(["100.10"] * 30)


def loose() -> SampleOutcome:
    return outcome(["98.5", "101.5"] * 15)


def test_a_passing_sample_moves_the_group_up_a_step() -> None:
    d = decide("G1", tight(), on="2025-06-30", current_months=96)
    assert d.passed
    assert d.interval_months == 120
    assert d.moved == "up"
    assert d.next_due() == date(2035, 6, 30)


def test_a_failing_sample_moves_it_down() -> None:
    d = decide("G1", loose(), on="2025-06-30", current_months=96)
    assert not d.passed
    assert d.interval_months == 72
    assert d.moved == "down"
    assert d.reasons()


def test_failing_at_the_bottom_is_a_mass_test() -> None:
    d = decide("G1", loose(), on="2025-06-30", current_months=48)
    assert d.is_mass_test
    assert d.interval_months is None
    assert d.moved == "mass test"
    assert d.next_due() is None
    assert "mass test" in d.show()


def test_passing_at_the_top_holds() -> None:
    d = decide("G1", tight(), on="2025-06-30", current_months=300)
    assert d.interval_months == 300
    assert d.moved == "held"


def test_an_interval_that_is_not_on_the_ladder() -> None:
    with pytest.raises(RuleError, match="not a step on the ladder"):
        decide("G1", tight(), on="2025-06-30", current_months=60)


def test_the_group_code_is_upper_cased_and_the_note_tidied() -> None:
    d = decide("g1", tight(), on="2025-06-30", current_months=48, note="  spring  sample ")
    assert d.group_code == "G1"
    assert d.note == "spring sample"
    assert decide("G1", tight(), on="2025-06-30", current_months=48, note="  ").note is None


def test_replaying_a_history() -> None:
    first = decide("G1", tight(), on="2021-06-30", current_months=48)
    second = decide("G1", tight(), on="2025-06-30", current_months=72)
    assert interval_after([second, first]) == 96
    assert interval_after([]) == 48


def test_a_mass_test_puts_the_group_back_at_the_bottom() -> None:
    up = decide("G1", tight(), on="2021-06-30", current_months=48)
    pulled = decide("G1", loose(), on="2025-06-30", current_months=48)
    assert interval_after([up, pulled]) == 48


def test_replay_takes_the_decisions_in_date_order() -> None:
    later = decide("G1", tight(), on="2029-06-30", current_months=96)
    earlier = decide("G1", tight(), on="2025-06-30", current_months=72)
    assert interval_after([later, earlier]) == 120


def test_the_decision_carries_the_working() -> None:
    d = decide("G1", tight(), on="2025-06-30", current_months=48)
    assert d.outcome.tested == 30
    assert d.outcome.mean == Decimal("100.1000")
    assert str(d).startswith("G1 2025-06-30")


def test_reading_a_stored_statistic() -> None:
    assert decimal_or_zero(None) == Decimal(0)
    assert decimal_or_zero("100.1") == Decimal("100.1")
