from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from kilodial.adjust.compute import Adjustment, BilledMonth
from kilodial.adjust.period import Boundary
from kilodial.adjust.rules import Direction
from kilodial.adjust.service import (
    Refusal,
    finding_run,
    period_of,
    raise_adjustment,
)
from kilodial.errors import RuleError
from kilodial.install.point import MeterSet, ServicePoint
from kilodial.model.bench import Bench, ReferenceStandard
from kilodial.model.device import DeviceType
from kilodial.model.form import Service, Technology
from kilodial.model.meter import Meter
from kilodial.model.run import BenchPoint, BenchRun, RunKind
from kilodial.store.shop import Shop, open_shop
from kilodial.tamper.event import Finding as TamperFinding
from kilodial.units.money import Money
from kilodial.xfmr.transformer import InstrumentTransformer, TransformerKind


@pytest.fixture
def shop(tmp_path: Path) -> Iterator[Shop]:
    opened = open_shop(tmp_path / "shop.sqlite3", create=True)
    opened.devices.add(
        DeviceType.build(
            "Halvern",
            "R4S",
            form_code="2S",
            class_code="200",
            voltage="240",
            kh="7.2",
            technology=Technology.INDUCTION,
            register_ratio="100",
            introduced="2004-05-01",
        )
    )
    opened.meters.add(Meter.receive("84-119302", "Halvern/R4S", acquired="2015-01-01"))
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
            positions=8,
            standard_serial="RS-5511",
            max_amperes="100",
            max_volts="480",
            polyphase=True,
            installed="2010-01-01",
        )
    )
    opened.points.add(
        ServicePoint.build(
            "SP-1042",
            account="44-9021",
            address="18 Fenwick Row",
            service=Service.SINGLE_PHASE_3W,
            voltage="240",
            rate_code="R1",
            energised="2011-06-14",
        )
    )
    yield opened
    opened.close()


def set_meter(shop: Shop, **over: object) -> MeterSet:
    args: dict[str, object] = {"programmed_multiplier": "1", "set_on": "2019-05-02"}
    args.update(over)
    return shop.installs.set_meter(MeterSet.build("SP-1042", "84-119302", **args))


def bench(
    shop: Shop, reference: str, on: str, pct: str, kind: RunKind = RunKind.AS_FOUND
) -> BenchRun:
    return shop.runs.add(
        BenchRun.build(
            reference,
            meter_serial="84-119302",
            bench_code="B2",
            standard_serial="RS-5511",
            kind=kind,
            tested_on=on,
            technician="R Ellis",
            points=[
                BenchPoint.build("FL", amperes="30", volts="240", registration=pct),
                BenchPoint.build("LL", amperes="3", volts="240", registration=pct),
            ],
        )
    )


def bill(shop: Shop, year: int, months: int = 12, amount: str = "100.00") -> None:
    for index in range(1, months + 1):
        last = {
            1: 31,
            2: 28,
            3: 31,
            4: 30,
            5: 31,
            6: 30,
            7: 31,
            8: 31,
            9: 30,
            10: 31,
            11: 30,
            12: 31,
        }[index]
        shop.billing.add(
            "SP-1042",
            BilledMonth.of(f"{year}-{index:02d}-01", f"{year}-{index:02d}-{last}", amount),
        )


def test_the_finding_run_is_the_latest_usable_one(shop: Shop) -> None:
    bench(shop, "TR-1", "2023-01-05", "100.10")
    bench(shop, "TR-2", "2025-06-30", "103.00")
    bench(shop, "TR-3", "2025-07-01", "100.00", RunKind.AS_LEFT)
    assert finding_run(shop, "84-119302").reference == "TR-2"


def test_a_meter_with_no_usable_run(shop: Shop) -> None:
    with pytest.raises(RuleError, match="no usable as found run"):
        finding_run(shop, "84-119302")


def test_a_meter_inside_tolerance_is_refused(shop: Shop) -> None:
    set_meter(shop)
    bench(shop, "TR-1", "2025-06-30", "101.00")
    bill(shop, 2025, 6)
    found = raise_adjustment(shop, "SP-1042", on="2025-07-15")
    assert isinstance(found, Refusal)
    assert "inside the +/-2.0 percent tolerance" in found.reason


def test_a_fast_meter_refunds_the_customer(shop: Shop) -> None:
    set_meter(shop, set_on="2024-12-01")
    bench(shop, "TR-1", "2025-06-30", "103.00")
    bill(shop, 2025, 6)
    found = raise_adjustment(shop, "SP-1042", on="2025-07-15")
    assert isinstance(found, Adjustment)
    assert found.direction is Direction.REFUND
    assert found.period.reason is Boundary.METER_SET
    assert found.billed == Money("600.00")
    assert found.moved.cents > 0


def test_the_lookback_caps_a_back_bill_at_a_year(shop: Shop) -> None:
    set_meter(shop, set_on="2015-01-01")
    bench(shop, "TR-1", "2025-06-30", "96.00")
    bill(shop, 2024)
    bill(shop, 2025, 6)
    found = raise_adjustment(shop, "SP-1042", on="2025-07-15")
    assert isinstance(found, Adjustment)
    assert found.direction is Direction.BACK_BILL
    assert found.period.reason is Boundary.TARIFF_CAP
    assert found.period.span.start.isoformat() == "2024-06-30"


def test_a_clean_test_stops_the_lookback(shop: Shop) -> None:
    set_meter(shop, set_on="2015-01-01")
    bench(shop, "TR-0", "2025-02-14", "100.10")
    bench(shop, "TR-1", "2025-06-30", "104.00")
    bill(shop, 2025, 6)
    found = raise_adjustment(shop, "SP-1042", on="2025-07-15")
    assert isinstance(found, Adjustment)
    assert found.period.reason is Boundary.CLEAN_TEST
    assert found.period.span.start.isoformat() == "2025-02-15"


def test_a_failing_earlier_test_does_not_stop_it(shop: Shop) -> None:
    set_meter(shop, set_on="2024-12-01")
    bench(shop, "TR-0", "2025-02-14", "104.00")
    bench(shop, "TR-1", "2025-06-30", "104.00")
    bill(shop, 2025, 6)
    found = raise_adjustment(shop, "SP-1042", on="2025-07-15")
    assert isinstance(found, Adjustment)
    assert found.period.reason is Boundary.METER_SET


def test_a_multiplier_error_is_adjusted_though_the_meter_is_fine(shop: Shop) -> None:
    shop.transformers.add(
        InstrumentTransformer.build(
            "CT-8841",
            kind=TransformerKind.CURRENT,
            maker="Ferrand",
            marked_ratio="40",
            accuracy="0.3",
            rcf="1.0000",
            phase_minutes="0",
            tested_on="2024-05-01",
        )
    )
    set_meter(shop, set_on="2024-12-01", ct_serial="CT-8841", programmed_multiplier="80")
    bench(shop, "TR-1", "2025-06-30", "100.00")
    bill(shop, 2025, 6)
    found = raise_adjustment(shop, "SP-1042", on="2025-07-15")
    assert isinstance(found, Adjustment)
    assert found.direction is Direction.REFUND
    assert found.moved == Money("300.00")


def test_no_billed_history_is_a_refusal_not_a_crash(shop: Shop) -> None:
    set_meter(shop, set_on="2024-12-01")
    bench(shop, "TR-1", "2025-06-30", "103.00")
    found = raise_adjustment(shop, "SP-1042", on="2025-07-15")
    assert isinstance(found, Refusal)
    assert "no billed history" in found.reason
    assert str(found).startswith("SP-1042")


def test_a_point_that_never_had_a_meter(shop: Shop) -> None:
    with pytest.raises(RuleError, match="nothing has ever been set"):
        raise_adjustment(shop, "SP-1042", on="2025-07-15")


def test_a_pulled_meter_ends_the_period_at_the_pull(shop: Shop) -> None:
    set_meter(shop, set_on="2024-12-01")
    bench(shop, "TR-1", "2025-06-30", "103.00")
    shop.installs.pull("SP-1042", "2025-05-14")
    bill(shop, 2025, 6)
    found = raise_adjustment(shop, "SP-1042", on="2025-07-15")
    assert isinstance(found, Adjustment)
    assert found.period.span.end is not None
    assert found.period.span.end.isoformat() == "2025-05-14"


def confirm_tamper(shop: Shop, kind: str, since: str = "2022-01-01") -> None:
    shop.tamper.add(
        TamperFinding.raise_finding(
            "TF-1", "SP-1042", kind, found_on="2025-06-30", found_by="R Ellis"
        )
    )
    shop.tamper.save(
        shop.tamper.get("TF-1").confirmed(
            on="2025-07-01", since=since, evidence="found on the pull"
        )
    )


def test_a_confirmed_seal_cut_lengthens_a_back_bill(shop: Shop) -> None:
    set_meter(shop, set_on="2015-01-01")
    bench(shop, "TR-1", "2025-06-30", "96.00")
    bill(shop, 2023)
    bill(shop, 2024)
    bill(shop, 2025, 6)
    confirm_tamper(shop, "seal cut")
    found = raise_adjustment(shop, "SP-1042", on="2025-07-15")
    assert isinstance(found, Adjustment)
    assert found.period.span.start.isoformat() == "2022-06-30"


def test_a_suspicion_does_not_lengthen_anything(shop: Shop) -> None:
    set_meter(shop, set_on="2015-01-01")
    bench(shop, "TR-1", "2025-06-30", "96.00")
    bill(shop, 2024)
    bill(shop, 2025, 6)
    shop.tamper.add(
        TamperFinding.raise_finding(
            "TF-1", "SP-1042", "seal cut", found_on="2025-06-30", found_by="R Ellis"
        )
    )
    found = raise_adjustment(shop, "SP-1042", on="2025-07-15")
    assert isinstance(found, Adjustment)
    assert found.period.span.start.isoformat() == "2024-06-30"


def test_a_confirmed_bypass_cannot_be_priced_from_a_registration(shop: Shop) -> None:
    set_meter(shop, set_on="2015-01-01")
    bench(shop, "TR-1", "2025-06-30", "96.00")
    bill(shop, 2025, 6)
    confirm_tamper(shop, "bypass")
    found = raise_adjustment(shop, "SP-1042", on="2025-07-15")
    assert isinstance(found, Refusal)
    assert "has to be estimated" in found.reason


def test_a_confirmed_bypass_stops_even_a_meter_inside_tolerance(shop: Shop) -> None:
    set_meter(shop, set_on="2015-01-01")
    bench(shop, "TR-1", "2025-06-30", "100.10")
    bill(shop, 2025, 6)
    confirm_tamper(shop, "reversed")
    found = raise_adjustment(shop, "SP-1042", on="2025-07-15")
    assert isinstance(found, Refusal)
    assert "stopped the meter measuring" in found.reason


def test_a_finding_confirmed_after_the_run_still_counts(shop: Shop) -> None:
    set_meter(shop, set_on="2015-01-01")
    bench(shop, "TR-1", "2025-06-30", "96.00")
    bill(shop, 2023)
    bill(shop, 2024)
    bill(shop, 2025, 6)
    shop.tamper.add(
        TamperFinding.raise_finding(
            "TF-1", "SP-1042", "seal cut", found_on="2025-07-02", found_by="R Ellis"
        )
    )
    shop.tamper.save(
        shop.tamper.get("TF-1").confirmed(
            on="2025-07-02", since="2022-01-01", evidence="copper wire"
        )
    )
    found = raise_adjustment(shop, "SP-1042", on="2025-07-15")
    assert isinstance(found, Adjustment)
    assert found.period.span.start.isoformat() == "2022-06-30"


def test_a_finding_confirmed_after_the_adjustment_does_not(shop: Shop) -> None:
    set_meter(shop, set_on="2015-01-01")
    bench(shop, "TR-1", "2025-06-30", "96.00")
    bill(shop, 2024)
    bill(shop, 2025, 6)
    shop.tamper.add(
        TamperFinding.raise_finding(
            "TF-1", "SP-1042", "seal cut", found_on="2025-08-02", found_by="R Ellis"
        )
    )
    shop.tamper.save(
        shop.tamper.get("TF-1").confirmed(
            on="2025-08-02", since="2022-01-01", evidence="copper wire"
        )
    )
    found = raise_adjustment(shop, "SP-1042", on="2025-07-15")
    assert isinstance(found, Adjustment)
    assert found.period.span.start.isoformat() == "2024-06-30"


def test_the_period_alone_needs_a_day(shop: Shop) -> None:
    set_meter(shop, set_on="2015-01-01")
    bench(shop, "TR-1", "2025-06-30", "96.00")
    bill(shop, 2024)
    bill(shop, 2025, 6)
    period = period_of(shop, "SP-1042", on="2025-07-15")
    assert period.span.start.isoformat() == "2024-06-30"


def test_the_period_alone_refuses_a_meter_that_is_fine(shop: Shop) -> None:
    set_meter(shop, set_on="2015-01-01")
    bench(shop, "TR-1", "2025-06-30", "100.10")
    bill(shop, 2025, 6)
    with pytest.raises(RuleError, match="inside the"):
        period_of(shop, "SP-1042", on="2025-07-15")
