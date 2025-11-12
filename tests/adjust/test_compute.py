from __future__ import annotations

from decimal import Decimal

import pytest

from kilodial.adjust.compute import BilledMonth, compute
from kilodial.adjust.period import period_for
from kilodial.adjust.rules import STATE_TARIFF, Direction, Tariff
from kilodial.errors import RuleError
from kilodial.install.multiplier import InstalledAccuracy, accuracy_of
from kilodial.install.point import MeterSet
from kilodial.units.money import Money
from kilodial.units.registration import Registration
from kilodial.xfmr.transformer import InstrumentTransformer, TransformerKind

NO_INTEREST = Tariff("flat", Decimal("2.0"), 60, 12, 60, 36, Decimal("0"))


def a_set(**over: object) -> MeterSet:
    args: dict[str, object] = {"programmed_multiplier": "1", "set_on": "2019-05-02"}
    args.update(over)
    return MeterSet.build("SP-1042", "84-119302", **args)


def accuracy(percent: str, **over: object) -> InstalledAccuracy:
    return accuracy_of(a_set(**over), Registration(percent))


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


def months(*amounts: str) -> list[BilledMonth]:
    made = []
    for index, amount in enumerate(amounts, start=1):
        last = 31 if index in (1, 3, 5, 7, 8, 10, 12) else 30
        if index == 2:
            last = 28
        made.append(BilledMonth.of(f"2025-{index:02d}-01", f"2025-{index:02d}-{last}", amount))
    return made


def a_period(**over: object) -> object:
    args: dict[str, object] = {
        "found_on": "2025-04-30",
        "set_on": "2025-01-01",
        "cap_months": 60,
    }
    args.update(over)
    return period_for(**args)  # type: ignore[arg-type]


def test_a_fast_meter_refunds_the_customer() -> None:
    found = compute(
        point_code="sp-1042",
        meter_serial="84-119302",
        accuracy=accuracy("103.00"),
        period=a_period(),  # type: ignore[arg-type]
        billed=months("100.00", "100.00", "100.00", "100.00"),
        on="2025-04-30",
        tariff=NO_INTEREST,
    )
    assert found.direction is Direction.REFUND
    assert found.point_code == "SP-1042"
    assert found.billed == Money("400.00")
    assert found.moved == Money("11.65")
    assert found.total == found.moved


def test_a_slow_meter_back_bills() -> None:
    found = compute(
        point_code="SP-1042",
        meter_serial="84-119302",
        accuracy=accuracy("97.00"),
        period=a_period(cap_months=12),  # type: ignore[arg-type]
        billed=months("100.00", "100.00", "100.00", "100.00"),
        on="2025-04-30",
        tariff=NO_INTEREST,
    )
    assert found.direction is Direction.BACK_BILL
    assert found.moved == Money("12.37")
    assert found.interest.is_zero


def test_the_lines_add_back_to_the_total_exactly() -> None:
    found = compute(
        point_code="SP-1042",
        meter_serial="84-119302",
        accuracy=accuracy("103.00"),
        period=a_period(),  # type: ignore[arg-type]
        billed=months("33.33", "33.33", "33.34", "33.33"),
        on="2025-04-30",
        tariff=NO_INTEREST,
    )
    assert sum(line.moved.cents for line in found.lines) == found.moved.cents
    assert len(found.lines) == 4


def test_a_part_month_is_prorated_by_days() -> None:
    found = compute(
        point_code="SP-1042",
        meter_serial="84-119302",
        accuracy=accuracy("103.00"),
        period=a_period(set_on="2025-01-17"),  # type: ignore[arg-type]
        billed=months("310.00", "100.00", "100.00", "100.00"),
        on="2025-04-30",
        tariff=NO_INTEREST,
    )
    assert found.lines[0].billed == Money("150.00")
    assert found.period.span.start.isoformat() == "2025-01-17"


def test_a_billing_month_outside_the_period_contributes_nothing() -> None:
    found = compute(
        point_code="SP-1042",
        meter_serial="84-119302",
        accuracy=accuracy("103.00"),
        period=a_period(set_on="2025-03-01"),  # type: ignore[arg-type]
        billed=months("100.00", "100.00", "100.00", "100.00"),
        on="2025-04-30",
        tariff=NO_INTEREST,
    )
    assert found.billed == Money("200.00")
    assert len(found.lines) == 2


def test_interest_runs_on_a_refund_only() -> None:
    found = compute(
        point_code="SP-1042",
        meter_serial="84-119302",
        accuracy=accuracy("103.00"),
        period=a_period(),  # type: ignore[arg-type]
        billed=months("100.00", "100.00", "100.00", "100.00"),
        on="2026-04-30",
        tariff=STATE_TARIFF,
    )
    assert not found.interest.is_zero
    assert found.total == found.moved + found.interest
    assert found.lines[0].interest > found.lines[3].interest


def test_no_interest_on_a_back_bill() -> None:
    found = compute(
        point_code="SP-1042",
        meter_serial="84-119302",
        accuracy=accuracy("97.00"),
        period=a_period(cap_months=12),  # type: ignore[arg-type]
        billed=months("100.00", "100.00", "100.00", "100.00"),
        on="2026-04-30",
        tariff=STATE_TARIFF,
    )
    assert found.interest.is_zero


def test_a_multiplier_error_moves_the_whole_difference() -> None:
    found = compute(
        point_code="SP-1042",
        meter_serial="84-119302",
        accuracy=accuracy_of(
            a_set(ct_serial="CT-8841", programmed_multiplier="80"),
            Registration("100.00"),
            current=ct(),
        ),
        period=a_period(),  # type: ignore[arg-type]
        billed=months("100.00", "100.00", "100.00", "100.00"),
        on="2025-04-30",
        tariff=NO_INTEREST,
    )
    assert found.direction is Direction.REFUND
    assert found.moved == Money("200.00")


def test_a_perfect_meter_owes_nobody_anything() -> None:
    with pytest.raises(RuleError, match="owes nobody anything"):
        compute(
            point_code="SP-1042",
            meter_serial="84-119302",
            accuracy=accuracy("100.00"),
            period=a_period(),  # type: ignore[arg-type]
            billed=months("100.00"),
            on="2025-04-30",
        )


def test_no_billed_history() -> None:
    with pytest.raises(RuleError, match="no billed history"):
        compute(
            point_code="SP-1042",
            meter_serial="84-119302",
            accuracy=accuracy("103.00"),
            period=a_period(),  # type: ignore[arg-type]
            billed=[],
            on="2025-04-30",
        )


def test_a_period_with_nothing_billed_in_it() -> None:
    with pytest.raises(RuleError, match="nothing was billed"):
        compute(
            point_code="SP-1042",
            meter_serial="84-119302",
            accuracy=accuracy("103.00"),
            period=a_period(),  # type: ignore[arg-type]
            billed=[BilledMonth.of("2020-01-01", "2020-01-31", "100.00")],
            on="2025-04-30",
        )


def test_the_explanation_names_the_share() -> None:
    found = compute(
        point_code="SP-1042",
        meter_serial="84-119302",
        accuracy=accuracy("103.00"),
        period=a_period(),  # type: ignore[arg-type]
        billed=months("100.00", "100.00", "100.00", "100.00"),
        on="2025-04-30",
        tariff=NO_INTEREST,
    )
    assert "refund of $11.65" in found.explain()
    assert "2.9126 percent" in found.explain()


def test_a_billed_month_prorates_itself() -> None:
    month = BilledMonth.of("2025-01-01", "2025-01-31", "310.00")
    from kilodial.units.span import DateSpan

    assert month.share_over(DateSpan("2025-01-01", "2025-01-31")) == Money("310.00")
    assert month.share_over(DateSpan("2025-01-17", "2025-01-31")) == Money("150.00")
    assert month.share_over(DateSpan("2025-06-01", "2025-06-30")).is_zero
    assert str(month) == "2025-01-01 to 2025-01-31 $310.00"
