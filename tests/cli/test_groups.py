from __future__ import annotations

import pytest

from tests.cli.conftest import Invoke


@pytest.fixture
def shop(started: Invoke) -> Invoke:
    started(
        "device",
        "add",
        "Halvern",
        "R4S",
        "--form",
        "2S",
        "--class",
        "200",
        "--volts",
        "240",
        "--kh",
        "7.2",
        "--ratio",
        "100",
        "--introduced",
        "2004-05-01",
    )
    started(
        "standard",
        "add",
        "RS-5511",
        "--maker",
        "Radian",
        "--model",
        "RD-23",
        "--certificate",
        "NVLAP-88214",
        "--certified",
        "2019-01-01",
        "--due",
        "2035-01-01",
        "--uncertainty",
        "0.02",
    )
    started(
        "bench",
        "add",
        "B2",
        "north wall",
        "--positions",
        "8",
        "--standard",
        "RS-5511",
        "--max-amps",
        "100",
        "--max-volts",
        "480",
        "--installed",
        "2010-01-01",
    )
    started("group", "add", "G1", "Halvern R4S", "--type", "Halvern/R4S")
    return started


def stock(invoke: Invoke, serial: str, acquired: str = "2015-01-01") -> None:
    invoke("meter", "receive", serial, "--type", "Halvern/R4S", "--acquired", acquired)


def bench(invoke: Invoke, reference: str, serial: str, on: str, pct: str = "100.10") -> None:
    invoke(
        "run",
        "record",
        reference,
        "--meter",
        serial,
        "--bench",
        "B2",
        "--on",
        on,
        "--by",
        "R Ellis",
        "--fl",
        pct,
        "--ll",
        pct,
    )


def test_adding_a_group(shop: Invoke) -> None:
    result = shop("group", "list")
    assert "G1" in result.output
    assert "48" in result.output


def test_a_group_with_stacked_criteria(shop: Invoke) -> None:
    result = shop(
        "group",
        "add",
        "G2",
        "induction 2S",
        "--class",
        "200",
        "--tech",
        "induction",
        "--form",
        "2S",
        "--acquired-from",
        "2015-01-01",
    )
    assert "class CL200" in result.output
    assert "form 2S" in result.output


def test_a_technology_nobody_stocks(shop: Invoke) -> None:
    result = shop("group", "add", "G2", "clockwork", "--tech", "clockwork", expect=2)
    assert "is not one of" in result.output


def test_members_follow_the_criteria(shop: Invoke) -> None:
    stock(shop, "84-119302")
    stock(shop, "84-119303")
    result = shop("group", "members", "G1")
    assert "84-119302" in result.output
    assert "84-119303" in result.output


def test_showing_a_group_with_no_history(shop: Invoke) -> None:
    stock(shop, "84-119302")
    result = shop("group", "show", "G1")
    assert "population" in result.output
    assert "48 months" in result.output


def test_a_group_nobody_has(shop: Invoke) -> None:
    result = shop("group", "show", "G9", expect=2)
    assert "no sampling group" in result.output


def test_sampling_a_tight_group_moves_it_up(shop: Invoke) -> None:
    for n in range(5):
        serial = f"84-11930{n}"
        stock(shop, serial)
        bench(shop, f"TR-{n}", serial, "2025-03-04")
    result = shop(
        "group",
        "sample",
        "G1",
        "--from",
        "2025-01-01",
        "--to",
        "2025-06-30",
        "--on",
        "2025-06-30",
    )
    assert "5 readings from a population of 5" in result.output
    assert "48 months to 72 months" in result.output
    assert "72" in shop("group", "list").output


def test_sampling_a_scattered_group_is_a_mass_test(shop: Invoke) -> None:
    for n in range(6):
        serial = f"84-11930{n}"
        stock(shop, serial)
        bench(shop, f"TR-{n}", serial, "2025-03-04", "98.5" if n % 2 else "101.5")
    result = shop(
        "group",
        "sample",
        "G1",
        "--from",
        "2025-01-01",
        "--to",
        "2025-06-30",
        "--on",
        "2025-06-30",
        expect=1,
    )
    assert "mass test" in result.output
    assert "outside the +/-2.0 percent band" in result.output


def test_sampling_an_empty_group(shop: Invoke) -> None:
    result = shop(
        "group",
        "sample",
        "G1",
        "--from",
        "2025-01-01",
        "--to",
        "2025-06-30",
        "--on",
        "2025-06-30",
        expect=2,
    )
    assert "no meters in it" in result.output


def test_the_history_shows_up_after_a_sample(shop: Invoke) -> None:
    for n in range(5):
        serial = f"84-11930{n}"
        stock(shop, serial)
        bench(shop, f"TR-{n}", serial, "2025-03-04")
    shop(
        "group", "sample", "G1", "--from", "2025-01-01", "--to", "2025-06-30", "--on", "2025-06-30"
    )
    result = shop("group", "show", "G1")
    assert "2025-06-30" in result.output
    assert "passed" in result.output


def test_the_due_list(shop: Invoke) -> None:
    stock(shop, "84-119302", "2015-01-01")
    stock(shop, "84-119303", "2024-01-01")
    result = shop("due", "list", "--on", "2025-01-01")
    assert "84-119302" in result.output
    assert "84-119303" not in result.output
    assert "overdue" in result.output


def test_the_due_list_by_group(shop: Invoke) -> None:
    stock(shop, "84-119302", "2015-01-01")
    assert "84-119302" in shop("due", "list", "--on", "2025-01-01", "--group", "g1").output
    assert "84-119302" not in shop("due", "list", "--on", "2025-01-01", "--group", "G9").output


def test_the_grace_period_can_be_set(shop: Invoke) -> None:
    stock(shop, "84-119302", "2015-01-01")
    bench(shop, "TR-1", "84-119302", "2021-01-01")
    assert "due" in shop("due", "list", "--on", "2025-02-01").output
    assert shop("due", "list", "--on", "2025-02-01", "--overdue").output.count("84-") == 0
    assert (
        "84-119302" in shop("due", "list", "--on", "2025-02-01", "--grace", "0", "--overdue").output
    )


def test_due_counts(shop: Invoke) -> None:
    stock(shop, "84-119302", "2015-01-01")
    result = shop("due", "counts", "--on", "2025-01-01")
    assert "overdue" in result.output
    assert "ungrouped" in result.output


def test_deleting_a_group(shop: Invoke) -> None:
    result = shop("group", "delete", "G1", "--yes")
    assert "G1 deleted with 0 decisions" in result.output
    assert "G1" not in shop("group", "list").output


def test_deleting_a_group_takes_its_decisions(shop: Invoke) -> None:
    for n in range(5):
        serial = f"84-11930{n}"
        stock(shop, serial)
        bench(shop, f"TR-{n}", serial, "2025-03-04")
    shop(
        "group", "sample", "G1", "--from", "2025-01-01", "--to", "2025-06-30", "--on", "2025-06-30"
    )
    result = shop("group", "delete", "G1", "--yes")
    assert "1 decisions" in result.output


def test_deleting_without_confirming(shop: Invoke) -> None:
    result = shop("group", "delete", "G1", expect=1)
    assert "G1" in shop("group", "list").output
    assert result.exit_code == 1


def test_deleting_a_group_nobody_has(shop: Invoke) -> None:
    result = shop("group", "delete", "G9", "--yes", expect=2)
    assert "no sampling group" in result.output


def test_a_deleted_group_leaves_a_line_in_the_log(shop: Invoke) -> None:
    shop("group", "delete", "G1", "--yes")
    assert "deleted" in shop("book", "history").output


def test_a_group_can_be_given_its_own_grace_period(shop: Invoke) -> None:
    shop("group", "add", "G2", "commercial", "--grace", "14")
    assert "14 days" in shop("group", "show", "G2").output
    assert "the programme's" in shop("group", "show", "G1").output


def test_showing_a_group_names_both_plans(shop: Invoke) -> None:
    for n in range(3):
        stock(shop, f"84-11930{n}")
    result = shop("group", "show", "G1")
    assert "sample needed" in result.output
    assert "attributes plan" in result.output
    assert "accept on 0" in result.output


def test_the_attributes_plan_follows_the_population(shop: Invoke) -> None:
    small = shop("group", "show", "G1").output
    assert "lot 0" in small
    for n in range(9):
        stock(shop, f"84-11930{n}")
    bigger = shop("group", "show", "G1").output
    assert "lot 9" in bigger
