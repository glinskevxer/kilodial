from __future__ import annotations

from datetime import date

import pytest

from kilodial.errors import BadInputError, RuleError, StateError
from kilodial.orders.order import (
    Disposition,
    OrderKind,
    OrderState,
    Priority,
    WorkOrder,
    disposition_named,
    order_kind,
    priority_named,
)


def order(kind: object = "test", **over: object) -> WorkOrder:
    args: dict[str, object] = {"raised_on": "2025-03-04"}
    args.update(over)
    return WorkOrder.raise_order(
        str(args.pop("reference", "WO-1")),
        kind,
        str(args.pop("meter_serial", "84-119302")),
        **args,
    )


def test_lookups() -> None:
    assert order_kind("TEST") is OrderKind.TEST
    assert order_kind(OrderKind.REPAIR) is OrderKind.REPAIR
    assert priority_named("urgent") is Priority.URGENT
    assert disposition_named("scrapped") is Disposition.SCRAPPED
    assert disposition_named("RETURNED") is Disposition.RETURNED


@pytest.mark.parametrize("bad", ["fix", "", None, 4])
def test_bad_kinds(bad: object) -> None:
    with pytest.raises(BadInputError):
        order_kind(bad)
    with pytest.raises(BadInputError):
        priority_named(bad)
    with pytest.raises(BadInputError):
        disposition_named(bad)


def test_a_new_order_is_open() -> None:
    o = order()
    assert o.state is OrderState.OPEN
    assert o.is_live
    assert o.assigned_to is None
    assert str(o) == "WO-1 test 84-119302 (open)"


def test_the_due_date_comes_off_the_priority() -> None:
    assert order(priority="urgent").due_on == date(2025, 3, 6)
    assert order(priority="normal").due_on == date(2025, 4, 3)
    assert order(priority="low").due_on == date(2025, 6, 2)


def test_lateness_needs_the_order_to_be_open() -> None:
    o = order(priority="urgent")
    assert not o.is_late_on("2025-03-06")
    assert o.is_late_on("2025-03-07")
    closed = o.done(on="2025-03-05", run_reference="TR-1")
    assert not closed.is_late_on("2025-04-01")


def test_assigning() -> None:
    o = order().assigned("  R  Ellis ")
    assert o.state is OrderState.ASSIGNED
    assert o.assigned_to == "R Ellis"
    assert o.is_live


def test_a_test_order_closes_with_a_run() -> None:
    o = order("test").done(on="2025-03-14", run_reference="tr-1")
    assert o.state is OrderState.DONE
    assert o.run_reference == "TR-1"
    assert o.closed_on == date(2025, 3, 14)


def test_a_test_order_without_a_run() -> None:
    with pytest.raises(RuleError, match="closes with the run"):
        order("test").done(on="2025-03-14")


def test_a_repair_order_closes_with_a_disposition() -> None:
    o = order("repair").done(on="2025-03-14", disposition="scrapped")
    assert o.disposition is Disposition.SCRAPPED


def test_a_repair_order_without_a_disposition() -> None:
    with pytest.raises(RuleError, match="what became of the meter"):
        order("repair").done(on="2025-03-14")


def test_evidence_that_does_not_belong_on_the_order() -> None:
    with pytest.raises(RuleError, match="does not carry a run"):
        order("receive").done(on="2025-03-14", run_reference="TR-1")
    with pytest.raises(RuleError, match="does not carry a disposition"):
        order("test").done(on="2025-03-14", run_reference="TR-1", disposition="scrapped")


def test_a_plain_order_closes_on_its_own() -> None:
    o = order("set", point_code="sp-1042").done(on="2025-03-14")
    assert o.state is OrderState.DONE
    assert o.point_code == "SP-1042"


def test_an_order_cannot_close_before_it_was_raised() -> None:
    with pytest.raises(RuleError, match="before it was raised"):
        order("receive").done(on="2025-01-01")


def test_closing_a_closed_order() -> None:
    o = order("receive").done(on="2025-03-14")
    with pytest.raises(StateError, match="already done"):
        o.done(on="2025-03-15")
    with pytest.raises(StateError):
        o.assigned("R Ellis")
    with pytest.raises(StateError):
        o.cancelled(on="2025-03-15", why="never mind")


def test_cancelling_needs_a_reason() -> None:
    o = order().cancelled(on="2025-03-10", why="  meter already scrapped ")
    assert o.state is OrderState.CANCELLED
    assert o.note == "meter already scrapped"
    assert not o.is_live
    with pytest.raises(RuleError, match="needs a reason"):
        order().cancelled(on="2025-03-10", why="   ")


def test_cancelling_keeps_the_original_note() -> None:
    o = order(note="pulled for the sample").cancelled(on="2025-03-10", why="duplicate")
    assert o.note == "pulled for the sample; duplicate"


def test_days_open() -> None:
    o = order()
    assert o.days_open("2025-03-14") == 10
    closed = o.done(on="2025-03-09", run_reference="TR-1")
    assert closed.days_open("2025-06-01") == 5


def test_which_kinds_want_what() -> None:
    assert OrderKind.TEST.needs_run
    assert not OrderKind.TEST.needs_disposition
    assert OrderKind.REPAIR.needs_disposition
    assert not OrderKind.RECEIVE.needs_run
    assert str(OrderKind.PULL) == "pull"
    assert str(Priority.HIGH) == "high"
    assert str(OrderState.DONE) == "done"
    assert str(Disposition.UNREPAIRABLE) == "unrepairable, held"
