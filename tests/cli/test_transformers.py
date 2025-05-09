from __future__ import annotations

import pytest

from kilodial.cli.transformers import load_factor
from kilodial.errors import BadInputError
from kilodial.units.electrical import Sense
from tests.cli.conftest import Invoke


def add(invoke: Invoke, serial: str = "CT-8841", *extra: str) -> None:
    invoke(
        "xfmr",
        "add",
        serial,
        "--kind",
        "current",
        "--maker",
        "Ferrand",
        "--ratio",
        "40",
        "--accuracy",
        "0.3",
        "--rcf",
        "1.0020",
        "--minutes",
        "12",
        "--tested",
        "2024-05-01",
        *extra,
    )


def test_reading_a_power_factor_the_way_it_is_said() -> None:
    assert load_factor("unity").is_unity
    assert load_factor("1.0").is_unity
    assert load_factor("0.5 lagging").sense is Sense.LAGGING
    assert load_factor("0.5 lag").sense is Sense.LAGGING
    assert load_factor("0.8 leading").sense is Sense.LEADING


@pytest.mark.parametrize("bad", ["0.5", "0.5 sideways", "half"])
def test_a_power_factor_nobody_would_say(bad: str) -> None:
    with pytest.raises(BadInputError):
        load_factor(bad)


def test_adding_a_transformer(started: Invoke) -> None:
    add(started)
    assert "CT-8841" in started("xfmr", "list").output


def test_a_kind_nobody_makes(started: Invoke) -> None:
    result = started(
        "xfmr",
        "add",
        "CT-8841",
        "--kind",
        "magnetic",
        "--maker",
        "Ferrand",
        "--ratio",
        "40",
        "--accuracy",
        "0.3",
        "--rcf",
        "1.0",
        "--tested",
        "2024-05-01",
        expect=2,
    )
    assert "is not one of" in result.output


def test_an_impossible_ratio_correction_factor(started: Invoke) -> None:
    result = started(
        "xfmr",
        "add",
        "CT-8841",
        "--kind",
        "current",
        "--maker",
        "Ferrand",
        "--ratio",
        "40",
        "--accuracy",
        "0.3",
        "--rcf",
        "3.0",
        "--tested",
        "2024-05-01",
        expect=2,
    )
    assert "not a transformer" in result.output


def test_retesting(started: Invoke) -> None:
    add(started)
    result = started(
        "xfmr",
        "retest",
        "CT-8841",
        "--rcf",
        "1.0041",
        "--minutes",
        "18",
        "--tested",
        "2026-05-01",
    )
    assert "1.0020 is now 1.0041" in result.output
    assert "2026-05-01" in started("xfmr", "list").output


def test_listing_by_kind_and_class(started: Invoke) -> None:
    add(started, "CT-8841")
    started(
        "xfmr",
        "add",
        "VT-2201",
        "--kind",
        "voltage",
        "--maker",
        "Ferrand",
        "--ratio",
        "20",
        "--accuracy",
        "0.6",
        "--rcf",
        "0.9990",
        "--tested",
        "2024-05-01",
    )
    assert "VT-2201" in started("xfmr", "list", "--kind", "voltage").output
    assert "CT-8841" not in started("xfmr", "list", "--kind", "voltage").output
    assert "VT-2201" in started("xfmr", "list", "--accuracy", "0.6").output


def test_listing_what_is_overdue(started: Invoke) -> None:
    add(started, "CT-8841")
    assert "CT-8841" in started("xfmr", "list", "--tested-before", "2026-01-01").output
    assert "CT-8841" not in started("xfmr", "list", "--tested-before", "2020-01-01").output


def test_checking_a_transformer_at_unity(started: Invoke) -> None:
    add(started)
    result = started("xfmr", "check", "CT-8841")
    assert "holds class" in result.output
    assert "yes" in result.output


def test_a_transformer_that_fails_only_on_a_lagging_load(started: Invoke) -> None:
    started(
        "xfmr",
        "add",
        "CT-9001",
        "--kind",
        "current",
        "--maker",
        "Ferrand",
        "--ratio",
        "40",
        "--accuracy",
        "0.3",
        "--rcf",
        "1.0029",
        "--minutes",
        "-60",
        "--tested",
        "2024-05-01",
    )
    started("xfmr", "check", "CT-9001")
    result = started("xfmr", "check", "CT-9001", "--pf", "0.5 lagging", expect=1)
    assert "holds class" in result.output


def test_checking_something_that_is_not_there(started: Invoke) -> None:
    result = started("xfmr", "check", "CT-0000", expect=2)
    assert "no instrument transformer" in result.output


def test_where_a_transformer_has_been(started: Invoke) -> None:
    add(started)
    result = started("xfmr", "where", "CT-8841")
    assert result.output.splitlines()[0].startswith("point")
