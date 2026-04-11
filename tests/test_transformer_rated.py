"""A transformer rated service, where the meter is only part of the answer.

A self contained meter is its own error. A transformer rated installation is
three errors composed, and two of them behave in ways the meter's own error does
not: the phase angle correction is exactly zero at unity power factor and real
on a motor load, and the programmed multiplier is arithmetic rather than
measurement and is corrected in full.

This walk sets one up and checks each of those separately, because the whole
argument of the install layer is that they are separate.
"""

from __future__ import annotations

from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path

import pytest

from kilodial.adjust.compute import Adjustment, BilledMonth
from kilodial.adjust.rules import Direction, is_adjustable
from kilodial.adjust.service import raise_adjustment
from kilodial.install.point import MeterSet, ServicePoint
from kilodial.model.bench import Bench, ReferenceStandard
from kilodial.model.device import DeviceType
from kilodial.model.form import Service, Technology
from kilodial.model.meter import Meter, MeterState
from kilodial.model.run import RunKind
from kilodial.store.shop import Shop, open_shop
from kilodial.testing.record import Readings, build_run
from kilodial.units.electrical import PowerFactor
from kilodial.units.money import Money
from kilodial.xfmr.transformer import InstrumentTransformer, TransformerKind

LAST_DAY = {1: 31, 2: 28, 3: 31, 4: 30, 5: 31, 6: 30}
HALF_LAG = PowerFactor.lagging("0.5")


@pytest.fixture
def shop(tmp_path: Path) -> Iterator[Shop]:
    opened = open_shop(tmp_path / "ct.sqlite3", create=True)
    opened.devices.add(
        DeviceType.build(
            "Halvern",
            "R9S",
            form_code="9S",
            class_code="20",
            voltage="240",
            kh="0.6",
            technology=Technology.INDUCTION,
            register_ratio="100",
            introduced="2009-01-01",
        )
    )
    opened.meters.add(Meter.receive("84-220001", "Halvern/R9S", acquired="2015-01-01"))
    opened.meters.move("84-220001", MeterState.STOCK)
    opened.meters.move("84-220001", MeterState.SET)
    opened.standards.add(
        ReferenceStandard.build(
            "RS-5511",
            maker="Radian",
            model_code="RD-23",
            certificate="NVLAP-88214",
            certified_on="2015-01-01",
            certificate_due="2035-01-01",
            uncertainty="0.02",
        )
    )
    opened.benches.add(
        Bench.build(
            "B2",
            "north wall",
            positions=4,
            standard_serial="RS-5511",
            max_amperes="100",
            max_volts="480",
            polyphase=True,
            installed="2010-01-01",
        )
    )
    opened.points.add(
        ServicePoint.build(
            "SP-2001",
            account="44-9500",
            address="Fenwick Mill",
            service=Service.THREE_PHASE_4W_WYE,
            voltage="240",
            rate_code="GS3",
            energised="2011-06-14",
        )
    )
    yield opened
    opened.close()


def add_ct(shop: Shop, *, rcf: str = "1.0000", minutes: str = "0") -> None:
    shop.transformers.add(
        InstrumentTransformer.build(
            "CT-8841",
            kind=TransformerKind.CURRENT,
            maker="Ferrand",
            marked_ratio="40",
            accuracy="0.3",
            rcf=rcf,
            phase_minutes=minutes,
            tested_on="2024-05-01",
        )
    )


def set_it(shop: Shop, *, multiplier: str = "40") -> None:
    shop.installs.set_meter(
        MeterSet.build(
            "SP-2001",
            "84-220001",
            ct_serial="CT-8841",
            programmed_multiplier=multiplier,
            set_on="2018-06-01",
        )
    )


def bench_it(shop: Shop, reading: str) -> None:
    shop.runs.add(
        build_run(
            "TR-1",
            device=shop.device_for("84-220001"),
            meter_serial="84-220001",
            bench_code="B2",
            standard_serial="RS-5511",
            kind=RunKind.AS_FOUND,
            tested_on="2025-06-30",
            technician="R Ellis",
            readings=Readings.of(full_load=reading, light_load=reading, power_factor=reading),
        )
    )


def bill(shop: Shop) -> None:
    for month in range(1, 7):
        shop.billing.add(
            "SP-2001",
            BilledMonth.of(
                f"2025-{month:02d}-01", f"2025-{month:02d}-{LAST_DAY[month]}", "4000.00"
            ),
        )


def test_a_perfect_installation(shop: Shop) -> None:
    add_ct(shop)
    set_it(shop)
    bench_it(shop, "100.00")
    found = shop.installed_accuracy("SP-2001")
    assert found.meter.percent == Decimal("100.0000")
    assert found.overall.percent == Decimal("100.0000")
    assert found.multiplier_is_right
    assert found.expected_multiplier == Decimal("40")
    assert not is_adjustable(found)


def test_the_transformer_error_composes_onto_the_meter(shop: Shop) -> None:
    add_ct(shop, rcf="1.0100")
    set_it(shop)
    bench_it(shop, "100.00")
    found = shop.installed_accuracy("SP-2001")
    assert found.meter.percent == Decimal("100.0000")
    assert found.current_transformer is not None
    assert found.overall < found.meter
    assert found.overall.percent == Decimal("99.0099")


def test_a_phase_angle_does_nothing_at_unity_and_bites_on_a_motor_load(
    shop: Shop,
) -> None:
    add_ct(shop, minutes="120")
    set_it(shop)
    bench_it(shop, "100.00")
    flat = shop.installed_accuracy("SP-2001")
    lagging = shop.installed_accuracy("SP-2001", power_factor=HALF_LAG)
    assert flat.overall.percent == Decimal("100.0000")
    assert lagging.overall > flat.overall
    assert not is_adjustable(flat)
    assert lagging.overall.error > Decimal("2.0")
    assert is_adjustable(lagging)


def test_a_meter_inside_tolerance_can_be_a_failing_installation(shop: Shop) -> None:
    # The meter is 1.5 percent fast, which passes on its own. The transformer
    # adds another one and a half, and the installation does not.
    add_ct(shop, rcf="0.9850")
    set_it(shop)
    bench_it(shop, "101.50")
    found = shop.installed_accuracy("SP-2001")
    assert found.meter.within(Decimal("2.0"))
    assert not found.overall.within(Decimal("2.0"))
    assert is_adjustable(found)


def test_a_multiplier_typed_in_wrong_is_not_a_measurement_problem(shop: Shop) -> None:
    add_ct(shop)
    set_it(shop, multiplier="20")
    bench_it(shop, "100.00")
    bill(shop)
    found = shop.installed_accuracy("SP-2001")
    assert found.overall == found.meter
    assert not found.multiplier_is_right
    assert found.billed_registration.percent == Decimal("50.0000")
    assert "programmed multiplier 20 against a computed 40" in found.faults()[0]

    # It is adjustable however small the meter error is, it goes the utility's
    # way, and it reaches back five years rather than one.
    raised = raise_adjustment(shop, "SP-2001", on="2025-07-15")
    assert isinstance(raised, Adjustment)
    assert raised.direction is Direction.BACK_BILL
    assert raised.period.span.start.isoformat() == "2020-06-30"
    assert raised.moved == Money("24000.00")


def test_the_transformer_has_to_be_on_the_book(shop: Shop) -> None:
    add_ct(shop)
    set_it(shop)
    bench_it(shop, "100.00")
    shop.book.connection.execute("DELETE FROM instrument_transformer")
    with pytest.raises(Exception, match="CT-8841, which was not supplied"):
        shop.installed_accuracy("SP-2001")
    assert any("names current transformer CT-8841" in f for f in shop.audit())


def test_the_class_20_meter_is_held_to_a_tighter_band(shop: Shop) -> None:
    add_ct(shop)
    set_it(shop)
    bench_it(shop, "101.50")
    verdict = shop.judge("TR-1")
    assert verdict.band.weighted == Decimal("1.33")
    assert not verdict.passed
