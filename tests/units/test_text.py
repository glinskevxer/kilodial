from __future__ import annotations

from decimal import Decimal

import pytest

from kilodial.errors import BadInputError
from kilodial.units.text import key, number, optional, positive, tidy


def test_tidy_collapses_internal_whitespace() -> None:
    assert tidy("  north   wall  ", "bench name") == "north wall"


@pytest.mark.parametrize("bad", ["", "   ", None, 7, ["a"]])
def test_tidy_refuses_the_unusable(bad: object) -> None:
    with pytest.raises(BadInputError):
        tidy(bad, "bench name")


def test_tidy_has_a_limit() -> None:
    assert tidy("x" * 40, "bench name") == "x" * 40
    with pytest.raises(BadInputError, match="40 characters"):
        tidy("x" * 41, "bench name")
    assert tidy("x" * 60, "bench name", 80) == "x" * 60


def test_key_upper_cases() -> None:
    assert key(" rs-5511 ", "standard serial", 24) == "RS-5511"


def test_optional_treats_blank_as_missing() -> None:
    assert optional(None, "note") is None
    assert optional("   ", "note") is None
    assert optional("  cover   cracked ", "note") == "cover cracked"


def test_optional_still_has_a_limit_and_a_type() -> None:
    with pytest.raises(BadInputError, match="240 characters"):
        optional("x" * 241, "note")
    with pytest.raises(BadInputError, match="cannot read"):
        optional(7, "note")


def test_number_reads_what_it_should() -> None:
    assert number("7.2", "constant") == Decimal("7.2")
    assert number(7, "constant") == Decimal(7)
    assert number(7.2, "constant") == Decimal("7.2")
    assert number(Decimal("7.2"), "constant") == Decimal("7.2")


@pytest.mark.parametrize("bad", ["", "lots", None, True, [1]])
def test_number_refuses_the_rest(bad: object) -> None:
    with pytest.raises(BadInputError):
        number(bad, "constant")


def test_positive_wants_more_than_nothing() -> None:
    assert positive("1", "multiplier") == Decimal("1")
    with pytest.raises(BadInputError, match="above zero"):
        positive("0", "multiplier")
    with pytest.raises(BadInputError, match="above zero"):
        positive("-1", "multiplier")


def test_positive_takes_a_ceiling() -> None:
    assert positive("99", "multiplier", ceiling=Decimal("100")) == Decimal("99")
    with pytest.raises(BadInputError, match="not a real installation"):
        positive("101", "multiplier", ceiling=Decimal("100"))
