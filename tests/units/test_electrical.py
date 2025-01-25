from __future__ import annotations

from decimal import Decimal

import pytest

from kilodial.errors import BadInputError
from kilodial.units.electrical import (
    Amperes,
    PowerFactor,
    Sense,
    Volts,
    WattHours,
)


def test_amperes_round_to_a_milliamp() -> None:
    assert Amperes("2.4996").value == Decimal("2.500")
    assert str(Amperes(30)) == "30 A"


@pytest.mark.parametrize("bad", ["-1", "401", "lots", None])
def test_bad_currents(bad: object) -> None:
    with pytest.raises(BadInputError):
        Amperes(bad)


def test_current_as_a_percentage_of_the_test_ampere_rating() -> None:
    assert Amperes(30).as_percent_of(Amperes(30)) == Decimal("100.00")
    assert Amperes("3").as_percent_of(Amperes(30)) == Decimal("10.00")
    assert Amperes("15").as_percent_of(Amperes(30)) == Decimal("50.00")


def test_percentage_of_a_zero_rating_is_refused() -> None:
    with pytest.raises(BadInputError, match="above zero"):
        Amperes(1).as_percent_of(Amperes(0))


def test_volts() -> None:
    assert Volts("240").value == Decimal("240.00")
    assert str(Volts(120)) == "120 V"


@pytest.mark.parametrize("bad", ["0", "-120", "601", "mains"])
def test_bad_voltages(bad: object) -> None:
    with pytest.raises(BadInputError):
        Volts(bad)


def test_unity_power_factor_collapses_its_sense() -> None:
    assert PowerFactor(1, Sense.LAGGING) == PowerFactor.unity()
    assert PowerFactor.unity().is_unity
    assert str(PowerFactor.unity()) == "1.0 PF"


def test_lagging_and_leading_are_different_values() -> None:
    assert PowerFactor.lagging("0.5") != PowerFactor.leading("0.5")
    assert str(PowerFactor.lagging("0.5")) == "0.5 PF lagging"


def test_a_power_factor_below_one_needs_a_sense() -> None:
    with pytest.raises(BadInputError, match="lead or lag"):
        PowerFactor("0.5")


@pytest.mark.parametrize("bad", ["0", "-0.5", "1.01", "half"])
def test_bad_power_factors(bad: object) -> None:
    with pytest.raises(BadInputError):
        PowerFactor(bad, Sense.LAGGING)


def test_a_sense_that_is_not_a_sense() -> None:
    with pytest.raises(BadInputError, match="Sense"):
        PowerFactor("0.5", "lagging")  # type: ignore[arg-type]


def test_watthours_from_revolutions() -> None:
    wh = WattHours.from_revolutions("7.2", 100)
    assert wh.value == Decimal("720.000")
    assert str(wh) == "720 Wh"


@pytest.mark.parametrize(
    ("kh", "revs"),
    [("0", 10), ("-1", 10), ("7.2", -1), ("many", 10)],
)
def test_bad_revolution_maths(kh: object, revs: object) -> None:
    with pytest.raises(BadInputError):
        WattHours.from_revolutions(kh, revs)


def test_watthours_add() -> None:
    assert (WattHours("1.5") + WattHours("2.25")).value == Decimal("3.750")
    with pytest.raises(TypeError):
        _ = WattHours("1") + 1


def test_negative_energy_is_refused() -> None:
    with pytest.raises(BadInputError, match="cannot be negative"):
        WattHours("-1")
