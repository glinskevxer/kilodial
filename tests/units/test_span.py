from __future__ import annotations

from datetime import date

import pytest

from kilodial.errors import BadInputError
from kilodial.units.span import DateSpan, add_months, parse_date


def test_parse_date_takes_a_date_or_a_string() -> None:
    assert parse_date("2025-03-04") == date(2025, 3, 4)
    assert parse_date(date(2025, 3, 4)) == date(2025, 3, 4)


@pytest.mark.parametrize("bad", ["4 March", "2025-13-01", None, 20250304])
def test_parse_date_refuses_the_rest(bad: object) -> None:
    with pytest.raises(BadInputError):
        parse_date(bad)


@pytest.mark.parametrize(
    ("start", "months", "expected"),
    [
        ("2025-01-31", 1, "2025-02-28"),
        ("2024-01-31", 1, "2024-02-29"),
        ("2025-01-15", 12, "2026-01-15"),
        ("2025-03-31", -1, "2025-02-28"),
        ("2025-01-10", 0, "2025-01-10"),
    ],
)
def test_add_months_clamps_at_the_end_of_a_short_month(
    start: str, months: int, expected: str
) -> None:
    assert add_months(parse_date(start), months).isoformat() == expected


def test_a_span_cannot_end_before_it_starts() -> None:
    with pytest.raises(BadInputError, match="cannot end"):
        DateSpan("2025-03-01", "2025-02-01")


def test_a_single_day_span() -> None:
    span = DateSpan("2025-03-04", "2025-03-04")
    assert span.days == 1
    assert span.contains("2025-03-04")


def test_open_spans() -> None:
    span = DateSpan("2025-03-04")
    assert span.is_open
    assert span.contains("2099-01-01")
    assert not span.contains("2025-03-03")
    with pytest.raises(BadInputError, match="no day count"):
        _ = span.days


def test_days_is_inclusive() -> None:
    assert DateSpan("2025-01-01", "2025-01-31").days == 31


def test_overlap_and_intersect() -> None:
    a = DateSpan("2025-01-01", "2025-06-30")
    b = DateSpan("2025-06-30", "2025-12-31")
    c = DateSpan("2025-07-01", "2025-12-31")
    assert a.overlaps(b)
    assert not a.overlaps(c)
    cut = a.intersect(b)
    assert cut is not None
    assert cut.start == date(2025, 6, 30)
    assert cut.end == date(2025, 6, 30)
    assert a.intersect(c) is None


def test_intersect_with_an_open_span() -> None:
    closed = DateSpan("2025-01-01", "2025-12-31")
    open_span = DateSpan("2025-06-01")
    cut = closed.intersect(open_span)
    assert cut is not None
    assert cut.start == date(2025, 6, 1)
    assert cut.end == date(2025, 12, 31)
    both_open = DateSpan("2025-01-01").intersect(DateSpan("2025-06-01"))
    assert both_open is not None
    assert both_open.is_open


def test_clipped_to_refuses_a_miss() -> None:
    a = DateSpan("2025-01-01", "2025-01-31")
    assert a.clipped_to(DateSpan("2025-01-15", "2025-02-15")).days == 17
    with pytest.raises(BadInputError, match="does not overlap"):
        a.clipped_to(DateSpan("2025-03-01", "2025-03-31"))


def test_by_month_covers_the_span_exactly() -> None:
    span = DateSpan("2025-01-15", "2025-04-03")
    pieces = span.by_month()
    assert [str(p) for p in pieces] == [
        "2025-01-15 to 2025-01-31",
        "2025-02-01 to 2025-02-28",
        "2025-03-01 to 2025-03-31",
        "2025-04-01 to 2025-04-03",
    ]
    assert sum(p.days for p in pieces) == span.days


def test_by_month_of_a_single_month() -> None:
    span = DateSpan("2025-05-02", "2025-05-09")
    assert [str(p) for p in span.by_month()] == ["2025-05-02 to 2025-05-09"]


def test_by_month_refuses_an_open_span() -> None:
    with pytest.raises(BadInputError, match="open ended"):
        DateSpan("2025-01-01").by_month()


def test_shifted_back() -> None:
    span = DateSpan("2025-03-31", "2025-05-31").shifted_back(1)
    assert str(span) == "2025-02-28 to 2025-04-30"
    assert DateSpan("2025-03-01").shifted_back(2).is_open
    with pytest.raises(BadInputError, match="whole number"):
        span.shifted_back(-1)


def test_closed_at() -> None:
    assert str(DateSpan("2025-01-01").closed_at("2025-02-01")) == "2025-01-01 to 2025-02-01"
    with pytest.raises(BadInputError, match="already closed"):
        DateSpan("2025-01-01", "2025-02-01").closed_at("2025-03-01")


def test_str_of_an_open_span() -> None:
    assert str(DateSpan("2025-01-01")) == "2025-01-01 to open"
