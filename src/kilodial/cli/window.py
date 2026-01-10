"""The date window options, in one place because they were in six.

Five commands take a ``--from`` and ``--to`` pair and every one of them wrote out
the same three lines: check both were given, complain when only one was, build a
span. The complaints had already drifted into two different wordings, which is
how somebody grepping for the message ends up thinking there are two features.

There is one more thing worth having here and it is the reason this is a module
rather than a copied helper. A window whose end is before its start is a typo
that produces an empty result, and an empty result reads as "there is nothing"
rather than as "you typed it backwards". The span refuses it.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeVar

import click

from kilodial.errors import ShopError
from kilodial.units.span import DateSpan

_F = TypeVar("_F", bound=Callable[..., Any])

BOTH_ENDS = "a window needs both --from and --to"
COUNT_FROM = "{option} needs --on to count from"


def window_options(help_first: str = "start of the window") -> Callable[[_F], _F]:
    """The ``--from`` and ``--to`` pair, so the two cannot drift apart."""

    def wrap(command: _F) -> _F:
        command = click.option("--to", "last", default=None, help="end of the window")(command)
        return click.option("--from", "first", default=None, help=help_first)(command)

    return wrap


def span_of(first: str | None, last: str | None) -> DateSpan | None:
    """A span from a pair of options, or nothing when neither was given."""
    if first is None and last is None:
        return None
    if first is None or last is None:
        raise click.BadParameter(BOTH_ENDS)
    try:
        return DateSpan(first, last)
    except ShopError as exc:
        raise click.BadParameter(str(exc)) from exc


def require_span(first: str | None, last: str | None) -> DateSpan:
    """The same, for a command that cannot work without one."""
    span = span_of(first, last)
    if span is None:
        raise click.BadParameter(BOTH_ENDS)
    return span


def counted_from(day: str | None, option: str) -> str:
    """Refuse a lookahead option that has no day to count from."""
    if day is None:
        raise click.BadParameter(COUNT_FROM.format(option=option))
    return day


__all__ = [
    "BOTH_ENDS",
    "COUNT_FROM",
    "counted_from",
    "require_span",
    "span_of",
    "window_options",
]
