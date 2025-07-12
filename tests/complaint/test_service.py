from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from kilodial.complaint.request import Charge, Reason
from kilodial.complaint.service import answer, log, previous_free_window
from kilodial.errors import RuleError
from kilodial.install.point import MeterSet, ServicePoint
from kilodial.model.bench import Bench, ReferenceStandard
from kilodial.model.device import DeviceType
from kilodial.model.form import Service, Technology
from kilodial.model.meter import Meter
from kilodial.model.run import BenchPoint, BenchRun, RunKind
from kilodial.store.shop import Shop, open_shop
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
    opened.installs.set_meter(
        MeterSet.build("SP-1042", "84-119302", programmed_multiplier="1", set_on="2019-05-02")
    )
    yield opened
    opened.close()


def referee(shop: Shop, reference: str, on: str, pct: str, kind: RunKind = RunKind.REFEREE) -> None:
    shop.runs.add(
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


def test_logging_a_request(shop: Shop) -> None:
    opened = log(
        shop,
        "CR-1",
        "sp-1042",
        on="2025-03-04",
        by="M Okafor",
        reason=Reason.HIGH_BILL,
        note="bill doubled",
    )
    assert opened.is_open
    assert opened.request.point_code == "SP-1042"
    assert opened.request.previous_request_on is None


def test_a_second_request_carries_the_first_one_forward(shop: Shop) -> None:
    log(shop, "CR-1", "SP-1042", on="2024-01-01", by="M Okafor")
    second = log(shop, "CR-2", "SP-1042", on="2025-03-04", by="M Okafor")
    assert second.request.previous_request_on is not None
    assert not second.request.in_free_window()


def test_the_free_window_helper(shop: Shop) -> None:
    assert previous_free_window(shop, "SP-1042", "2025-03-04")
    log(shop, "CR-1", "SP-1042", on="2024-01-01", by="M Okafor")
    assert not previous_free_window(shop, "SP-1042", "2025-03-04")
    assert previous_free_window(shop, "SP-1042", "2026-03-04")


def test_a_good_meter_on_a_first_request_is_free(shop: Shop) -> None:
    log(shop, "CR-1", "SP-1042", on="2025-03-04", by="M Okafor")
    referee(shop, "TR-9", "2025-03-14", "100.10")
    found = answer(shop, "CR-1", run_reference="TR-9", on="2025-03-14")
    assert found.charge is Charge.WAIVED_FREE
    assert found.fee.is_zero
    assert found.within_tolerance
    assert "100.10%" in found.explain()


def test_a_repeat_request_on_a_good_meter_is_charged(shop: Shop) -> None:
    log(shop, "CR-0", "SP-1042", on="2024-01-01", by="M Okafor")
    log(shop, "CR-1", "SP-1042", on="2025-03-04", by="M Okafor")
    referee(shop, "TR-9", "2025-03-14", "100.10")
    found = answer(shop, "CR-1", run_reference="TR-9", on="2025-03-14")
    assert found.charge is Charge.CHARGED
    assert found.fee == Money("28.00")


def test_a_bad_meter_waives_the_fee(shop: Shop) -> None:
    log(shop, "CR-0", "SP-1042", on="2024-01-01", by="M Okafor")
    log(shop, "CR-1", "SP-1042", on="2025-03-04", by="M Okafor")
    referee(shop, "TR-9", "2025-03-14", "103.00")
    found = answer(shop, "CR-1", run_reference="TR-9", on="2025-03-14")
    assert found.charge is Charge.WAIVED_ACCURACY
    assert not found.within_tolerance


def test_a_multiplier_error_waives_the_fee_on_a_perfect_meter(shop: Shop) -> None:
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
    shop.installs.pull("SP-1042", "2020-01-01")
    shop.installs.set_meter(
        MeterSet.build(
            "SP-1042",
            "84-119302",
            ct_serial="CT-8841",
            programmed_multiplier="80",
            set_on="2020-01-02",
        )
    )
    log(shop, "CR-0", "SP-1042", on="2024-01-01", by="M Okafor")
    log(shop, "CR-1", "SP-1042", on="2025-03-04", by="M Okafor")
    referee(shop, "TR-9", "2025-03-14", "100.00")
    found = answer(shop, "CR-1", run_reference="TR-9", on="2025-03-14")
    assert found.charge is Charge.WAIVED_ACCURACY


def test_a_late_test_waives_the_fee(shop: Shop) -> None:
    log(shop, "CR-0", "SP-1042", on="2024-01-01", by="M Okafor")
    log(shop, "CR-1", "SP-1042", on="2025-03-04", by="M Okafor")
    referee(shop, "TR-9", "2025-05-01", "100.10")
    found = answer(shop, "CR-1", run_reference="TR-9", on="2025-05-01")
    assert found.charge is Charge.WAIVED_LATE


def test_an_ordinary_run_does_not_answer_a_request(shop: Shop) -> None:
    log(shop, "CR-1", "SP-1042", on="2025-03-04", by="M Okafor")
    referee(shop, "TR-9", "2025-03-14", "100.10", RunKind.AS_FOUND)
    with pytest.raises(RuleError, match="answered by a referee run"):
        answer(shop, "CR-1", run_reference="TR-9", on="2025-03-14")


def test_a_run_on_the_wrong_meter(shop: Shop) -> None:
    shop.meters.add(Meter.receive("84-119303", "Halvern/R4S", acquired="2015-01-01"))
    shop.runs.add(
        BenchRun.build(
            "TR-9",
            meter_serial="84-119303",
            bench_code="B2",
            standard_serial="RS-5511",
            kind=RunKind.REFEREE,
            tested_on="2025-03-14",
            technician="R Ellis",
            points=[
                BenchPoint.build("FL", amperes="30", volts="240", registration="100.10"),
                BenchPoint.build("LL", amperes="3", volts="240", registration="100.10"),
            ],
        )
    )
    log(shop, "CR-1", "SP-1042", on="2025-03-04", by="M Okafor")
    with pytest.raises(RuleError, match="is on meter 84-119303"):
        answer(shop, "CR-1", run_reference="TR-9", on="2025-03-14")


def test_a_run_on_a_day_nothing_was_set(shop: Shop) -> None:
    shop.installs.pull("SP-1042", "2020-01-01")
    log(shop, "CR-1", "SP-1042", on="2025-03-04", by="M Okafor")
    referee(shop, "TR-9", "2025-03-14", "100.10")
    with pytest.raises(RuleError, match="nothing was set at SP-1042"):
        answer(shop, "CR-1", run_reference="TR-9", on="2025-03-14")


def test_a_void_run_answers_nothing(shop: Shop) -> None:
    shop.standards.add(
        ReferenceStandard.build(
            "RS-0001",
            maker="Radian",
            model_code="RD-23",
            certificate="OLD",
            certified_on="2010-01-01",
            certificate_due="2011-01-01",
            uncertainty="0.02",
        )
    )
    shop.runs.add(
        BenchRun.build(
            "TR-9",
            meter_serial="84-119302",
            bench_code="B2",
            standard_serial="RS-0001",
            kind=RunKind.REFEREE,
            tested_on="2025-03-14",
            technician="R Ellis",
            points=[
                BenchPoint.build("FL", amperes="30", volts="240", registration="100.10"),
                BenchPoint.build("LL", amperes="3", volts="240", registration="100.10"),
            ],
        )
    )
    log(shop, "CR-1", "SP-1042", on="2025-03-04", by="M Okafor")
    with pytest.raises(RuleError, match="answers nothing"):
        answer(shop, "CR-1", run_reference="TR-9", on="2025-03-14")


def test_the_fee_can_be_overridden(shop: Shop) -> None:
    log(shop, "CR-0", "SP-1042", on="2024-01-01", by="M Okafor")
    log(shop, "CR-1", "SP-1042", on="2025-03-04", by="M Okafor")
    referee(shop, "TR-9", "2025-03-14", "100.10")
    found = answer(shop, "CR-1", run_reference="TR-9", on="2025-03-14", fee=Money("40"))
    assert found.fee == Money("40.00")
