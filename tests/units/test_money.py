from __future__ import annotations

from decimal import Decimal

import pytest

from kilodial.errors import BadInputError
from kilodial.units.money import Money


def test_reads_the_usual_shapes() -> None:
    assert Money("12.34").cents == 1234
    assert Money("$1,204.05").cents == 120405
    assert Money(7).cents == 700
    assert Money(Decimal("0.005")).cents == 1
    assert Money(3.10).cents == 310


def test_accounting_parentheses_mean_negative() -> None:
    assert Money("(42.50)").cents == -4250


def test_default_is_zero() -> None:
    assert Money().is_zero
    assert Money.zero() == Money(0)


@pytest.mark.parametrize("bad", ["", "lots", "1.2.3", None, [1]])
def test_rubbish_is_refused(bad: object) -> None:
    with pytest.raises(BadInputError):
        Money(bad)


def test_from_cents_wants_a_whole_number() -> None:
    assert Money.from_cents(-5).cents == -5
    with pytest.raises(BadInputError, match="whole number"):
        Money.from_cents(1.5)  # type: ignore[arg-type]


def test_dollars_and_str() -> None:
    assert Money("1234.5").dollars == Decimal("1234.50")
    assert str(Money("1234.5")) == "$1,234.50"
    assert str(Money("-0.07")) == "-$0.07"


def test_arithmetic() -> None:
    assert Money("10") + Money("2.50") == Money("12.50")
    assert Money("10") - Money("12.50") == Money("-2.50")
    assert -Money("3") == Money("-3")
    assert abs(Money("-3")) == Money("3")


def test_arithmetic_against_another_type() -> None:
    with pytest.raises(TypeError):
        _ = Money("1") + 1


def test_scaling_rounds_half_up_at_the_cent() -> None:
    assert Money("10.00").scaled("0.125") == Money("1.25")
    assert Money("0.05").scaled("0.5") == Money("0.03")
    assert Money("100").scaled(Decimal("1.0062")) == Money("100.62")


def test_scaling_by_money_is_refused() -> None:
    with pytest.raises(BadInputError, match="not money"):
        Money("1").scaled(Money("1"))
    with pytest.raises(BadInputError, match="cannot scale"):
        Money("1").scaled(None)


def test_split_adds_back_to_the_whole() -> None:
    parts = Money("100.00").split([1, 1, 1])
    assert [p.cents for p in parts] == [3334, 3333, 3333]
    assert sum(p.cents for p in parts) == 10000


def test_split_follows_the_weights() -> None:
    parts = Money("60.00").split([30, 20, 10])
    assert [str(p) for p in parts] == ["$30.00", "$20.00", "$10.00"]


def test_split_keeps_the_sign() -> None:
    parts = Money("-1.00").split([1, 1, 1])
    assert [p.cents for p in parts] == [-34, -33, -33]


def test_split_gives_a_zero_weight_nothing() -> None:
    parts = Money("10.00").split([1, 0, 1])
    assert [p.cents for p in parts] == [500, 0, 500]


@pytest.mark.parametrize("weights", [[], [0, 0], [1, -1]])
def test_bad_splits(weights: list[int]) -> None:
    with pytest.raises(BadInputError):
        Money("10").split(weights)


def test_ordering_and_hashing() -> None:
    assert Money("1") < Money("2")
    assert sorted([Money("3"), Money("-1"), Money("2")])[0] == Money("-1")
    assert len({Money("1"), Money("1.00"), Money("2")}) == 2
    assert Money("1") != "1"
