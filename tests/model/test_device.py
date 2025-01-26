from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from kilodial.errors import BadInputError, RuleError
from kilodial.model.device import DeviceType
from kilodial.model.form import MeterClass, Technology


def a_type(**over: object) -> DeviceType:
    args: dict[str, object] = {
        "manufacturer": "Halvern",
        "model_code": "R4S",
        "form_code": "2S",
        "class_code": "200",
        "voltage": "240",
        "kh": "7.2",
        "technology": Technology.INDUCTION,
        "register_ratio": "100",
        "introduced": "2004-05-01",
    }
    args.update(over)
    return DeviceType.build(
        args.pop("manufacturer"),
        args.pop("model_code"),
        **args,  # type: ignore[arg-type]
    )


def test_the_key_is_maker_and_model() -> None:
    assert a_type().key == "Halvern/R4S"
    assert str(a_type()) == "Halvern/R4S form 2S CL200"


def test_names_are_tidied() -> None:
    assert a_type(manufacturer="  Halvern   Meter  ").manufacturer == "Halvern Meter"


@pytest.mark.parametrize("bad", ["", "   ", None, 4, "x" * 60])
def test_bad_manufacturer_names(bad: object) -> None:
    with pytest.raises(BadInputError):
        a_type(manufacturer=bad)


def test_test_currents_come_off_the_class() -> None:
    d = a_type()
    assert d.test_amperes.value == Decimal("30.000")
    assert d.light_load_amperes.value == Decimal("3.000")
    assert d.power_factor_amperes.value == Decimal("15.000")


def test_a_class_20_meter_needs_a_transformer_rated_form() -> None:
    with pytest.raises(RuleError, match="transformer rated class"):
        a_type(class_code="20", form_code="2S")
    ok = a_type(class_code="20", form_code="9S")
    assert ok.is_transformer_rated
    assert ok.test_amperes.value == Decimal("2.500")


def test_a_self_contained_meter_is_not_transformer_rated() -> None:
    assert not a_type().is_transformer_rated


def test_an_induction_meter_needs_a_register_ratio() -> None:
    with pytest.raises(RuleError, match="register ratio"):
        a_type(register_ratio=None)


def test_a_solid_state_meter_does_not() -> None:
    d = a_type(technology=Technology.SOLID_STATE, register_ratio=None, kh="1.0")
    assert d.register_ratio is None
    assert not d.is_disc


@pytest.mark.parametrize("bad", ["0", "-1", "lots"])
def test_bad_register_ratios(bad: object) -> None:
    with pytest.raises(BadInputError):
        a_type(register_ratio=bad)


@pytest.mark.parametrize("bad", ["0.001", "200", "big", None])
def test_bad_watthour_constants(bad: object) -> None:
    with pytest.raises(BadInputError):
        a_type(kh=bad)


def test_a_technology_that_is_not_one() -> None:
    with pytest.raises(BadInputError, match="Technology"):
        a_type(technology="disc")


def test_service_life_and_currency() -> None:
    d = a_type(introduced="2004-05-01", retired="2016-12-31")
    assert d.was_current_on("2010-01-01")
    assert not d.was_current_on("2017-01-01")
    assert d.service_life.end == date(2016, 12, 31)
    assert a_type().service_life.is_open


def test_a_type_cannot_retire_before_it_arrived() -> None:
    with pytest.raises(RuleError, match="retire before"):
        a_type(introduced="2010-01-01", retired="2004-01-01")


def test_demand_capability_defaults_off() -> None:
    assert not a_type().demand_capable
    assert a_type(demand_capable=True).demand_capable


def test_elements_come_off_the_form() -> None:
    assert a_type().elements == Decimal("1")
    assert a_type(form_code="16S", class_code=MeterClass.CL320).elements == Decimal("3")
