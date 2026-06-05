"""The properties the arithmetic has to hold, checked over a lot of values.

The unit tests check the cases somebody thought of. These check the statements
that have to be true of every input, over enough inputs that a case nobody
thought of has to survive them.

There is no random generation here and that is deliberate. A test that fails on
a seed nobody recorded is a test that reports a problem and then loses it, and
the value of a property is only realised when the failure is reproducible. So
the inputs are enumerated: a wide, boring, fixed sweep.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from kilodial.units.money import Money
from kilodial.units.registration import Registration

CENTS = [0, 1, 2, 3, 7, 99, 100, 101, 999, 1000, 12_345, 999_999, -1, -7, -12_345]
WEIGHTS = [
    [1],
    [1, 1],
    [1, 1, 1],
    [1, 2],
    [2, 1],
    [1, 0, 1],
    [30, 20, 10],
    [1, 1, 1, 1, 1, 1, 1],
    [365, 28, 31],
]
PERCENTS = [
    "50.0000",
    "90.0000",
    "99.0000",
    "99.9900",
    "100.0000",
    "100.0100",
    "101.0000",
    "110.0000",
    "200.0000",
]


@pytest.mark.parametrize("cents", CENTS)
@pytest.mark.parametrize("weights", WEIGHTS)
def test_a_split_always_adds_back_to_the_whole(cents: int, weights: list[int]) -> None:
    whole = Money.from_cents(cents)
    parts = whole.split(weights)
    assert sum(p.cents for p in parts) == cents


@pytest.mark.parametrize("cents", CENTS)
@pytest.mark.parametrize("weights", WEIGHTS)
def test_a_split_gives_one_part_per_weight(cents: int, weights: list[int]) -> None:
    assert len(Money.from_cents(cents).split(weights)) == len(weights)


@pytest.mark.parametrize("cents", CENTS)
@pytest.mark.parametrize("weights", WEIGHTS)
def test_a_split_keeps_the_sign_of_the_whole(cents: int, weights: list[int]) -> None:
    parts = Money.from_cents(cents).split(weights)
    if cents > 0:
        assert all(p.cents >= 0 for p in parts)
    elif cents < 0:
        assert all(p.cents <= 0 for p in parts)
    else:
        assert all(p.is_zero for p in parts)


@pytest.mark.parametrize("cents", CENTS)
@pytest.mark.parametrize("weights", WEIGHTS)
def test_a_zero_weight_gets_nothing(cents: int, weights: list[int]) -> None:
    parts = Money.from_cents(cents).split(weights)
    for weight, part in zip(weights, parts, strict=True):
        if weight == 0:
            assert part.is_zero


@pytest.mark.parametrize("cents", CENTS)
@pytest.mark.parametrize("weights", WEIGHTS)
def test_no_two_parts_differ_by_more_than_a_penny_on_equal_weights(
    cents: int, weights: list[int]
) -> None:
    if len(set(weights)) != 1:
        return
    parts = [p.cents for p in Money.from_cents(cents).split(weights)]
    assert max(parts) - min(parts) <= 1


@pytest.mark.parametrize("cents", CENTS)
def test_negating_twice_is_the_original(cents: int) -> None:
    whole = Money.from_cents(cents)
    flipped = -whole
    assert -flipped == whole
    assert abs(whole).cents == abs(cents)


@pytest.mark.parametrize("cents", CENTS)
def test_adding_and_subtracting_the_same_amount_returns(cents: int) -> None:
    whole = Money.from_cents(cents)
    other = Money("12.34")
    assert whole + other - other == whole


@pytest.mark.parametrize("percent", PERCENTS)
def test_composing_with_nominal_changes_nothing(percent: str) -> None:
    reading = Registration(percent)
    assert reading.compose(Registration.nominal()) == reading
    assert Registration.nominal().compose(reading) == reading


@pytest.mark.parametrize("percent", PERCENTS)
@pytest.mark.parametrize("other", PERCENTS)
def test_composition_is_commutative(percent: str, other: str) -> None:
    assert Registration(percent).compose(Registration(other)) == Registration(other).compose(
        Registration(percent)
    )


@pytest.mark.parametrize("percent", PERCENTS)
def test_the_correction_factor_undoes_the_error(percent: str) -> None:
    reading = Registration(percent)
    corrected = reading.percent * reading.correction_factor
    assert abs(corrected - Decimal(100)) < Decimal("0.01")


@pytest.mark.parametrize("percent", PERCENTS)
def test_fast_and_slow_are_exclusive(percent: str) -> None:
    reading = Registration(percent)
    assert not (reading.is_fast and reading.is_slow)
    assert reading.is_fast == (reading.error > 0)
    assert reading.is_slow == (reading.error < 0)


@pytest.mark.parametrize("percent", PERCENTS)
@pytest.mark.parametrize("band", ["0.5", "1.0", "2.0", "5.0"])
def test_within_a_band_agrees_with_the_error(percent: str, band: str) -> None:
    reading = Registration(percent)
    assert reading.within(band) == (abs(reading.error) <= Decimal(band))


@pytest.mark.parametrize("percent", PERCENTS)
def test_a_reading_round_trips_through_its_own_string(percent: str) -> None:
    reading = Registration(percent)
    assert Registration(reading.percent) == reading
    assert Registration(str(reading.percent)) == reading
