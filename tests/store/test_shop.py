from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from kilodial.errors import NotFoundError, RuleError
from kilodial.install.point import MeterSet, ServicePoint
from kilodial.model.bench import Bench, ReferenceStandard
from kilodial.model.device import DeviceType
from kilodial.model.form import Service, Technology
from kilodial.model.meter import Meter
from kilodial.model.run import BenchPoint, BenchRun, RunKind
from kilodial.store.shop import Shop, open_shop, require
from kilodial.testing.verdict import Outcome
from kilodial.units.registration import Registration
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
    opened.meters.add(Meter.receive("84-119302", "Halvern/R4S", acquired="2019-04-02"))
    opened.standards.add(
        ReferenceStandard.build(
            "RS-5511",
            maker="Radian",
            model_code="RD-23",
            certificate="NVLAP-88214",
            certified_on="2024-11-04",
            certificate_due="2025-11-04",
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
            installed="2018-03-01",
        )
    )
    yield opened
    opened.close()


def run(reference: str = "TR-1", **over: object) -> BenchRun:
    args: dict[str, object] = {
        "meter_serial": "84-119302",
        "bench_code": "B2",
        "standard_serial": "RS-5511",
        "kind": RunKind.AS_FOUND,
        "tested_on": "2025-03-04",
        "technician": "R Ellis",
        "points": [
            BenchPoint.build("FL", amperes="30", volts="240", registration="100.12"),
            BenchPoint.build("LL", amperes="3", volts="240", registration="99.60"),
        ],
    }
    args.update(over)
    return BenchRun.build(reference, **args)  # type: ignore[arg-type]


def test_the_device_behind_a_meter(shop: Shop) -> None:
    assert shop.device_for("84-119302").key == "Halvern/R4S"
    with pytest.raises(NotFoundError, match="meter"):
        shop.device_for("84-000000")


def test_judging_a_stored_run(shop: Shop) -> None:
    shop.runs.add(run())
    verdict = shop.judge("TR-1")
    assert verdict.outcome is Outcome.PASSED
    assert verdict.run_reference == "TR-1"


def test_judging_pulls_the_standard_the_run_named(shop: Shop) -> None:
    shop.standards.add(
        ReferenceStandard.build(
            "RS-7002",
            maker="Radian",
            model_code="RD-23",
            certificate="NVLAP-90001",
            certified_on="2025-06-01",
            certificate_due="2026-06-01",
            uncertainty="0.02",
        )
    )
    shop.runs.add(run())
    shop.benches.save(
        Bench.build(
            "B2",
            "north wall",
            positions=8,
            standard_serial="RS-7002",
            max_amperes="100",
            max_volts="480",
            polyphase=True,
            installed="2018-03-01",
        )
    )
    assert shop.benches.standard_for("B2").serial == "RS-7002"
    assert shop.judge("TR-1").outcome is Outcome.PASSED


def test_a_run_against_an_expired_certificate_is_void(shop: Shop) -> None:
    shop.runs.add(run(tested_on="2025-12-01"))
    assert shop.judge("TR-1").outcome is Outcome.VOID


def test_history_pairs_every_run_with_a_verdict(shop: Shop) -> None:
    shop.runs.add(run("TR-1", tested_on="2025-01-06"))
    shop.runs.add(
        run(
            "TR-2",
            tested_on="2025-03-04",
            points=[
                BenchPoint.build("FL", amperes="30", volts="240", registration="104.00"),
                BenchPoint.build("LL", amperes="3", volts="240", registration="103.00"),
            ],
        )
    )
    history = shop.history("84-119302")
    assert [r.reference for r, _ in history] == ["TR-1", "TR-2"]
    assert [v.outcome for _, v in history] == [Outcome.PASSED, Outcome.FAILED]


def test_summary_counts_every_table(shop: Shop) -> None:
    shop.runs.add(run())
    assert shop.summary() == {
        "device types": 1,
        "meters": 1,
        "standards": 1,
        "benches": 1,
        "runs": 1,
        "transformers": 0,
        "service points": 0,
        "meter sets": 0,
    }


def test_a_clean_book_audits_clean(shop: Shop) -> None:
    shop.runs.add(run())
    assert shop.audit() == []


def test_the_audit_finds_a_meter_pointing_at_nothing(shop: Shop) -> None:
    shop.book.connection.execute(
        "UPDATE meter SET device_key = 'Nowhere/X1' WHERE serial = '84-119302'"
    )
    faults = shop.audit()
    assert any("names device type Nowhere/X1" in f for f in faults)


def test_the_audit_finds_a_bench_pointing_at_nothing(shop: Shop) -> None:
    shop.book.connection.execute("UPDATE bench SET standard_serial = 'RS-0000'")
    assert any("names standard RS-0000" in f for f in shop.audit())


def test_the_audit_finds_a_run_pointing_at_nothing(shop: Shop) -> None:
    shop.runs.add(run())
    shop.book.connection.execute("DELETE FROM meter WHERE serial = '84-119302'")
    assert any("run TR-1 names meter 84-119302" in f for f in shop.audit())


def test_a_shop_transaction_rolls_back(shop: Shop) -> None:
    def add_then_fail() -> None:
        with shop.transaction() as inner:
            inner.meters.add(Meter.receive("84-119999", "Halvern/R4S", acquired="2020-01-01"))
            raise RuntimeError("no")

    with pytest.raises(RuntimeError):
        add_then_fail()
    assert shop.meters.find("84-119999") is None


def test_the_shop_closes_itself(tmp_path: Path) -> None:
    with open_shop(tmp_path / "one.sqlite3", create=True) as opened:
        assert opened.summary()["meters"] == 0
        assert str(opened).startswith("shop book at ")


def test_require_raises_on_nothing() -> None:
    require("something", "meter", "X")
    with pytest.raises(NotFoundError, match="meter"):
        require(None, "meter", "84-119302")


def a_point(code: str = "SP-1042", **over: object) -> ServicePoint:
    args: dict[str, object] = {
        "account": "44-9021",
        "address": "18 Fenwick Row",
        "service": Service.SINGLE_PHASE_3W,
        "voltage": "240",
        "rate_code": "R1",
        "energised": "2011-06-14",
    }
    args.update(over)
    return ServicePoint.build(code, **args)  # type: ignore[arg-type]


def a_ct(serial: str = "CT-8841", **over: object) -> InstrumentTransformer:
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
    return InstrumentTransformer.build(serial, **args)  # type: ignore[arg-type]


def test_the_summary_counts_the_new_tables(shop: Shop) -> None:
    assert shop.summary()["transformers"] == 0
    assert shop.summary()["service points"] == 0
    assert shop.summary()["meter sets"] == 0


def test_a_self_contained_installation(shop: Shop) -> None:
    shop.points.add(a_point())
    shop.installs.set_meter(
        MeterSet.build("SP-1042", "84-119302", programmed_multiplier="1", set_on="2019-05-02")
    )
    shop.runs.add(
        run(
            points=[
                BenchPoint.build("FL", amperes="30", volts="240", registration="100.30"),
                BenchPoint.build("LL", amperes="3", volts="240", registration="100.30"),
            ]
        )
    )
    found = shop.installed_accuracy("SP-1042")
    assert found.overall == Registration("100.30")
    assert found.multiplier_is_right


def test_a_transformer_rated_installation(shop: Shop) -> None:
    shop.points.add(a_point())
    shop.transformers.add(a_ct(rcf="1.0020"))
    shop.installs.set_meter(
        MeterSet.build(
            "SP-1042",
            "84-119302",
            ct_serial="CT-8841",
            programmed_multiplier="40",
            set_on="2019-05-02",
        )
    )
    shop.runs.add(run())
    found = shop.installed_accuracy("SP-1042")
    assert found.current_transformer is not None
    assert found.overall < found.meter


def test_an_installation_with_nothing_set(shop: Shop) -> None:
    shop.points.add(a_point())
    with pytest.raises(RuleError, match="nothing was set at SP-1042"):
        shop.installed_accuracy("SP-1042")


def test_an_installation_whose_meter_was_never_tested(shop: Shop) -> None:
    shop.points.add(a_point())
    shop.installs.set_meter(
        MeterSet.build("SP-1042", "84-119302", programmed_multiplier="1", set_on="2019-05-02")
    )
    with pytest.raises(RuleError, match="no usable as found run"):
        shop.installed_accuracy("SP-1042")


def test_a_void_run_does_not_count_as_an_as_found_reading(shop: Shop) -> None:
    shop.points.add(a_point())
    shop.installs.set_meter(
        MeterSet.build("SP-1042", "84-119302", programmed_multiplier="1", set_on="2019-05-02")
    )
    shop.runs.add(run("TR-1", tested_on="2025-12-01"))
    with pytest.raises(RuleError, match="no usable as found run"):
        shop.installed_accuracy("SP-1042")


def test_the_latest_as_found_run_is_the_one_that_counts(shop: Shop) -> None:
    shop.points.add(a_point())
    shop.installs.set_meter(
        MeterSet.build("SP-1042", "84-119302", programmed_multiplier="1", set_on="2019-05-02")
    )
    shop.runs.add(run("TR-1", tested_on="2025-01-06"))
    shop.runs.add(
        run(
            "TR-2",
            tested_on="2025-03-04",
            points=[
                BenchPoint.build("FL", amperes="30", volts="240", registration="101.00"),
                BenchPoint.build("LL", amperes="3", volts="240", registration="101.00"),
            ],
        )
    )
    assert shop.as_found_registration("84-119302") == Registration("101.00")


def test_an_as_left_run_is_not_an_as_found_reading(shop: Shop) -> None:
    shop.runs.add(run("TR-1", kind=RunKind.AS_LEFT))
    with pytest.raises(RuleError, match="no usable as found run"):
        shop.as_found_registration("84-119302")


def test_unusable_runs_are_listed(shop: Shop) -> None:
    shop.runs.add(run("TR-1"))
    shop.runs.add(run("TR-2", tested_on="2025-12-01"))
    unusable = shop.unusable_runs()
    assert [r.reference for r, _ in unusable] == ["TR-2"]


def test_the_audit_finds_a_set_pointing_at_nothing(shop: Shop) -> None:
    shop.points.add(a_point())
    shop.installs.set_meter(
        MeterSet.build(
            "SP-1042",
            "84-119302",
            ct_serial="CT-0000",
            programmed_multiplier="40",
            set_on="2019-05-02",
        )
    )
    assert any("names current transformer CT-0000" in f for f in shop.audit())


def test_the_audit_finds_a_set_naming_a_meter_that_is_gone(shop: Shop) -> None:
    shop.points.add(a_point())
    shop.installs.set_meter(
        MeterSet.build("SP-1042", "84-119302", programmed_multiplier="1", set_on="2019-05-02")
    )
    shop.book.connection.execute("DELETE FROM meter WHERE serial = '84-119302'")
    assert any("names meter 84-119302" in f for f in shop.audit())
