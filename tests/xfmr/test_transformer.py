from __future__ import annotations

from decimal import Decimal

import pytest

from kilodial.errors import BadInputError, RuleError
from kilodial.units.electrical import PowerFactor
from kilodial.units.registration import Registration
from kilodial.xfmr.transformer import (
    AccuracyClass,
    InstrumentTransformer,
    TransformerKind,
    accuracy_class,
    tan_theta,
)

UNITY = PowerFactor.unity()
HALF_LAG = PowerFactor.lagging("0.5")
HALF_LEAD = PowerFactor.leading("0.5")


def ct(**over: object) -> InstrumentTransformer:
    args: dict[str, object] = {
        "kind": TransformerKind.CURRENT,
        "maker": "Ferrand",
        "marked_ratio": "40",
        "accuracy": "0.3",
        "rcf": "1.0020",
        "phase_minutes": "12",
        "tested_on": "2024-05-01",
    }
    args.update(over)
    return InstrumentTransformer.build(str(args.pop("serial", "CT-8841")), **args)  # type: ignore[arg-type]


def test_tan_theta_is_zero_at_unity() -> None:
    assert tan_theta(UNITY) == Decimal(0)


def test_tan_theta_at_half_a_power_factor() -> None:
    assert tan_theta(HALF_LAG) == Decimal("1.732051")
    assert tan_theta(HALF_LEAD) == Decimal("-1.732051")


def test_the_phase_angle_does_nothing_at_unity() -> None:
    assert ct(phase_minutes="60").pacf(UNITY) == Decimal("1.000000")
    assert ct(phase_minutes="60").tcf(UNITY) == Decimal("1.002000")


def test_the_phase_angle_bites_on_a_lagging_load() -> None:
    transformer = ct(phase_minutes="60")
    assert transformer.pacf(HALF_LAG) < 1
    assert transformer.tcf(HALF_LAG) < transformer.tcf(UNITY)


def test_a_leading_load_pulls_the_other_way() -> None:
    transformer = ct(phase_minutes="60")
    assert transformer.pacf(HALF_LEAD) > 1
    assert transformer.tcf(HALF_LEAD) > transformer.tcf(UNITY)


def test_a_transformer_with_no_phase_error_is_its_ratio_alone() -> None:
    flat = ct(phase_minutes="0")
    assert flat.tcf(HALF_LAG) == flat.rcf
    assert flat.tcf(UNITY) == flat.rcf


def test_the_contribution_is_the_reciprocal() -> None:
    flat = ct(rcf="1.0000", phase_minutes="0")
    assert flat.contribution(UNITY) == Registration("100")
    slow = ct(rcf="1.0100", phase_minutes="0")
    assert slow.contribution(UNITY).percent == Decimal("99.0099")
    assert slow.contribution(UNITY).is_slow


def test_the_contribution_composes_onto_a_meter() -> None:
    meter = Registration("100.30")
    overall = meter.compose(ct(rcf="1.0000", phase_minutes="0").contribution(UNITY))
    assert overall == meter


def test_true_ratio() -> None:
    assert ct(marked_ratio="40", rcf="1.0020").true_ratio == Decimal("40.0800")


def test_a_class_holds_or_does_not() -> None:
    assert ct(rcf="1.0020", phase_minutes="0").within_class(HALF_LAG)
    assert not ct(rcf="1.0040", phase_minutes="0").within_class(HALF_LAG)
    assert ct(rcf="1.0040", accuracy="0.6", phase_minutes="0").within_class(HALF_LAG)


def test_a_transformer_can_hold_its_class_at_unity_and_lose_it_lagging() -> None:
    marginal = ct(rcf="1.0029", phase_minutes="-60")
    assert marginal.within_class(UNITY)
    assert not marginal.within_class(HALF_LAG)


def test_accuracy_class_lookup() -> None:
    assert accuracy_class("0.3") is AccuracyClass.C03
    assert accuracy_class(AccuracyClass.C12) is AccuracyClass.C12
    assert AccuracyClass.C06.limits == (Decimal("0.994"), Decimal("1.006"))
    with pytest.raises(BadInputError, match="accuracy class"):
        accuracy_class("0.9")


def test_bad_transformers() -> None:
    with pytest.raises(BadInputError, match="TransformerKind"):
        ct(kind="current")
    with pytest.raises(BadInputError, match="above zero"):
        ct(marked_ratio="0")
    with pytest.raises(BadInputError, match="marked ratio"):
        ct(marked_ratio="lots")
    with pytest.raises(RuleError, match="not a transformer"):
        ct(rcf="1.5")
    with pytest.raises(RuleError, match="not a transformer"):
        ct(phase_minutes="900")


def test_str_names_the_ratio_and_the_class() -> None:
    assert str(ct()) == "CT-8841 current 40:1 class 0.3 RCF 1.0020"


def test_a_voltage_transformer_works_the_same_way() -> None:
    vt = ct(serial="VT-2201", kind=TransformerKind.VOLTAGE, marked_ratio="20", rcf="0.9990")
    assert vt.kind is TransformerKind.VOLTAGE
    assert vt.contribution(UNITY).is_fast


def test_a_transformer_whose_correction_factor_collapses() -> None:
    dead = ct(rcf="0.9000", phase_minutes="240")
    lagging = PowerFactor.lagging("0.01")
    assert dead.tcf(lagging) < 0
    with pytest.raises(RuleError, match="correction factor of"):
        dead.contribution(lagging)
