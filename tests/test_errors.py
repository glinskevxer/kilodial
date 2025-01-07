from __future__ import annotations

import pytest

from kilodial.errors import (
    BadInputError,
    ConfigError,
    DuplicateError,
    NotFoundError,
    RuleError,
    ShopError,
    StateError,
)


@pytest.mark.parametrize(
    "cls",
    [BadInputError, NotFoundError, DuplicateError, RuleError, StateError, ConfigError],
)
def test_every_error_is_a_shop_error(cls: type[ShopError]) -> None:
    assert issubclass(cls, ShopError)


def test_not_found_carries_kind_and_key() -> None:
    exc = NotFoundError("meter", "84-119302")
    assert exc.kind == "meter"
    assert exc.key == "84-119302"
    assert "84-119302" in str(exc)
    assert "meter" in str(exc)


def test_already_exists_carries_kind_and_key() -> None:
    exc = DuplicateError("bench", "B2")
    assert exc.kind == "bench"
    assert exc.key == "B2"
    assert "already on the book" in str(exc)


def test_shop_error_is_an_exception() -> None:
    assert issubclass(ShopError, Exception)
    with pytest.raises(ShopError):
        raise RuleError("standard 5511 was out of certificate on 2025-03-04")


def test_messages_do_not_end_in_punctuation() -> None:
    for exc in (NotFoundError("meter", "x"), DuplicateError("bench", "y")):
        assert not str(exc).endswith(".")
