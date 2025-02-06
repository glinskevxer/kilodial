from __future__ import annotations

from decimal import Decimal

import pytest

from kilodial.errors import BadInputError
from kilodial.model.form import MeterClass
from kilodial.model.run import PointKind, RunKind
from kilodial.testing.tolerance import BANDS, band_for
from kilodial.units.registration import Registration


def test_every_run_kind_has_a_band() -> None:
    assert set(BANDS) == set(RunKind)


def test_as_found_is_the_widest_band() -> None:
    widths = {kind: band_for(kind).weighted for kind in RunKind}
    assert widths[RunKind.AS_FOUND] == Decimal("2.0")
    assert widths[RunKind.AS_FOUND] == widths[RunKind.REFEREE]
    assert widths[RunKind.ACCEPTANCE] < widths[RunKind.AS_LEFT] < widths[RunKind.AS_FOUND]


def test_a_meter_can_pass_as_found_and_fail_as_left() -> None:
    reading = Registration("101.4")
    assert band_for(RunKind.AS_FOUND).accepts(reading)
    assert not band_for(RunKind.AS_LEFT).accepts(reading)


def test_the_edge_of_the_band_is_inside_it() -> None:
    assert band_for(RunKind.AS_FOUND).accepts(Registration("102.00"))
    assert not band_for(RunKind.AS_FOUND).accepts(Registration("102.01"))


def test_light_load_gets_a_wider_band_than_the_other_points() -> None:
    band = band_for(RunKind.AS_FOUND)
    assert band.limit_for(PointKind.LIGHT_LOAD) == Decimal("4.0")
    assert band.limit_for(PointKind.FULL_LOAD) == Decimal("3.0")
    assert band.limit_for(PointKind.POWER_FACTOR) == Decimal("3.0")
    assert band.accepts_point(PointKind.LIGHT_LOAD, Registration("96.5"))
    assert not band.accepts_point(PointKind.FULL_LOAD, Registration("96.5"))


def test_a_transformer_class_meter_is_held_tighter() -> None:
    ordinary = band_for(RunKind.AS_FOUND, MeterClass.CL200)
    tight = band_for(RunKind.AS_FOUND, MeterClass.CL20)
    assert ordinary.weighted == Decimal("2.0")
    assert tight.weighted == Decimal("1.33")
    assert tight.per_point == Decimal("2.00")
    assert tight.light_load == Decimal("2.67")


def test_the_tight_band_never_collapses_below_the_floor() -> None:
    tight = band_for(RunKind.ACCEPTANCE, MeterClass.CL10)
    assert tight.weighted == Decimal("0.33")
    assert tight.weighted >= Decimal("0.25")


def test_leaving_the_class_out_gives_the_ordinary_band() -> None:
    assert band_for(RunKind.AS_FOUND) == band_for(RunKind.AS_FOUND, MeterClass.CL320)


def test_creep_is_never_allowed() -> None:
    assert not any(band_for(kind).creep_allowed for kind in RunKind)


def test_bad_arguments() -> None:
    with pytest.raises(BadInputError, match="RunKind"):
        band_for("as found")
    with pytest.raises(BadInputError, match="MeterClass"):
        band_for(RunKind.AS_FOUND, "CL200")


def test_str_of_a_band() -> None:
    assert str(band_for(RunKind.AS_LEFT)) == "+/-1.0 percent weighted, +/-2.0 per point"
