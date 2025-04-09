from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from kilodial.errors import BadInputError, RuleError
from kilodial.install.point import MeterSet, ServicePoint
from kilodial.model.form import Service


def point(**over: object) -> ServicePoint:
    args: dict[str, object] = {
        "account": "44-9021",
        "address": "18 Fenwick Row",
        "service": Service.SINGLE_PHASE_3W,
        "voltage": "240",
        "rate_code": "R1",
        "energised": "2011-06-14",
    }
    args.update(over)
    return ServicePoint.build(str(args.pop("code", "SP-1042")), **args)  # type: ignore[arg-type]


def a_set(**over: object) -> MeterSet:
    args: dict[str, object] = {
        "programmed_multiplier": "1",
        "set_on": "2019-05-02",
    }
    args.update(over)
    return MeterSet.build(
        str(args.pop("point_code", "SP-1042")),
        str(args.pop("meter_serial", "84-119302")),
        **args,
    )


def test_a_service_point_is_tidied_and_upper_cased() -> None:
    p = point(code=" sp-1042 ", account="44-9021", rate_code="r1")
    assert p.code == "SP-1042"
    assert p.rate_code == "R1"
    assert str(p) == "SP-1042 18 Fenwick Row (R1)"


def test_a_service_point_stays_live_until_it_is_disconnected() -> None:
    assert point().was_live_on("2099-01-01")
    closed = point(disconnected="2020-03-01")
    assert closed.was_live_on("2020-03-01")
    assert not closed.was_live_on("2020-03-02")
    assert closed.live.end == date(2020, 3, 1)


def test_a_point_cannot_be_disconnected_before_it_was_energised() -> None:
    with pytest.raises(RuleError, match="disconnected before"):
        point(energised="2011-06-14", disconnected="2010-01-01")


def test_a_service_that_is_not_a_service() -> None:
    with pytest.raises(BadInputError, match="Service"):
        point(service="1P3W")


@pytest.mark.parametrize("bad", ["", "   ", None, "x" * 100])
def test_bad_addresses(bad: object) -> None:
    with pytest.raises(BadInputError):
        point(address=bad)


def test_a_self_contained_set() -> None:
    s = a_set()
    assert not s.is_transformer_rated
    assert s.is_current
    assert s.register_multiplier == Decimal("1")
    assert str(s) == "84-119302 at SP-1042 from 2019-05-02 x1"


def test_a_transformer_rated_set() -> None:
    s = a_set(ct_serial="ct-8841", vt_serial="vt-2201", programmed_multiplier="800")
    assert s.is_transformer_rated
    assert s.ct_serial == "CT-8841"
    assert s.vt_serial == "VT-2201"


def test_a_set_with_only_a_current_transformer_is_still_transformer_rated() -> None:
    assert a_set(ct_serial="CT-8841", programmed_multiplier="40").is_transformer_rated


@pytest.mark.parametrize("bad", ["0", "-1", "lots", "1000000"])
def test_bad_multipliers(bad: object) -> None:
    with pytest.raises(BadInputError):
        a_set(programmed_multiplier=bad)
    with pytest.raises(BadInputError):
        a_set(register_multiplier=bad)


def test_pulling_a_set() -> None:
    s = a_set().pulled_on("2025-03-01")
    assert not s.is_current
    assert s.removed_on == date(2025, 3, 1)
    assert s.was_set_on("2025-03-01")
    assert not s.was_set_on("2025-03-02")


def test_pulling_a_set_that_is_already_pulled() -> None:
    s = a_set().pulled_on("2025-03-01")
    with pytest.raises(RuleError, match="already pulled"):
        s.pulled_on("2025-04-01")


def test_pulling_a_set_before_it_was_set() -> None:
    with pytest.raises(RuleError, match="before it was set"):
        a_set().pulled_on("2018-01-01")
    with pytest.raises(RuleError, match="before it was set"):
        a_set(removed_on="2018-01-01")


def test_the_span_of_a_current_set_is_open() -> None:
    assert a_set().span.is_open
    assert not a_set(removed_on="2025-03-01").span.is_open
