from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from kilodial.errors import BadInputError, RuleError
from kilodial.model.bench import Bench, ReferenceStandard
from kilodial.model.device import DeviceType
from kilodial.model.form import Technology


def a_standard(**over: object) -> ReferenceStandard:
    args: dict[str, object] = {
        "serial": "rs-5511",
        "maker": "Radian",
        "model_code": "RD-23",
        "certificate": "nvlap-88214",
        "certified_on": "2024-11-04",
        "certificate_due": "2025-11-04",
        "uncertainty": "0.02",
    }
    args.update(over)
    return ReferenceStandard.build(args.pop("serial"), **args)


def a_bench(**over: object) -> Bench:
    args: dict[str, object] = {
        "code": "b2",
        "name": "north wall three phase",
        "positions": 8,
        "standard_serial": "rs-5511",
        "max_amperes": "100",
        "max_volts": "480",
        "polyphase": True,
        "installed": "2018-03-01",
    }
    args.update(over)
    return Bench.build(args.pop("code"), args.pop("name"), **args)  # type: ignore[arg-type]


def a_device(**over: object) -> DeviceType:
    args: dict[str, object] = {
        "form_code": "2S",
        "class_code": "200",
        "voltage": "240",
        "kh": "7.2",
        "technology": Technology.INDUCTION,
        "register_ratio": "100",
        "introduced": "2004-05-01",
    }
    args.update(over)
    return DeviceType.build("Halvern", "R4S", **args)  # type: ignore[arg-type]


def test_a_standard_carries_its_window() -> None:
    s = a_standard()
    assert s.serial == "RS-5511"
    assert s.certificate == "NVLAP-88214"
    assert s.window.start == date(2024, 11, 4)
    assert s.is_valid_on("2025-03-04")
    assert not s.is_valid_on("2025-11-05")
    assert s.is_valid_on("2025-11-04")


def test_days_left_goes_negative() -> None:
    s = a_standard()
    assert s.days_left_on("2025-11-04") == 0
    assert s.days_left_on("2025-11-14") == -10
    assert s.days_left_on("2025-10-30") == 5


def test_a_certificate_that_expires_before_it_starts() -> None:
    with pytest.raises(RuleError, match="run out after"):
        a_standard(certified_on="2025-01-01", certificate_due="2024-01-01")


def test_uncertainty_has_to_be_shop_grade() -> None:
    assert a_standard(uncertainty="0.1").uncertainty == Decimal("0.1")
    with pytest.raises(RuleError, match="looser than"):
        a_standard(uncertainty="0.5")
    with pytest.raises(BadInputError):
        a_standard(uncertainty="0")
    with pytest.raises(BadInputError):
        a_standard(uncertainty="tight")


def test_str_of_a_standard_names_the_certificate() -> None:
    assert str(a_standard()) == "RS-5511 cert NVLAP-88214 to 2025-11-04"


def test_a_bench_is_upper_cased_and_counted() -> None:
    b = a_bench()
    assert b.code == "B2"
    assert b.positions == 8
    assert str(b) == "B2 north wall three phase (8 positions)"


@pytest.mark.parametrize("bad", [0, 65, "eight", 8.0, True])
def test_bad_position_counts(bad: object) -> None:
    with pytest.raises(BadInputError):
        a_bench(positions=bad)


def test_bench_service_life() -> None:
    assert a_bench().is_available_on("2030-01-01")
    b = a_bench(removed="2022-06-30")
    assert not b.is_available_on("2022-07-01")
    with pytest.raises(RuleError, match="come out before"):
        a_bench(installed="2020-01-01", removed="2018-01-01")


def test_a_single_phase_bench_refuses_a_polyphase_meter() -> None:
    bench = a_bench(polyphase=False)
    poly = a_device(form_code="16S", class_code="320")
    assert not bench.can_hold(poly)
    with pytest.raises(RuleError, match="single phase"):
        bench.refuse_unless_it_can_hold(poly)


def test_a_bench_that_cannot_reach_the_current() -> None:
    bench = a_bench(max_amperes="10")
    with pytest.raises(RuleError, match="tops out at 10 A"):
        bench.refuse_unless_it_can_hold(a_device())


def test_a_bench_that_cannot_reach_the_voltage() -> None:
    bench = a_bench(max_volts="120")
    with pytest.raises(RuleError, match="tops out at 120 V"):
        bench.refuse_unless_it_can_hold(a_device(voltage="277"))


def test_a_bench_that_can_hold_it_says_nothing() -> None:
    bench = a_bench()
    assert bench.can_hold(a_device())
    bench.refuse_unless_it_can_hold(a_device())


@pytest.mark.parametrize("bad", ["", None, "x" * 80])
def test_bad_bench_names(bad: object) -> None:
    with pytest.raises(BadInputError):
        a_bench(name=bad)
