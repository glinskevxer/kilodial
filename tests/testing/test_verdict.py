from __future__ import annotations

from decimal import Decimal

import pytest

from kilodial.model.bench import Bench, ReferenceStandard
from kilodial.model.device import DeviceType
from kilodial.model.form import Technology
from kilodial.model.run import BenchPoint, BenchRun, RunKind
from kilodial.testing.verdict import Outcome, judge
from kilodial.units.electrical import PowerFactor


def device(**over: object) -> DeviceType:
    args: dict[str, object] = {
        "form_code": "2S",
        "class_code": "200",
        "voltage": "240",
        "kh": "7.2",
        "technology": Technology.INDUCTION,
        "register_ratio": "100",
        "introduced": "2004-05-01",
    }
    args.update(over)
    return DeviceType.build("Halvern", "R4S", **args)  # type: ignore[arg-type]


def standard(**over: object) -> ReferenceStandard:
    args: dict[str, object] = {
        "maker": "Radian",
        "model_code": "RD-23",
        "certificate": "NVLAP-88214",
        "certified_on": "2024-11-04",
        "certificate_due": "2025-11-04",
        "uncertainty": "0.02",
    }
    args.update(over)
    return ReferenceStandard.build(str(args.pop("serial", "RS-5511")), **args)


def bench(**over: object) -> Bench:
    args: dict[str, object] = {
        "positions": 8,
        "standard_serial": "RS-5511",
        "max_amperes": "100",
        "max_volts": "480",
        "polyphase": True,
        "installed": "2018-03-01",
    }
    args.update(over)
    return Bench.build(str(args.pop("code", "B2")), "north wall", **args)  # type: ignore[arg-type]


def fl(pct: str = "100.10") -> BenchPoint:
    return BenchPoint.build("FL", amperes="30", volts="240", registration=pct)


def ll(pct: str = "99.80") -> BenchPoint:
    return BenchPoint.build("LL", amperes="3", volts="240", registration=pct)


def cr(moved: bool = False) -> BenchPoint:
    return BenchPoint.build("CR", amperes="0", volts="264", crept=moved)


def run(**over: object) -> BenchRun:
    args: dict[str, object] = {
        "meter_serial": "84-119302",
        "bench_code": "B2",
        "standard_serial": "RS-5511",
        "kind": RunKind.AS_FOUND,
        "tested_on": "2025-03-04",
        "technician": "R Ellis",
        "points": [fl(), ll()],
    }
    args.update(over)
    return BenchRun.build(str(args.pop("reference", "TR-1")), **args)  # type: ignore[arg-type]


def test_a_clean_run_passes() -> None:
    v = judge(run(), device(), standard=standard(), bench=bench())
    assert v.outcome is Outcome.PASSED
    assert v.passed
    assert v.registration is not None
    assert v.registration.percent == Decimal("100.0400")
    assert v.why() == "within band"
    assert str(v) == "TR-1 passed at 100.04%"


def test_an_expired_certificate_voids_the_run_before_the_numbers() -> None:
    v = judge(run(tested_on="2025-12-01"), device(), standard=standard(), bench=bench())
    assert v.outcome is Outcome.VOID
    assert v.average is None
    assert v.registration is None
    assert v.error is None
    assert "outside its certificate" in v.why()
    assert not v.outcome.is_usable


def test_a_run_judged_against_the_wrong_standard() -> None:
    v = judge(run(), device(), standard=standard(serial="RS-9999"), bench=bench())
    assert v.outcome is Outcome.VOID
    assert "run names standard RS-5511" in v.why()


def test_a_run_judged_against_the_wrong_bench() -> None:
    v = judge(run(), device(), standard=standard(), bench=bench(code="B7"))
    assert v.outcome is Outcome.VOID
    assert "run names bench B2" in v.why()


def test_a_bench_that_was_out_of_service() -> None:
    v = judge(run(), device(), standard=standard(), bench=bench(removed="2024-01-01"))
    assert v.outcome is Outcome.VOID
    assert "out of service" in v.why()


def test_a_bench_that_cannot_hold_the_meter() -> None:
    poly = device(form_code="16S", class_code="320")
    v = judge(
        run(
            points=[
                fl(),
                ll(),
                BenchPoint.build(
                    "PF",
                    amperes="15",
                    volts="240",
                    registration="99.90",
                    power_factor=PowerFactor.lagging("0.5"),
                ),
            ]
        ),
        poly,
        standard=standard(),
        bench=bench(polyphase=False),
    )
    assert v.outcome is Outcome.VOID
    assert "cannot hold" in v.why()


def test_an_incomplete_sequence_voids_the_run() -> None:
    v = judge(run(points=[fl()]), device(), standard=standard(), bench=bench())
    assert v.outcome is Outcome.VOID
    assert "missing its light_load point" in v.why()


def test_a_point_run_at_the_wrong_load_voids_the_run() -> None:
    wrong = BenchPoint.build("FL", amperes="3", volts="240", registration="100.10")
    v = judge(run(points=[wrong, ll()]), device(), standard=standard(), bench=bench())
    assert v.outcome is Outcome.VOID
    assert "was run at 3 A" in v.why()


def test_an_implausible_average_is_suspect_and_not_a_failure() -> None:
    v = judge(
        run(points=[fl("600.00"), ll("590.00")]),
        device(),
        standard=standard(),
        bench=bench(),
    )
    assert v.outcome is Outcome.SUSPECT
    assert v.average is not None
    assert "check the wiring and the multiplier" in v.why()
    assert not v.outcome.is_usable


def test_a_fast_meter_fails_on_the_weighted_average() -> None:
    v = judge(
        run(points=[fl("103.00"), ll("102.00")]),
        device(),
        standard=standard(),
        bench=bench(),
    )
    assert v.outcome is Outcome.FAILED
    assert v.error == Decimal("2.8000")
    assert "outside the +/-2.0 percent band" in v.why()


def test_creep_fails_a_run_that_would_otherwise_pass() -> None:
    v = judge(
        run(kind=RunKind.AS_LEFT, points=[fl("100.10"), ll("99.80"), cr(True)]),
        device(),
        standard=standard(),
        bench=bench(),
    )
    assert v.outcome is Outcome.FAILED
    assert "the disc crept" in v.why()


def test_a_held_disc_does_not_fail_the_run() -> None:
    v = judge(
        run(kind=RunKind.AS_LEFT, points=[fl("100.10"), ll("99.80"), cr(False)]),
        device(),
        standard=standard(),
        bench=bench(),
    )
    assert v.outcome is Outcome.PASSED


def test_a_single_point_out_of_band_fails_even_with_a_good_average() -> None:
    v = judge(
        run(points=[fl("100.90"), ll("95.50")]),
        device(),
        standard=standard(),
        bench=bench(),
    )
    assert v.outcome is Outcome.FAILED
    assert "light_load at 95.50%" in v.why()
    assert v.average is not None
    assert v.average.value.within(Decimal("2.0"))


def test_the_band_narrows_for_a_transformer_class_meter() -> None:
    points = [
        BenchPoint.build("FL", amperes="2.5", volts="240", registration="101.50"),
        BenchPoint.build("LL", amperes="0.25", volts="240", registration="101.50"),
        BenchPoint.build(
            "PF",
            amperes="1.25",
            volts="240",
            registration="101.50",
            power_factor=PowerFactor.lagging("0.5"),
        ),
    ]
    tight = judge(
        run(points=points),
        device(form_code="9S", class_code="20"),
        standard=standard(),
        bench=bench(),
    )
    assert tight.band.weighted == Decimal("1.33")
    assert tight.outcome is Outcome.FAILED

    ordinary_points = [
        BenchPoint.build("FL", amperes="30", volts="240", registration="101.50"),
        BenchPoint.build("LL", amperes="3", volts="240", registration="101.50"),
        BenchPoint.build(
            "PF",
            amperes="15",
            volts="240",
            registration="101.50",
            power_factor=PowerFactor.lagging("0.5"),
        ),
    ]
    ordinary = judge(
        run(points=ordinary_points),
        device(form_code="16S", class_code="320"),
        standard=standard(),
        bench=bench(),
    )
    assert ordinary.band.weighted == Decimal("2.0")
    assert ordinary.outcome is Outcome.PASSED


@pytest.mark.parametrize(
    ("outcome", "usable"),
    [
        (Outcome.PASSED, True),
        (Outcome.FAILED, True),
        (Outcome.VOID, False),
        (Outcome.SUSPECT, False),
    ],
)
def test_which_outcomes_can_be_relied_on(outcome: Outcome, usable: bool) -> None:
    assert outcome.is_usable is usable
    assert str(outcome) == outcome.value
