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


def test_reading_a_member_by_its_label() -> None:
    from kilodial.orders.order import OrderKind

    assert member_of(OrderKind, "test", "order kind", field="label") is OrderKind.TEST


def test_a_field_nobody_stores_by() -> None:
    with pytest.raises(ConfigError, match="an enum column is stored by"):
        member_of(MeterState, "stock", "meter state", field="colour")


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


def test_has_row_and_one_row(tmp_path: object) -> None:
    from pathlib import Path

    from kilodial.errors import NotFoundError
    from kilodial.store.base import has_row, one_row
    from kilodial.store.book import open_migrated

    book = open_migrated(Path(str(tmp_path)) / "shop.sqlite3", create=True)
    try:
        conn = book.connection
        assert not has_row(conn, "meter", "serial", "84-119302")
        with pytest.raises(NotFoundError, match="meter"):
            one_row(conn, "serial", "meter", "serial", "84-119302", "meter")
        conn.execute(
            "INSERT INTO meter (serial, device_key, state, acquired, owner) "
            "VALUES ('84-119302', 'a/b', 'stock', '2025-01-01', 'utility')"
        )
        assert has_row(conn, "meter", "serial", "84-119302")
        row = one_row(conn, "serial, state", "meter", "serial", "84-119302", "meter")
        assert row == ("84-119302", "stock")
    finally:
        book.close()


def test_one_row_calls_the_record_what_a_person_would() -> None:
    from kilodial.errors import NotFoundError

    exc = NotFoundError("sampling group", "G1")
    assert "sampling group" in str(exc)
