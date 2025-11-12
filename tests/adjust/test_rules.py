from __future__ import annotations

from decimal import Decimal

import pytest

from kilodial.adjust.rules import (
    STATE_TARIFF,
    Direction,
    Tariff,
    direction_of,
    error_share,
    is_adjustable,
    lookback_months,
    why_not,
)
from kilodial.errors import BadInputError
from kilodial.install.multiplier import InstalledAccuracy, accuracy_of
from kilodial.install.point import MeterSet
from kilodial.units.registration import Registration
from kilodial.xfmr.transformer import InstrumentTransformer, TransformerKind


def a_set(**over: object) -> MeterSet:
    args: dict[str, object] = {"programmed_multiplier": "1", "set_on": "2019-05-02"}
    args.update(over)
    return MeterSet.build("SP-1042", "84-119302", **args)


def ct() -> InstrumentTransformer:
    return InstrumentTransformer.build(
        "CT-8841",
        kind=TransformerKind.CURRENT,
        maker="Ferrand",
        marked_ratio="40",
        accuracy="0.3",
        rcf="1.0000",
        phase_minutes="0",
        tested_on="2024-05-01",
    )


def accuracy(percent: str, **over: object) -> InstalledAccuracy:
    return accuracy_of(a_set(**over), Registration(percent))


def test_the_state_tariff_is_asymmetric() -> None:
    assert STATE_TARIFF.refund_months == 60
    assert STATE_TARIFF.back_bill_months == 12
    assert STATE_TARIFF.refund_months > STATE_TARIFF.back_bill_months
    assert "refund 60 months" in str(STATE_TARIFF)


def test_a_tariff_has_to_make_sense() -> None:
    with pytest.raises(BadInputError, match="tolerance cannot be negative"):
        Tariff("bad", Decimal("-1"), 60, 12, 60, 36, Decimal("0"))
    with pytest.raises(BadInputError, match="positive month count"):
        Tariff("bad", Decimal("2"), 0, 12, 60, 36, Decimal("0"))
    with pytest.raises(BadInputError, match="interest rate"):
        Tariff("bad", Decimal("2"), 60, 12, 60, 36, Decimal("-0.01"))


def test_a_meter_inside_tolerance_is_not_adjusted() -> None:
    found = accuracy("101.50")
    assert not is_adjustable(found)
    assert "inside the +/-2.0 percent tolerance" in str(why_not(found))


def test_a_meter_outside_tolerance_is() -> None:
    found = accuracy("103.00")
    assert is_adjustable(found)
    assert why_not(found) is None


def test_the_edge_of_the_tolerance_is_inside_it() -> None:
    assert not is_adjustable(accuracy("102.00"))
    assert is_adjustable(accuracy("102.01"))


def test_a_multiplier_error_is_adjustable_however_small_the_meter_error() -> None:
    found = accuracy_of(
        a_set(ct_serial="CT-8841", programmed_multiplier="20"),
        Registration("100.00"),
        current=ct(),
    )
    assert found.overall == Registration("100.00")
    assert is_adjustable(found)
    assert why_not(found) is None


def test_a_fast_meter_owes_the_customer() -> None:
    assert direction_of(accuracy("103.00")) is Direction.REFUND
    assert Direction.REFUND.moves_money
    assert str(Direction.BACK_BILL) == "back bill"


def test_a_slow_meter_is_owed_to_the_utility() -> None:
    assert direction_of(accuracy("97.00")) is Direction.BACK_BILL


def test_a_perfect_meter_moves_nothing() -> None:
    assert direction_of(accuracy("100.00")) is Direction.NONE
    assert not Direction.NONE.moves_money


def test_the_lookback_is_longer_for_a_refund() -> None:
    assert lookback_months(accuracy("103.00")) == 60
    assert lookback_months(accuracy("97.00")) == 12


def test_a_multiplier_error_gets_the_long_lookback_either_way() -> None:
    slow = accuracy_of(
        a_set(ct_serial="CT-8841", programmed_multiplier="20"),
        Registration("100.00"),
        current=ct(),
    )
    assert direction_of(slow) is Direction.BACK_BILL
    assert lookback_months(slow) == 60


def test_the_error_share_uses_the_billed_reading_as_the_denominator() -> None:
    assert error_share(accuracy("103.00")) == Decimal("0.02912621")
    assert error_share(accuracy("100.00")) == Decimal("0E-8")


def test_a_slow_meter_has_a_negative_share() -> None:
    assert error_share(accuracy("97.00")) < 0


def test_an_installation_registering_nothing() -> None:
    with pytest.raises(BadInputError, match="registering nothing"):
        error_share(accuracy("0"))


def test_confirmed_interference_reaches_furthest_on_a_back_bill() -> None:
    slow = accuracy("96.00")
    assert lookback_months(slow) == 12
    assert lookback_months(slow, tamper=True) == 36


def test_interference_does_not_lengthen_a_refund() -> None:
    fast = accuracy("104.00")
    assert lookback_months(fast) == 60
    assert lookback_months(fast, tamper=True) == 60


def test_interference_beats_a_multiplier_error_on_a_back_bill() -> None:
    slow = accuracy_of(
        a_set(ct_serial="CT-8841", programmed_multiplier="20"),
        Registration("100.00"),
        current=ct(),
    )
    assert lookback_months(slow) == 60
    assert lookback_months(slow, tamper=True) == 36


def test_the_tamper_lookback_has_to_be_positive() -> None:
    with pytest.raises(BadInputError, match="positive month count"):
        Tariff("bad", Decimal("2"), 60, 12, 60, 0, Decimal("0"))
