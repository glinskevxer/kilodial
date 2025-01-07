"""Every exception the package raises.

The shop is a records system before it is a calculator, so the hierarchy splits
on why a caller is wrong rather than on which module noticed. ``ShopError`` is
the only thing a caller ever has to catch; the command layer maps it to an exit
code and prints ``str(exc)`` with no traceback.
"""

from __future__ import annotations


class ShopError(Exception):
    """Base for everything raised on purpose."""


class BadInputError(ShopError):
    """A value the caller supplied cannot be used at all.

    Reach for this when the argument is malformed rather than merely
    inconvenient: a negative test current, a percentage that is not a number, a
    date string that does not parse.
    """


class NotFoundError(ShopError):
    """A record was looked up by key and is not on the book."""

    def __init__(self, kind: str, key: str) -> None:
        super().__init__(f"no {kind} on the book with key {key!r}")
        self.kind = kind
        self.key = key


class DuplicateError(ShopError):
    """A record would collide with one already on the book."""

    def __init__(self, kind: str, key: str) -> None:
        super().__init__(f"{kind} {key!r} is already on the book")
        self.kind = kind
        self.key = key


class RuleError(ShopError):
    """The values are well formed but the shop's rules forbid the operation.

    An expired reference standard, a test point that does not belong to the
    sequence being run, an adjustment reaching further back than the tariff
    allows. The message names the rule, not the field.
    """


class StateError(ShopError):
    """A record is in the wrong state for what was asked of it.

    Scrapping a meter that is still set at a service point, testing a meter that
    was never received, closing a work order with an open test on it.
    """


class ConfigError(ShopError):
    """The book itself is wrong: a missing migration, an unreadable schema."""


__all__ = [
    "BadInputError",
    "ConfigError",
    "DuplicateError",
    "NotFoundError",
    "RuleError",
    "ShopError",
    "StateError",
]
