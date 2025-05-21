from __future__ import annotations

from decimal import Decimal

import pytest

from kilodial.errors import RuleError
from kilodial.sampling.plan import (
    INTERVAL_LADDER,
    assess,
    deviation_of,
    mean_of,
    required,
    sample_size,
    step_interval,
)
from kilodial.units.registration import Registration


def readings(*values: str) -> list[Registration]:
    return [Registration(v) for v in values]


@pytest.mark.parametrize(
    ("population", "size"),
    [
        (0, 0),
        (40, 40),
        (50, 50),
        (51, 25),
        (100, 25),
        (150, 30),
        (400, 40),
        (900, 55),
        (2000, 75),
        (8000, 100),
        (40000, 125),
    ],
)
def test_the_sample_size_table(population: int, size: int) -> None:
    assert sample_size(population) == size


def test_a_small_group_is_tested_whole() -> None:
    assert required(40) == 40
    assert required(50) == 50


def test_a_large_group_is_sampled() -> None:
    assert required(900) == 55
    assert required(40000) == 125


def test_a_negative_population() -> None:
    with pytest.raises(RuleError, match="cannot be negative"):
        sample_size(-1)


def test_the_interval_ladder_only_goes_up_one_step() -> None:
    assert step_interval(48, passed=True) == 72
    assert step_interval(72, passed=True) == 96
    assert step_interval(300, passed=True) == 300


def test_failing_moves_one_step_down() -> None:
    assert step_interval(96, passed=False) == 72
    assert step_interval(72, passed=False) == 48


def test_failing_at_the_bottom_is_a_mass_test() -> None:
    assert step_interval(48, passed=False) is None


def test_an_interval_that_is_not_on_the_ladder() -> None:
    with pytest.raises(RuleError, match="not a step"):
        step_interval(60, passed=True)
    assert 60 not in INTERVAL_LADDER


def test_mean_and_deviation() -> None:
    assert mean_of(readings("100", "102")) == Decimal("101.0000")
    assert deviation_of(readings("100", "102")) == Decimal("1.4142")
    assert deviation_of(readings("100")) == Decimal(0)
    with pytest.raises(RuleError, match="nothing to average"):
        mean_of([])


def test_a_tight_group_passes() -> None:
    outcome = assess(readings(*["100.10"] * 30), population=150)
    assert outcome.passed
    assert outcome.mean == Decimal("100.1000")
    assert outcome.deviation == Decimal(0)
    assert outcome.failures == 0
    assert str(outcome).startswith("passed")


def test_a_scattered_group_fails_on_spread_with_a_perfect_mean() -> None:
    values = ["98.5", "101.5"] * 15
    outcome = assess(readings(*values), population=150)
    assert outcome.mean == Decimal("100.0000")
    assert not outcome.passed
    assert "outside the +/-2.0 percent band" in outcome.reasons[0]


def test_a_group_with_too_many_individual_failures() -> None:
    values = ["100.0"] * 27 + ["103.0"] * 3
    outcome = assess(readings(*values), population=150)
    assert outcome.failures == 3
    assert outcome.failure_share == Decimal("0.1000")
    assert not outcome.passed
    assert any("outside the band" in r for r in outcome.reasons)


def test_one_failure_in_thirty_is_tolerated_on_count_alone() -> None:
    values = ["100.0"] * 29 + ["102.4"]
    outcome = assess(readings(*values), population=150)
    assert outcome.failures == 1
    assert outcome.failure_share <= Decimal("0.05")


def test_a_short_sample_fails_before_anything_else() -> None:
    outcome = assess(readings(*["100.0"] * 10), population=150)
    assert not outcome.passed
    assert "the sample is 10 and a population of 150 needs 30" in outcome.reasons[0]


def test_more_readings_than_meters() -> None:
    with pytest.raises(RuleError, match="for a population of"):
        assess(readings("100", "100"), population=1)


def test_an_empty_group() -> None:
    with pytest.raises(RuleError, match="no meters in it"):
        assess([], population=0)


def test_the_band_can_be_narrowed() -> None:
    values = ["100.6"] * 30
    assert assess(readings(*values), population=150).passed
    tight = assess(readings(*values), population=150, band=Decimal("0.5"))
    assert not tight.passed


def test_the_working_is_printable() -> None:
    outcome = assess(readings(*["100.0", "101.0"] * 15), population=150)
    assert "30 of 150" in outcome.show()
    assert "mean 100.5000" in outcome.show()
    assert outcome.required == 30
    assert outcome.tested == 30
