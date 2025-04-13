from __future__ import annotations

from decimal import Decimal

import pytest

from kilodial.errors import RuleError
from kilodial.install.multiplier import accuracy_of, expected_multiplier
from kilodial.install.point import MeterSet
from kilodial.units.electrical import PowerFactor
from kilodial.units.registration import Registration
from kilodial.xfmr.transformer import InstrumentTransformer, TransformerKind

UNITY = PowerFactor.unity()
HALF_LAG = PowerFactor.lagging("0.5")


def ct(**over: object) -> InstrumentTransformer:
    args: dict[str, object] = {
        "kind": TransformerKind.CURRENT,
        "maker": "Ferrand",
        "marked_ratio": "40",
        "accuracy": "0.3",
        "rcf": "1.0000",
        "phase_minutes": "0",
        "tested_on": "2024-05-01",
    }
    args.update(over)
    return InstrumentTransformer.build(str(args.pop("serial", "CT-8841")), **args)  # type: ignore[arg-type]


def vt(**over: object) -> InstrumentTransformer:
    args: dict[str, object] = {
        "serial": "VT-2201",
        "kind": TransformerKind.VOLTAGE,
        "marked_ratio": "20",
        "rcf": "1.0000",
    }
    args.update(over)
    return ct(**args)


def a_set(**over: object) -> MeterSet:
    args: dict[str, object] = {"programmed_multiplier": "1", "set_on": "2019-05-02"}
    args.update(over)
    return MeterSet.build("SP-1042", "84-119302", **args)


def test_a_self_contained_set_has_a_multiplier_of_one() -> None:
    assert expected_multiplier(a_set()) == Decimal("1")


def test_the_multiplier_is_a_product() -> None:
    s = a_set(ct_serial="CT-8841", vt_serial="VT-2201", programmed_multiplier="800")
    assert expected_multiplier(s, current=ct(), voltage=vt()) == Decimal("800")


def test_the_register_multiplier_is_in_the_product() -> None:
    s = a_set(ct_serial="CT-8841", register_multiplier="10", programmed_multiplier="400")
    assert expected_multiplier(s, current=ct()) == Decimal("400")


def test_a_voltage_transformer_given_as_the_current_one() -> None:
    with pytest.raises(RuleError, match="is a voltage transformer"):
        expected_multiplier(a_set(), current=vt())
    with pytest.raises(RuleError, match="is a current transformer"):
        expected_multiplier(a_set(), voltage=ct())


def test_a_clean_self_contained_installation() -> None:
    found = accuracy_of(a_set(), Registration("100.30"))
    assert found.overall == Registration("100.30")
    assert found.current_transformer is None
    assert found.multiplier_is_right
    assert found.faults() == []
    assert str(found) == "100.30% overall at 1.0 PF"


def test_the_transformers_compose_onto_the_meter() -> None:
    s = a_set(ct_serial="CT-8841", programmed_multiplier="40")
    found = accuracy_of(s, Registration("100.30"), current=ct(rcf="1.0020"))
    assert found.current_transformer is not None
    assert found.overall.percent == Decimal("100.0998")
    assert found.overall < found.meter


def test_a_phase_angle_only_bites_at_a_lagging_load() -> None:
    s = a_set(ct_serial="CT-8841", programmed_multiplier="40")
    flat = accuracy_of(s, Registration("100.00"), current=ct(phase_minutes="60"))
    lagging = accuracy_of(
        s, Registration("100.00"), current=ct(phase_minutes="60"), power_factor=HALF_LAG
    )
    assert flat.overall == Registration("100.00")
    assert lagging.overall > flat.overall


def test_a_set_that_names_a_transformer_nobody_passed_in() -> None:
    s = a_set(ct_serial="CT-8841", programmed_multiplier="40")
    with pytest.raises(RuleError, match="CT-8841, which was not supplied"):
        accuracy_of(s, Registration("100"))
    s = a_set(vt_serial="VT-2201", programmed_multiplier="20")
    with pytest.raises(RuleError, match="VT-2201, which was not supplied"):
        accuracy_of(s, Registration("100"))


def test_a_multiplier_that_was_typed_in_wrong() -> None:
    s = a_set(ct_serial="CT-8841", vt_serial="VT-2201", programmed_multiplier="400")
    found = accuracy_of(s, Registration("100.00"), current=ct(), voltage=vt())
    assert not found.multiplier_is_right
    assert found.multiplier_ratio == Decimal("0.500000")
    assert "programmed multiplier 400 against a computed 800" in found.faults()[0]


def test_the_billed_registration_folds_the_multiplier_in() -> None:
    s = a_set(ct_serial="CT-8841", vt_serial="VT-2201", programmed_multiplier="400")
    found = accuracy_of(s, Registration("100.00"), current=ct(), voltage=vt())
    assert found.overall == Registration("100.00")
    assert found.billed_registration == Registration("50.00")


def test_a_right_multiplier_leaves_the_billed_reading_alone() -> None:
    s = a_set(ct_serial="CT-8841", programmed_multiplier="40")
    found = accuracy_of(s, Registration("99.40"), current=ct())
    assert found.billed_registration == found.overall
    assert found.faults() == []


def test_a_meter_error_and_a_multiplier_error_stay_apart() -> None:
    s = a_set(ct_serial="CT-8841", programmed_multiplier="80")
    found = accuracy_of(s, Registration("102.00"), current=ct())
    assert found.overall == Registration("102.00")
    assert not found.multiplier_is_right
    assert found.billed_registration == Registration("204.00")
