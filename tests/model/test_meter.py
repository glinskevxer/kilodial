from __future__ import annotations

from datetime import date

import pytest

from kilodial.errors import BadInputError, StateError
from kilodial.model.meter import (
    BENCHABLE,
    TRANSITIONS,
    Meter,
    MeterState,
    normalise_serial,
)


def a_meter(**over: object) -> Meter:
    args: dict[str, object] = {"serial": "84-119302", "acquired": "2019-04-02"}
    args.update(over)
    return Meter.receive(
        args.pop("serial"),
        str(args.pop("device_key", "Halvern/R4S")),
        **args,  # type: ignore[arg-type]
    )


def test_serials_are_upper_cased_and_stripped() -> None:
    assert normalise_serial(" 84-119302 ") == "84-119302"
    assert normalise_serial("ab12cd") == "AB12CD"


@pytest.mark.parametrize("bad", ["", "a", "-1234", "way-too-long-a-serial-number", None, 84])
def test_bad_serials(bad: object) -> None:
    with pytest.raises(BadInputError):
        normalise_serial(bad)


def test_a_received_meter() -> None:
    m = a_meter()
    assert m.state is MeterState.RECEIVED
    assert m.acquired == date(2019, 4, 2)
    assert m.owner == "utility"
    assert m.seal is None
    assert m.is_in_shop
    assert not m.is_retired
    assert str(m) == "84-119302 (Halvern/R4S, received)"


@pytest.mark.parametrize("bad", ["", "  ", None, 7, "x" * 50])
def test_bad_owners(bad: object) -> None:
    with pytest.raises(BadInputError):
        a_meter(owner=bad)


def test_seals() -> None:
    m = a_meter(seal=" bx4471 ")
    assert m.seal == "BX4471"
    assert m.resealed(None).seal is None
    assert m.resealed("").seal is None


@pytest.mark.parametrize("bad", ["seal 4471", "x" * 20, 4471])
def test_bad_seals(bad: object) -> None:
    with pytest.raises(BadInputError):
        a_meter(seal=bad)


def test_the_ordinary_route_through_the_shop() -> None:
    m = a_meter()
    m = m.moved_to(MeterState.STOCK)
    m = m.moved_to(MeterState.SET)
    m = m.moved_to(MeterState.PULLED)
    m = m.moved_to(MeterState.STOCK)
    assert m.state is MeterState.STOCK


def test_a_move_that_is_not_allowed() -> None:
    m = a_meter().moved_to(MeterState.STOCK).moved_to(MeterState.SET)
    with pytest.raises(StateError, match="cannot go from set to repair"):
        m.moved_to(MeterState.REPAIR)


def test_moving_to_where_it_already_is() -> None:
    with pytest.raises(StateError, match="already received"):
        a_meter().moved_to(MeterState.RECEIVED)


def test_a_move_to_something_that_is_not_a_state() -> None:
    with pytest.raises(BadInputError, match="not a meter state"):
        a_meter().moved_to("stock")  # type: ignore[arg-type]


def test_scrapping_records_the_day() -> None:
    m = a_meter().moved_to(MeterState.SCRAP, on="2025-02-11")
    assert m.is_retired
    assert m.retired_on == date(2025, 2, 11)
    assert not m.is_in_shop


def test_scrapping_without_a_day_is_refused() -> None:
    with pytest.raises(BadInputError, match="needs the day"):
        a_meter().moved_to(MeterState.SCRAP)


def test_scrap_is_terminal() -> None:
    m = a_meter().moved_to(MeterState.SCRAP, on="2025-02-11")
    assert TRANSITIONS[MeterState.SCRAP] == frozenset()
    with pytest.raises(StateError):
        m.moved_to(MeterState.STOCK)


def test_a_lost_meter_can_turn_up_again() -> None:
    m = a_meter().moved_to(MeterState.STOCK).moved_to(MeterState.SET)
    m = m.moved_to(MeterState.LOST)
    assert m.moved_to(MeterState.PULLED).state is MeterState.PULLED


def test_benchable_states_are_the_ones_in_the_shop() -> None:
    assert MeterState.SET not in BENCHABLE
    assert MeterState.SCRAP not in BENCHABLE
    assert MeterState.LOST not in BENCHABLE
    assert MeterState.REPAIR in BENCHABLE


def test_every_state_has_a_transition_row() -> None:
    assert set(TRANSITIONS) == set(MeterState)
    for targets in TRANSITIONS.values():
        assert targets <= set(MeterState)
