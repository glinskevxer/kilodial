from __future__ import annotations

from decimal import Decimal

import pytest

from kilodial.errors import ConfigError
from kilodial.model.bench import Bench, ReferenceStandard
from kilodial.model.device import DeviceType
from kilodial.model.form import Technology
from kilodial.model.meter import Meter, MeterState
from kilodial.model.run import BenchPoint, BenchRun, RunKind
from kilodial.store import codec
from kilodial.units.electrical import PowerFactor


def a_device() -> DeviceType:
    return DeviceType.build(
        "Halvern",
        "R4S",
        form_code="2S",
        class_code="200",
        voltage="240",
        kh="7.2",
        technology=Technology.INDUCTION,
        register_ratio="100",
        demand_capable=True,
        introduced="2004-05-01",
        retired="2016-12-31",
    )


def a_standard() -> ReferenceStandard:
    return ReferenceStandard.build(
        "RS-5511",
        maker="Radian",
        model_code="RD-23",
        certificate="NVLAP-88214",
        certified_on="2024-11-04",
        certificate_due="2025-11-04",
        uncertainty="0.02",
    )


def a_bench() -> Bench:
    return Bench.build(
        "B2",
        "north wall",
        positions=8,
        standard_serial="RS-5511",
        max_amperes="100",
        max_volts="480",
        polyphase=True,
        installed="2018-03-01",
        removed="2026-01-31",
    )


def a_run() -> BenchRun:
    return BenchRun.build(
        "TR-1",
        meter_serial="84-119302",
        bench_code="B2",
        standard_serial="RS-5511",
        kind=RunKind.AS_FOUND,
        tested_on="2025-03-04",
        technician="R Ellis",
        note="cover cracked",
        points=[
            BenchPoint.build("FL", amperes="30", volts="240", registration="100.12"),
            BenchPoint.build(
                "PF",
                amperes="15",
                volts="240",
                registration="99.40",
                power_factor=PowerFactor.lagging("0.5"),
            ),
            BenchPoint.build("CR", amperes="0", volts="264", crept=False),
        ],
    )


def test_a_device_round_trips() -> None:
    device = a_device()
    assert codec.read_device(codec.device_row(device)) == device


def test_a_solid_state_device_round_trips_without_a_ratio() -> None:
    device = DeviceType.build(
        "Vantage",
        "SM3",
        form_code="16S",
        class_code="320",
        voltage="277",
        kh="1.0",
        technology=Technology.SOLID_STATE,
        introduced="2018-01-01",
    )
    row = codec.device_row(device)
    assert row[7] is None
    assert codec.read_device(row) == device


def test_a_meter_round_trips() -> None:
    meter = Meter.receive("84-119302", "Halvern/R4S", acquired="2019-04-02", seal="BX4471")
    assert codec.read_meter(codec.meter_row(meter)) == meter
    scrapped = meter.moved_to(MeterState.SCRAP, on="2025-06-01")
    assert codec.read_meter(codec.meter_row(scrapped)) == scrapped


def test_a_standard_round_trips() -> None:
    standard = a_standard()
    assert codec.read_standard(codec.standard_row(standard)) == standard


def test_a_bench_round_trips() -> None:
    bench = a_bench()
    assert codec.read_bench(codec.bench_row(bench)) == bench


def test_a_run_and_its_points_round_trip() -> None:
    run = a_run()
    rows = [codec.point_row(run.reference, i, p) for i, p in enumerate(run.points)]
    points = [codec.read_point(r) for r in rows]
    assert codec.read_run(codec.run_row(run), points) == run


def test_a_creep_point_keeps_its_three_states() -> None:
    held = BenchPoint.build("CR", amperes="0", volts="264", crept=False)
    crept = BenchPoint.build("CR", amperes="0", volts="264", crept=True)
    load = BenchPoint.build("FL", amperes="30", volts="240", registration="100")
    assert codec.point_row("TR-1", 0, held)[8] == 0
    assert codec.point_row("TR-1", 0, crept)[8] == 1
    assert codec.point_row("TR-1", 0, load)[8] is None
    assert codec.read_point(codec.point_row("TR-1", 0, held)).crept is False
    assert codec.read_point(codec.point_row("TR-1", 0, crept)).crept is True
    assert codec.read_point(codec.point_row("TR-1", 0, load)).crept is None


def test_decimals_go_in_as_text() -> None:
    row = codec.device_row(a_device())
    assert row[5] == "7.2"
    assert isinstance(row[5], str)
    assert codec.read_device(row).kh == Decimal("7.2")


def test_a_row_holding_a_state_nobody_knows() -> None:
    row = list(codec.meter_row(Meter.receive("X1099", "a/b", acquired="2020-01-01")))
    row[2] = "melted"
    with pytest.raises(ConfigError, match="not a meter state"):
        codec.read_meter(tuple(row))


def test_a_row_holding_a_point_kind_nobody_knows() -> None:
    run = a_run()
    row = list(codec.point_row(run.reference, 0, run.points[0]))
    row[2] = "ZZ"
    with pytest.raises(ConfigError, match="not a test point kind"):
        codec.read_point(tuple(row))


def test_a_row_holding_a_run_kind_nobody_knows() -> None:
    row = list(codec.run_row(a_run()))
    row[4] = "guesswork"
    with pytest.raises(ConfigError, match="not a run kind"):
        codec.read_run(tuple(row), [])


def test_a_row_holding_a_technology_nobody_knows() -> None:
    row = list(codec.device_row(a_device()))
    row[6] = "clockwork"
    with pytest.raises(ConfigError, match="not a technology"):
        codec.read_device(tuple(row))
