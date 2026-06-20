"""The interval ladder over eight seasons, which is the loop the scheme turns on.

A group's sample decides its interval. The interval decides which meters fall
due. Which meters get tested decides what the next sample looks like. That is a
loop, and every piece of it is tested on its own elsewhere; this walks it round
enough times to see the behaviour that only exists in the loop.

Three things it demonstrates and nothing else does:

A group that stays tight climbs the ladder one step at a time and cannot skip
one, however good the sample is. Eight good seasons take it from four years to
twenty five and no faster.

A single bad season drops it one step, not to the bottom, so a group is not
punished for a year for one bad batch.

A group that fails at the bottom does not go below it. It gets a mass test
instead, and the next season starts from four years again.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from kilodial.model.bench import Bench, ReferenceStandard
from kilodial.model.device import DeviceType
from kilodial.model.form import Technology
from kilodial.model.meter import Meter
from kilodial.model.run import RunKind
from kilodial.programme.season import run_sample
from kilodial.sampling.decision import Decision
from kilodial.sampling.group import Group
from kilodial.sampling.plan import INTERVAL_LADDER
from kilodial.store.shop import Shop, open_shop
from kilodial.testing.record import Readings, build_run
from kilodial.units.span import DateSpan

FLEET = 6
TIGHT = "100.10"
SCATTERED = ("98.40", "101.60")


@pytest.fixture
def shop(tmp_path: Path) -> Iterator[Shop]:
    opened = open_shop(tmp_path / "ladder.sqlite3", create=True)
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
    opened.standards.add(
        ReferenceStandard.build(
            "RS-5511",
            maker="Radian",
            model_code="RD-23",
            certificate="NVLAP-88214",
            certified_on="2010-01-01",
            certificate_due="2060-01-01",
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
            installed="2005-01-01",
        )
    )
    opened.groups.add(Group.build("G1", "Halvern R4S", device_keys=["Halvern/R4S"]))
    for index in range(FLEET):
        opened.meters.add(Meter.receive(f"84-11930{index}", "Halvern/R4S", acquired="2015-01-01"))
    yield opened
    opened.close()


def season(shop: Shop, year: int, *, tight: bool = True) -> Decision:
    """Bench the whole group in one year and judge the season."""
    for index in range(FLEET):
        reading = TIGHT if tight else SCATTERED[index % 2]
        shop.runs.add(
            build_run(
                f"TR-{year}-{index}",
                device=shop.device_for(f"84-11930{index}"),
                meter_serial=f"84-11930{index}",
                bench_code="B2",
                standard_serial="RS-5511",
                kind=RunKind.AS_FOUND,
                tested_on=f"{year}-03-04",
                technician="R Ellis",
                readings=Readings.of(full_load=reading, light_load=reading),
            )
        )
    _, decision = run_sample(
        shop,
        "G1",
        span=DateSpan(f"{year}-01-01", f"{year}-12-31"),
        on=f"{year}-12-31",
    )
    return decision


def test_eight_good_seasons_climb_the_ladder_one_step_at_a_time(shop: Shop) -> None:
    reached = [shop.plans.interval("G1")]
    for year in range(2025, 2033):
        decision = season(shop, year)
        assert decision.passed
        assert decision.moved in ("up", "held")
        reached.append(shop.plans.interval("G1"))
    assert reached[0] == INTERVAL_LADDER[0]
    assert reached[: len(INTERVAL_LADDER)] == list(INTERVAL_LADDER)
    assert reached[-1] == INTERVAL_LADDER[-1]


def test_the_top_of_the_ladder_holds(shop: Shop) -> None:
    for year in range(2025, 2033):
        season(shop, year)
    assert shop.plans.interval("G1") == INTERVAL_LADDER[-1]
    last = season(shop, 2033)
    assert last.moved == "held"
    assert shop.plans.interval("G1") == INTERVAL_LADDER[-1]


def test_one_bad_season_drops_a_group_one_step_and_no_further(shop: Shop) -> None:
    for year in (2025, 2026, 2027):
        season(shop, year)
    before = shop.plans.interval("G1")
    assert before == INTERVAL_LADDER[3]
    bad = season(shop, 2028, tight=False)
    assert not bad.passed
    assert bad.moved == "down"
    assert shop.plans.interval("G1") == INTERVAL_LADDER[2]


def test_a_group_recovers_at_the_same_speed_it_fell(shop: Shop) -> None:
    for year in (2025, 2026, 2027):
        season(shop, year)
    season(shop, 2028, tight=False)
    dropped = shop.plans.interval("G1")
    season(shop, 2029)
    assert shop.plans.interval("G1") == INTERVAL_LADDER[INTERVAL_LADDER.index(dropped) + 1]


def test_failing_at_the_bottom_is_a_mass_test_and_starts_again(shop: Shop) -> None:
    bad = season(shop, 2025, tight=False)
    assert bad.is_mass_test
    assert bad.interval_months is None
    assert shop.plans.interval("G1") == INTERVAL_LADDER[0]
    good = season(shop, 2026)
    assert good.previous_months == INTERVAL_LADDER[0]
    assert shop.plans.interval("G1") == INTERVAL_LADDER[1]


def test_the_history_replays_to_the_same_interval(shop: Shop) -> None:
    for year in (2025, 2026, 2027, 2028):
        season(shop, year, tight=year != 2027)
    history = shop.plans.history("G1")
    assert [d.decided_on.year for d in history] == [2025, 2026, 2027, 2028]
    assert [d.passed for d in history] == [True, True, False, True]
    assert shop.plans.interval("G1") == history[-1].interval_months
