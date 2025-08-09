"""Stand a whole shop up in a temporary book and drive it end to end.

This is not a test in the pytest sense and it is not trying to be. It runs
against the installed package rather than the source tree, which is the one
thing the test suite cannot check: a module missing from the wheel, a console
script that does not resolve, a package data file that was never included. All
of those pass every test and fail the first time somebody installs it.

So the shape here is deliberately end to end and shallow. It catalogues a meter
type, receives a meter, certifies a standard, benches the meter, sets it at a
service point, bills the customer, finds the meter fast, and works out the
refund. Every step asserts one thing. If any of it is broken the wheel is
broken.
"""

from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

from kilodial import __version__
from kilodial.adjust.compute import Adjustment, BilledMonth
from kilodial.adjust.rules import Direction
from kilodial.adjust.service import raise_adjustment
from kilodial.install.point import MeterSet, ServicePoint
from kilodial.model.bench import Bench, ReferenceStandard
from kilodial.model.device import DeviceType
from kilodial.model.form import Service, Technology
from kilodial.model.meter import Meter, MeterState
from kilodial.model.run import RunKind
from kilodial.programme import roster
from kilodial.sampling.group import Group
from kilodial.store.shop import Shop, open_shop
from kilodial.testing.record import Readings, build_run
from kilodial.testing.verdict import Outcome
from kilodial.tools import FAILED, OK

LAST_DAY = {1: 31, 2: 28, 3: 31, 4: 30, 5: 31, 6: 30}


def stand_up(shop: Shop) -> None:
    """Put a small but complete shop on an empty book."""
    shop.devices.add(
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
    shop.meters.add(Meter.receive("84-119302", "Halvern/R4S", acquired="2015-01-01"))
    shop.standards.add(
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
    shop.benches.add(
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
    shop.points.add(
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
    shop.installs.set_meter(
        MeterSet.build("SP-1042", "84-119302", programmed_multiplier="1", set_on="2019-05-02")
    )
    shop.groups.add(Group.build("G1", "Halvern R4S", device_keys=["Halvern/R4S"]))
    for index in range(1, 7):
        shop.billing.add(
            "SP-1042",
            BilledMonth.of(f"2025-{index:02d}-01", f"2025-{index:02d}-{LAST_DAY[index]}", "100.00"),
        )


def walk(shop: Shop) -> list[str]:
    """Drive the shop through a whole cycle, returning what it did."""
    steps: list[str] = []
    stand_up(shop)
    steps.append(f"stood up {shop.summary()}")

    shop.meters.move("84-119302", MeterState.STOCK)
    shop.meters.move("84-119302", MeterState.SET)
    steps.append(f"meter state {shop.meters.get('84-119302').state}")

    run = build_run(
        "TR-1",
        device=shop.device_for("84-119302"),
        meter_serial="84-119302",
        bench_code="B2",
        standard_serial="RS-5511",
        kind=RunKind.AS_FOUND,
        tested_on="2025-06-30",
        technician="R Ellis",
        readings=Readings.of(full_load="103.20", light_load="102.40"),
    )
    shop.runs.add(run)
    verdict = shop.judge("TR-1")
    _expect(verdict.outcome is Outcome.FAILED, f"expected a failure, got {verdict.outcome}")
    steps.append(f"judged {verdict}")

    accuracy = shop.installed_accuracy("SP-1042")
    _expect(accuracy.multiplier_is_right, "the multiplier should be right")
    steps.append(f"installed at {accuracy.overall}")

    found = raise_adjustment(shop, "SP-1042", on="2025-07-15")
    _expect(isinstance(found, Adjustment), f"expected an adjustment, got {found}")
    assert isinstance(found, Adjustment)
    _expect(found.direction is Direction.REFUND, "a fast meter refunds the customer")
    _expect(found.total.cents > 0, "the refund should be more than nothing")
    steps.append(f"adjustment {found.explain()}")

    built = roster.build(shop, on="2026-01-01")
    _expect(len(built) == 1, f"expected one meter in the programme, got {len(built)}")
    steps.append(f"programme {built.counts()}")

    faults = shop.audit()
    _expect(not faults, f"the book should audit clean, got {faults}")
    steps.append("book audits clean")
    return steps


def _expect(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def run_smoke() -> list[str]:
    """Do the whole walk on a throwaway book."""
    with tempfile.TemporaryDirectory() as where:
        shop = open_shop(Path(where) / "smoke.sqlite3", create=True)
        try:
            steps = walk(shop)
        finally:
            shop.close()
    return steps


def main(argv: list[str] | None = None) -> int:
    """Run the walk and print each step unless asked not to."""
    parser = argparse.ArgumentParser(description="drive an installed kilodial end to end")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)
    try:
        steps = run_smoke()
    except AssertionError as exc:
        print(f"smoke failed: {exc}")
        return FAILED
    if not args.quiet:
        for step in steps:
            print(step)
    print(f"kilodial {__version__} smoke passed in {len(steps)} steps")
    return OK


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())


__all__ = ["LAST_DAY", "main", "run_smoke", "stand_up", "walk"]
