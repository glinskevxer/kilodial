"""A tampered service, from the cut seal to the estimate that settled it.

This is the path where the ordinary machinery deliberately stops working. A
meter that has been bypassed did not under register; it registered nothing for
whatever went round it, and every tool in the adjustment layer is built on a
registration. The package's answer is to refuse rather than to produce a number,
and this test is the statement of that: it walks the whole path and asserts at
each step which tool takes over from which.
"""

from __future__ import annotations

from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path

import pytest

from kilodial.adjust.compute import Adjustment, BilledMonth
from kilodial.adjust.rules import Direction, lookback_months
from kilodial.adjust.service import Refusal, raise_adjustment
from kilodial.estimate.basis import Basis
from kilodial.estimate.service import estimate_point, gap_for
from kilodial.install.point import MeterSet, ServicePoint
from kilodial.model.bench import Bench, ReferenceStandard
from kilodial.model.device import DeviceType
from kilodial.model.form import Service, Technology
from kilodial.model.meter import Meter, MeterState
from kilodial.model.run import RunKind
from kilodial.store.shop import Shop, open_shop
from kilodial.tamper.event import Finding, Standing
from kilodial.testing.record import Readings, build_run
from kilodial.units.money import Money

LAST_DAY = {1: 31, 2: 28, 3: 31, 4: 30, 5: 31, 6: 30, 7: 31, 8: 31, 9: 30, 10: 31, 11: 30, 12: 31}


@pytest.fixture
def shop(tmp_path: Path) -> Iterator[Shop]:
    opened = open_shop(tmp_path / "tampered.sqlite3", create=True)
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
    opened.meters.move("84-119302", MeterState.STOCK)
    opened.meters.move("84-119302", MeterState.SET)
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
        MeterSet.build("SP-1042", "84-119302", programmed_multiplier="1", set_on="2018-06-01")
    )
    for year in (2023, 2024, 2025):
        for month in range(1, 13):
            amount = "30.00" if (year, month) >= (2024, 7) else "100.00"
            opened.billing.add(
                "SP-1042",
                BilledMonth.of(
                    f"{year}-{month:02d}-01",
                    f"{year}-{month:02d}-{LAST_DAY[month]}",
                    amount,
                ),
            )
    yield opened
    opened.close()


def bench_it(shop: Shop, reference: str, reading: str, on: str) -> None:
    shop.runs.add(
        build_run(
            reference,
            device=shop.device_for("84-119302"),
            meter_serial="84-119302",
            bench_code="B2",
            standard_serial="RS-5511",
            kind=RunKind.AS_FOUND,
            tested_on=on,
            technician="R Ellis",
            readings=Readings.of(full_load=reading, light_load=reading),
        )
    )


def test_a_bypassed_service(shop: Shop) -> None:
    # The bill halved in July 2024 and nobody looked until the meter reader
    # noticed the seal. The meter itself is fine, and that is the point: an
    # accurate meter and a bill that fell off a cliff is what a bypass looks
    # like from the office.
    bench_it(shop, "TR-1", "100.10", "2025-06-30")
    assert shop.judge("TR-1").passed

    # Before anything is confirmed, the ordinary path applies and finds nothing
    # to adjust, because the meter is inside tolerance.
    quiet = raise_adjustment(shop, "SP-1042", on="2025-07-15")
    assert isinstance(quiet, Refusal)
    assert "inside the" in quiet.reason

    # A cut seal is logged. It is a suspicion and it changes nothing at all.
    shop.tamper.add(
        Finding.raise_finding(
            "TF-1",
            "SP-1042",
            "seal cut",
            found_on="2025-06-30",
            found_by="R Ellis",
            evidence="seal wire hanging",
        )
    )
    assert shop.tamper.get("TF-1").standing is Standing.SUSPECTED
    assert not shop.tamper.unmetered_at("SP-1042", "2025-07-15")
    still_quiet = raise_adjustment(shop, "SP-1042", on="2025-07-15")
    assert isinstance(still_quiet, Refusal)

    # The crew goes back and finds a jumper. Now it is confirmed, and what it
    # confirms is that the meter was not measuring what passed.
    shop.tamper.add(
        Finding.raise_finding(
            "TF-2", "SP-1042", "bypass", found_on="2025-07-02", found_by="M Okafor"
        )
    )
    shop.tamper.save(
        shop.tamper.get("TF-2").confirmed(
            on="2025-07-02", since="2024-07-01", evidence="jumper on the load side"
        )
    )
    assert shop.tamper.unmetered_at("SP-1042", "2025-07-15")

    # And the adjustment layer stops rather than producing a figure. This is the
    # assertion the whole test exists for.
    refused = raise_adjustment(shop, "SP-1042", on="2025-07-15")
    assert isinstance(refused, Refusal)
    assert "has to be estimated" in refused.reason

    # The gap is the period the finding covers, clipped to the days a meter was
    # actually set at the point.
    gap = gap_for(shop, "SP-1042", on="2025-07-15")
    assert gap.start.isoformat() == "2024-07-01"
    assert gap.end is not None
    assert gap.end.isoformat() == "2025-07-02"

    # Two bases hold, and the one that carries the season with it says the
    # customer should have been billed roughly what they were billed a year
    # earlier, which is three times what they actually paid.
    options = estimate_point(shop, "SP-1042", on="2025-07-15")
    assert [e.basis for e in options.offered] == [Basis.LAST_YEAR, Basis.NEIGHBOURS]
    last_year = options.best()
    assert last_year.basis is Basis.LAST_YEAR
    assert last_year.amount > Money("1000.00")
    assert options.spread().cents > 0

    # Somebody chooses, and their name goes on it.
    settled = shop.estimates.settle("ES-1", last_year, on="2025-07-20", by="M Okafor")
    assert settled.settled_by == "M Okafor"
    assert shop.estimates.total_for("SP-1042") == last_year.amount

    # Had the finding been a cut seal alone, the meter would still have been
    # measuring and the ordinary path would have applied, with a back bill
    # window three times as long as usual.
    assert (
        lookback_months(
            shop.accuracy_of_set(shop.installs.current("SP-1042"))  # type: ignore[arg-type]
        )
        == 60
    )

    # The book still hangs together, and the whole thing is on the record.
    assert shop.audit() == []
    assert [f.reference for f in shop.tamper.for_point("SP-1042")] == ["TF-1", "TF-2"]
    assert shop.summary()["estimates"] == 1


def test_a_slow_meter_on_a_tampered_service_reaches_further_back(shop: Shop) -> None:
    # A cut seal does not stop the meter measuring, so the ordinary adjustment
    # applies. What changes is how far back it reaches: three years rather than
    # one, because the customer knew.
    bench_it(shop, "TR-1", "96.00", "2025-06-30")
    ordinary = raise_adjustment(shop, "SP-1042", on="2025-07-15")
    assert isinstance(ordinary, Adjustment)
    assert ordinary.direction is Direction.BACK_BILL
    assert ordinary.period.span.start.isoformat() == "2024-06-30"

    shop.tamper.add(
        Finding.raise_finding(
            "TF-1", "SP-1042", "seal cut", found_on="2025-06-30", found_by="R Ellis"
        )
    )
    shop.tamper.save(
        shop.tamper.get("TF-1").confirmed(
            on="2025-07-01", since="2022-01-01", evidence="seal replaced with wire"
        )
    )
    longer = raise_adjustment(shop, "SP-1042", on="2025-07-15")
    assert isinstance(longer, Adjustment)
    assert longer.period.span.start.isoformat() == "2022-06-30"
    assert longer.billed > ordinary.billed
    assert longer.share == ordinary.share
    assert longer.share > Decimal(0)
