from __future__ import annotations

from decimal import Decimal

import pytest

from kilodial.errors import BadInputError
from kilodial.model.form import (
    FORMS,
    MeterClass,
    Mounting,
    Service,
    form,
    meter_class,
)


def test_lookup_is_case_and_space_insensitive() -> None:
    assert form(" 2s ") is form("2S")
    assert form("2S").code == "2S"


@pytest.mark.parametrize("bad", ["99Z", "", None, 2])
def test_unknown_forms_are_refused(bad: object) -> None:
    with pytest.raises(BadInputError):
        form(bad)


def test_the_residential_workhorse() -> None:
    f = form("2S")
    assert f.elements == Decimal("1")
    assert f.service is Service.SINGLE_PHASE_3W
    assert f.is_self_contained
    assert not f.is_polyphase
    assert f.mounting is Mounting.SOCKET


def test_a_transformer_rated_polyphase_form() -> None:
    f = form("9S")
    assert f.elements == Decimal("3")
    assert f.transformer_rated
    assert not f.is_self_contained
    assert f.is_polyphase


def test_the_two_and_a_half_element_form() -> None:
    assert form("36S").elements == Decimal("2.5")


def test_bottom_connected_forms_exist() -> None:
    assert form("10A").mounting is Mounting.BOTTOM
    assert form("29A").mounting is Mounting.BOTTOM


def test_every_form_code_is_its_own_key() -> None:
    for code, f in FORMS.items():
        assert f.code == code


def test_network_forms_count_as_polyphase() -> None:
    assert form("12S").service is Service.NETWORK_3W
    assert form("12S").is_polyphase


def test_str_of_a_form_is_its_code() -> None:
    assert str(form("16S")) == "16S"
    assert str(Service.THREE_PHASE_4W_WYE) == "3P4WY"
    assert str(Mounting.SOCKET) == "socket"


def test_classes_carry_their_test_current() -> None:
    assert MeterClass.CL200.test_amperes == Decimal("30")
    assert MeterClass.CL200.continuous == Decimal("200")
    assert MeterClass.CL20.test_amperes == Decimal("2.5")


def test_transformer_classes() -> None:
    assert MeterClass.CL20.is_transformer_class
    assert MeterClass.CL10.is_transformer_class
    assert not MeterClass.CL200.is_transformer_class


def test_class_lookup_takes_the_bare_number() -> None:
    assert meter_class("200") is MeterClass.CL200
    assert meter_class("cl320") is MeterClass.CL320
    assert meter_class(MeterClass.CL10) is MeterClass.CL10


@pytest.mark.parametrize("bad", ["CL15", "big", None, 200])
def test_unknown_classes_are_refused(bad: object) -> None:
    with pytest.raises(BadInputError):
        meter_class(bad)


def test_str_of_a_class_is_its_code() -> None:
    assert str(MeterClass.CL480) == "CL480"
