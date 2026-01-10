from __future__ import annotations

from datetime import date

import click
import pytest

from kilodial.cli.window import (
    BOTH_ENDS,
    counted_from,
    require_span,
    span_of,
    window_options,
)


def test_neither_end_is_no_window() -> None:
    assert span_of(None, None) is None


def test_both_ends_make_a_span() -> None:
    span = span_of("2025-01-01", "2025-12-31")
    assert span is not None
    assert span.start == date(2025, 1, 1)
    assert span.end == date(2025, 12, 31)


@pytest.mark.parametrize(("first", "last"), [("2025-01-01", None), (None, "2025-12-31")])
def test_one_end_is_a_mistake(first: str | None, last: str | None) -> None:
    with pytest.raises(click.BadParameter, match=BOTH_ENDS):
        span_of(first, last)


def test_a_window_typed_backwards_is_refused() -> None:
    with pytest.raises(click.BadParameter, match="cannot end"):
        span_of("2025-12-31", "2025-01-01")


def test_a_window_that_is_not_dates() -> None:
    with pytest.raises(click.BadParameter, match="not an ISO date"):
        span_of("last spring", "2025-12-31")


def test_a_required_window() -> None:
    assert require_span("2025-01-01", "2025-12-31").days == 365
    with pytest.raises(click.BadParameter, match=BOTH_ENDS):
        require_span(None, None)


def test_counted_from() -> None:
    assert counted_from("2025-01-01", "--due-within") == "2025-01-01"
    with pytest.raises(click.BadParameter, match="--due-within needs --on"):
        counted_from(None, "--due-within")


def test_the_option_pair_is_added_to_a_command() -> None:
    @click.command()
    @window_options("start of the season")
    def sample(first: str | None, last: str | None) -> None:
        click.echo(f"{first} {last}")

    names = {opt for param in sample.params for opt in param.opts}
    assert "--from" in names
    assert "--to" in names
    from click.testing import CliRunner

    result = CliRunner().invoke(sample, ["--from", "a", "--to", "b"])
    assert result.output.strip() == "a b"
