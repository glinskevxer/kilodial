"""The small validators that were copied into six modules before this existed.

Every record in this package takes a handful of short strings off a command line
and has to decide whether they are usable. That check was written six times, and
the six copies had drifted: two of them collapsed internal whitespace and four
did not, so a bench called "north  wall" and one called "north wall" were
different benches depending on which constructor you went through.

One copy, and the limits stay on the caller where they belong.
"""

from __future__ import annotations

from decimal import Decimal

from kilodial.errors import BadInputError


def tidy(value: object, what: str, limit: int = 40) -> str:
    """A required short string: trimmed, internal whitespace collapsed, bounded."""
    if not isinstance(value, str):
        raise BadInputError(f"cannot read a {what} from {type(value).__name__}")
    text = " ".join(value.split())
    if not text:
        raise BadInputError(f"a {what} cannot be blank")
    if len(text) > limit:
        raise BadInputError(f"a {what} runs to {limit} characters at most")
    return text


def key(value: object, what: str, limit: int = 16) -> str:
    """The same, upper cased, for anything that is a key rather than prose."""
    return tidy(value, what, limit).upper()


def optional(value: object, what: str, limit: int = 240) -> str | None:
    """A string that may be missing, where blank and missing mean the same."""
    if value is None:
        return None
    text = value if isinstance(value, str) else None
    if text is None:
        raise BadInputError(f"cannot read a {what} from {type(value).__name__}")
    tidied = " ".join(text.split())
    if not tidied:
        return None
    if len(tidied) > limit:
        raise BadInputError(f"a {what} runs to {limit} characters at most")
    return tidied


def number(value: object, what: str) -> Decimal:
    """A Decimal from anything that can honestly be read as one."""
    if isinstance(value, Decimal):
        return value
    if isinstance(value, bool):
        raise BadInputError(f"cannot read a {what} from bool")
    if isinstance(value, int):
        return Decimal(value)
    if isinstance(value, float):
        return Decimal(repr(value))
    if isinstance(value, str):
        try:
            return Decimal(value.strip())
        except Exception:
            raise BadInputError(f"{value!r} is not a {what}") from None
    raise BadInputError(f"cannot read a {what} from {type(value).__name__}")


def positive(value: object, what: str, *, ceiling: Decimal | None = None) -> Decimal:
    """A Decimal that has to be above zero, and optionally under a ceiling."""
    got = number(value, what)
    if got <= 0:
        raise BadInputError(f"a {what} has to be above zero")
    if ceiling is not None and got > ceiling:
        raise BadInputError(f"a {what} of {got} is not a real installation")
    return got


__all__ = ["key", "number", "optional", "positive", "tidy"]
