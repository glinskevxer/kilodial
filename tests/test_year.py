"""A year in the shop, driven through the package rather than the command line.

Every other test in this suite checks one thing. This one checks that the things
fit together over a period long enough for the interactions to show up: a group
whose sample moves its interval, which changes who is due the following season,
which changes what the commission report says; a meter that fails, gets
adjusted, gets repaired and goes back out; a customer who asks twice.

It is deliberately long and deliberately linear. A reader following it should be
able to see the shop's year, and a failure in it should point at the step rather
than at a fixture.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from kilodial.adjust.compute import Adjustment, BilledMonth
from kilodial.adjust.rules import Direction
from kilodial.adjust.service import raise_adjustment
from kilodial.complaint.request import Charge
from kilodial.complaint.service import answer, log
from kilodial.install.point import MeterSet, ServicePoint
from kilodial.model.bench import Bench, ReferenceStandard
from kilodial.model.device import DeviceType
from kilodial.model.form import Service, Technology
from kilodial.model.meter import Meter, MeterState
from kilodial.model.repair import Fault, Repair
from kilodial.model.run import RunKind
from kilodial.model.technician import Grade, Technician
from kilodial.orders.order import OrderKind, OrderState, WorkOrder
from kilodial.orders.planner import raise_orders
from kilodial.programme import roster, rota
from kilodial.programme.schedule import DueState
from kilodial.programme.season import run_sample
from kilodial.report import commission, register
from kilodial.sampling.group import Group
from kilodial.store.shop import Shop, open_shop
from kilodial.testing.record import Readings, build_run
from kilodial.testing.verdict import Outcome
from kilodial.units.span import DateSpan

LAST_DAY = {1: 31, 2: 28, 3: 31, 4: 30, 5: 31, 6: 30, 7: 31, 8: 31, 9: 30, 10: 31, 11: 30, 12: 31}
FLEET = 6


@pytest.fixture
def shop(tmp_path: Path) -> Iterator[Shop]:
    opened = open_shop(tmp_path / "year.sqlite3", create=True)
    yield opened
    opened.close()


def point_code(index: int) -> str:
    return f"SP-10{index:02d}"


def serial(index: int) -> str:
    return f"84-11930{index}"


def stand_up(shop: Shop) -> None:
    """A small utility with six services on it, all set in 2015."""
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
            positions=4,
            standard_serial="RS-5511",
            max_amperes="100",
            max_volts="480",
            polyphase=True,
            installed="2010-01-01",
        )
    )
    shop.technicians.add(
        Technician.build(
            "T-441",
            "R Ellis",
            grade=Grade.SUPERVISOR,
            certified_on="2020-01-01",
            certificate_due="2030-01-01",
        )
    )
    shop.groups.add(Group.build("G1", "Halvern R4S", device_keys=["Halvern/R4S"]))
    for index in range(FLEET):
        shop.meters.add(Meter.receive(serial(index), "Halvern/R4S", acquired="2015-01-01"))
        shop.meters.move(serial(index), MeterState.STOCK)
        shop.meters.move(serial(index), MeterState.SET)
        shop.points.add(
            ServicePoint.build(
                point_code(index),
                account=f"44-90{index:02d}",
                address=f"{index + 1} Fenwick Row",
                service=Service.SINGLE_PHASE_3W,
                voltage="240",
                rate_code="R1",
                energised="2011-06-14",
            )
        )
        shop.installs.set_meter(
            MeterSet.build(
                point_code(index),
                serial(index),
                programmed_multiplier="1",
                set_on="2015-06-01",
            )
        )
        for month in range(1, 13):
            for year in (2024, 2025):
                shop.billing.add(
                    point_code(index),
                    BilledMonth.of(
                        f"{year}-{month:02d}-01",
                        f"{year}-{month:02d}-{LAST_DAY[month]}",
                        "100.00",
                    ),
                )


def bench_it(shop: Shop, index: int, reading: str, on: str, reference: str) -> None:
    run = build_run(
        reference,
        device=shop.device_for(serial(index)),
        meter_serial=serial(index),
        bench_code="B2",
        standard_serial="RS-5511",
        kind=RunKind.AS_FOUND,
        tested_on=on,
        technician="R Ellis",
        badge="T-441",
        readings=Readings.of(full_load=reading, light_load=reading),
    )
    shop.runs.add(run)


def test_a_year_in_the_shop(shop: Shop) -> None:
    stand_up(shop)
    assert shop.summary()["meters"] == FLEET
    assert shop.audit() == []

    # January. Every meter is overdue because none has ever been tested, and the
    # planner raises an order per meter at the priority its lateness earns.
    built = roster.build(shop, on="2025-01-06")
    assert built.counts()[DueState.OVERDUE] == FLEET
    planned = raise_orders(shop, on="2025-01-06")
    assert planned.count == FLEET
    assert shop.orders.count() == FLEET

    # The bench takes four at a time, so two orders wait.
    day = rota.plan_day(shop, on="2025-01-07")
    assert day.placed == 4
    assert len(day.unplaced) == 2
    assert day.unplaced[0][1] == "B2 is full"

    # March. Five meters come back clean and one is three percent fast.
    for index in range(FLEET):
        reading = "103.00" if index == 3 else "100.10"
        bench_it(shop, index, reading, "2025-03-04", f"TR-{index}")
    verdicts = [shop.judge(f"TR-{index}").outcome for index in range(FLEET)]
    assert verdicts.count(Outcome.PASSED) == FLEET - 1
    assert verdicts.count(Outcome.FAILED) == 1

    # Every test order closes against the run that answered it.
    for index, order in enumerate(shop.orders.live()):
        shop.orders.save(order.done(on="2025-03-04", run_reference=f"TR-{index}"))
    assert shop.orders.counts_by_state()[OrderState.DONE] == FLEET

    # The fast meter owes its customer a refund, and the tariff reaches back five
    # years, which is further than the meter has been set at that point.
    found = raise_adjustment(shop, point_code(3), on="2025-03-14")
    assert isinstance(found, Adjustment)
    assert found.direction is Direction.REFUND
    assert found.period.span.start.isoformat() == "2020-03-04"
    assert found.billed.cents > 0

    # Nothing else on the book is adjustable, and the register says why.
    priced = register.gather(shop, on="2025-03-14")
    assert len(priced.priced) == 1
    assert len(priced.passed_over) == FLEET - 1
    assert all("inside the" in why for _, why in priced.passed_over)

    # The fast meter comes out, is repaired, and goes back to stock.
    shop.installs.pull(point_code(3), "2025-03-20")
    shop.meters.move(serial(3), MeterState.PULLED)
    shop.meters.move(serial(3), MeterState.REPAIR)
    shop.orders.add(
        WorkOrder.raise_order("WO-R1", OrderKind.REPAIR, serial(3), raised_on="2025-03-20")
    )
    shop.repairs.add(
        Repair.build(
            "RP-1",
            serial(3),
            Fault.BEARING,
            repaired_on="2025-03-21",
            by="R Ellis",
            hours="1",
            parts="12.40",
            replacement_cost="184.00",
        )
    )
    shop.orders.save(
        shop.orders.get("WO-R1").done(
            on="2025-03-21", disposition="returned", repair_reference="RP-1"
        )
    )
    shop.meters.move(serial(3), MeterState.STOCK)
    assert shop.repairs.counts_by_fault()[Fault.BEARING] == 1
    assert shop.repairs.get("RP-1").was_worth_it

    # June. The season is judged, and this is the interaction the whole scheme
    # turns on: one meter in six outside the band takes the group past the five
    # percent failure rule, so a season where five meters were fine ends with the
    # group at the bottom of the ladder and facing a mass test.
    season, decision = run_sample(
        shop, "G1", span=DateSpan("2025-01-01", "2025-06-30"), on="2025-06-30"
    )
    assert season.tested == FLEET
    assert not decision.passed
    assert decision.is_mass_test
    assert any("outside the band" in reason for reason in decision.reasons())
    assert shop.plans.interval("G1") == 48

    # The fleet is still current on the four year interval it started on, because
    # every meter was tested in March.
    assert roster.build(shop, on="2026-01-06").counts()[DueState.OVERDUE] == 0
    assert roster.build(shop, on="2031-06-06").counts()[DueState.OVERDUE] > 0

    # A second season with the bad meter out of the population passes and moves
    # the group up, which is the same rule read the other way.
    shop.meters.move(serial(3), MeterState.SCRAP, on="2025-07-01")
    for index in range(FLEET):
        if index == 3:
            continue
        bench_it(shop, index, "100.10", "2025-09-04", f"TR-B{index}")
    _, second = run_sample(shop, "G1", span=DateSpan("2025-07-01", "2025-12-31"), on="2025-12-31")
    assert second.passed
    assert shop.plans.interval("G1") == 72

    # July. A customer asks for a test, and gets one free.
    log(shop, "CR-1", point_code(0), on="2025-07-01", by="M Okafor")
    referee = build_run(
        "TR-REF",
        device=shop.device_for(serial(0)),
        meter_serial=serial(0),
        bench_code="B2",
        standard_serial="RS-5511",
        kind=RunKind.REFEREE,
        tested_on="2025-07-10",
        technician="R Ellis",
        badge="T-441",
        readings=Readings.of(full_load="100.20", light_load="100.20"),
    )
    shop.runs.add(referee)
    first = answer(shop, "CR-1", run_reference="TR-REF", on="2025-07-10")
    assert first.charge is Charge.WAIVED_FREE

    # The commission report at the end of the year, and the thing worth noticing
    # is what the scrapped meter did to it. It is out of the population, so the
    # filing describes five meters and the failure that started all of this is
    # not in the count. That is right and it is also why the sample decision is
    # kept as its own record: the report describes the fleet as it stands and the
    # decision describes what was found.
    filing = commission.build(shop, first="2025-01-01", last="2025-12-31")
    facts = dict(filing.sections[0].facts)
    assert facts["meters in groups"] == str(FLEET - 1)
    assert facts["meters tested"] == str(FLEET - 1)
    assert facts["outside tolerance"] == "0"
    assert facts["groups short of their sample"] == "0"
    assert [d.is_mass_test for d in shop.plans.history("G1")] == [True, False]
    requests = dict(filing.sections[2].facts)
    assert requests["requested"] == "1"
    assert requests["answered"] == "1"

    # And the book still hangs together.
    assert shop.audit() == []
    assert shop.book.check() == []
