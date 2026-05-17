from __future__ import annotations

from decimal import Decimal

import pytest

from kilodial.errors import BadInputError
from kilodial.units.registration import Registration


def test_string_and_decimal_agree() -> None:
    assert Registration("99.87") == Registration(Decimal("99.87"))
    assert hash(Registration("99.87")) == hash(Registration(Decimal("99.8700")))


def test_a_trailing_percent_sign_is_accepted() -> None:
    assert Registration("100.24%") == Registration("100.24")


def test_float_does_not_leak_binary_noise() -> None:
    assert Registration(99.87).percent == Decimal("99.8700")


@pytest.mark.parametrize("bad", ["", "ninety", "9.9.9", None, object()])
def test_rubbish_is_refused(bad: object) -> None:
    with pytest.raises(BadInputError):
        Registration(bad)


def test_negative_is_refused() -> None:
    with pytest.raises(BadInputError, match="negative"):
        Registration("-1")


def test_nominal_is_exactly_a_hundred() -> None:
    r = Registration.nominal()
    assert r.percent == Decimal("100.0000")
    assert r.error == 0
    assert not r.is_fast
    assert not r.is_slow


def test_from_readings() -> None:
    r = Registration.from_readings("999.4", "1000")
    assert r.percent == Decimal("99.9400")
    assert r.is_slow


def test_from_readings_refuses_a_zero_reference() -> None:
    with pytest.raises(BadInputError, match="above zero"):
        Registration.from_readings("10", "0")


def test_from_readings_refuses_a_negative_meter_reading() -> None:
    with pytest.raises(BadInputError, match="cannot be negative"):
        Registration.from_readings("-1", "10")


def test_error_sign_follows_fast_and_slow() -> None:
    assert Registration("100.62").error == Decimal("0.6200")
    assert Registration("100.62").is_fast
    assert Registration("98.40").error == Decimal("-1.6000")
    assert Registration("98.40").is_slow


def test_correction_factor_undoes_the_error() -> None:
    assert Registration("100").correction_factor == Decimal("1.0000")
    assert Registration("50").correction_factor == Decimal("2.0000")


def test_a_dead_meter_has_no_correction_factor() -> None:
    with pytest.raises(BadInputError, match="registering nothing"):
        _ = Registration("0").correction_factor


@pytest.mark.parametrize(
    ("value", "plausible"),
    [("100.10", True), ("10", True), ("400", True), ("9.99", False), ("400.01", False)],
)
def test_plausibility_band(value: str, plausible: bool) -> None:
    assert Registration(value).is_plausible is plausible


def test_within_is_inclusive_at_the_edge() -> None:
    assert Registration("102").within("2")
    assert Registration("98").within("2")
    assert not Registration("102.01").within("2")


def test_within_refuses_a_negative_band() -> None:
    with pytest.raises(BadInputError, match="tolerance band"):
        Registration("100").within("-1")


def test_composition_is_series_multiplication() -> None:
    meter = Registration("100.30")
    ct = Registration("99.80")
    assert meter.compose(ct).percent == Decimal("100.0994")


def test_composition_with_nominal_changes_nothing() -> None:
    r = Registration("99.42")
    assert r.compose(Registration.nominal()) == r


def test_rounded_and_str() -> None:
    r = Registration("99.8765")
    assert r.rounded(2) == Decimal("99.88")
    assert r.rounded(0) == Decimal("100")
    assert str(r) == "99.88%"


def test_rounded_refuses_daft_places() -> None:
    with pytest.raises(BadInputError, match="0 and 4"):
        Registration("100").rounded(7)


def test_ordering() -> None:
    values = [Registration("101"), Registration("99"), Registration("100")]
    assert [r.percent for r in sorted(values)] == [
        Decimal("99.0000"),
        Decimal("100.0000"),
        Decimal("101.0000"),
    ]


def test_equality_against_another_type() -> None:
    assert Registration("100") != "100"


def test_an_integer_percentage() -> None:
    assert Registration(100).percent == Decimal("100.0000")


def test_ordering_against_another_type() -> None:
    with pytest.raises(TypeError):
        _ = Registration("100") < "100"
