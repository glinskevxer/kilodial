from __future__ import annotations

import enum

import pytest

from kilodial.errors import ConfigError, NotFoundError
from kilodial.model.form import MeterClass
from kilodial.model.meter import MeterState
from kilodial.model.run import PointKind
from kilodial.store.base import member_of, or_none, upper


def test_reading_a_member_by_value() -> None:
    assert member_of(MeterState, "stock", "meter state") is MeterState.STOCK


def test_reading_a_member_by_name() -> None:
    assert member_of(MeterState, "STOCK", "meter state", field="name") is MeterState.STOCK


def test_reading_a_member_by_its_short_code() -> None:
    assert member_of(PointKind, "FL", "point kind", field="code") is PointKind.FULL_LOAD
    assert member_of(MeterClass, "CL200", "meter class", field="code") is MeterClass.CL200


def test_an_enum_whose_value_is_a_tuple_is_not_matched_by_value() -> None:
    with pytest.raises(ConfigError, match="not a point kind"):
        member_of(PointKind, "FL", "point kind")


def test_a_value_the_book_should_not_hold() -> None:
    with pytest.raises(ConfigError, match="the book holds 'melted'"):
        member_of(MeterState, "melted", "meter state")


def test_a_field_nobody_stores_by() -> None:
    with pytest.raises(ConfigError, match="an enum column is stored by"):
        member_of(MeterState, "stock", "meter state", field="label")


def test_an_enum_with_no_such_attribute_matches_nothing() -> None:
    class Plain(enum.Enum):
        ONE = "one"

    with pytest.raises(ConfigError):
        member_of(Plain, "one", "plain", field="code")


def test_upper_is_the_key_shape() -> None:
    assert upper("  rs-5511 ") == "RS-5511"


def test_or_none_swallows_a_missing_record() -> None:
    def getter(key: str) -> str:
        if key == "here":
            return "found"
        raise NotFoundError("thing", key)

    assert or_none(getter, "here") == "found"
    assert or_none(getter, "gone") is None
    assert or_none(getter, None) is None


def test_or_none_does_not_swallow_anything_else() -> None:
    def getter(key: str) -> str:
        raise ValueError("that is a bug")

    with pytest.raises(ValueError, match="that is a bug"):
        or_none(getter, "anything")
