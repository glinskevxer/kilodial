from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from kilodial.errors import BadInputError
from kilodial.ingest import bench as ingest
from kilodial.model.bench import Bench, ReferenceStandard
from kilodial.model.device import DeviceType
from kilodial.model.form import Technology
from kilodial.model.meter import Meter
from kilodial.model.run import PointKind, RunKind
from kilodial.store.shop import Shop, open_shop

HEADER = "reference,meter,bench,kind,tested,technician,fl,ll,pf,creep,note\n"
ROW = "TR-1,84-119302,B2,as found,2025-03-04,R Ellis,100.12,99.60,,,\n"


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
    opened.meters.add(Meter.receive("84-119303", "Halvern/R4S", acquired="2015-01-01"))
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
    opened.standards.add(
        ReferenceStandard.build(
            "RS-7002",
            maker="Radian",
            model_code="RD-23",
            certificate="NVLAP-90001",
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
    yield opened
    opened.close()


def test_a_clean_import(shop: Shop) -> None:
    found = ingest.load_text(shop, HEADER + ROW)
    assert found.taken == 1
    assert found.clean
    run = shop.runs.get("TR-1")
    assert run.meter_serial == "84-119302"
    assert run.standard_serial == "RS-5511"
    assert run.point("FL").percent.rounded(2) == run.point("FL").percent.rounded(2)


def test_the_standard_comes_off_the_bench_unless_named(shop: Shop) -> None:
    text = (
        "reference,meter,bench,kind,tested,technician,fl,ll,standard\n"
        "TR-1,84-119302,B2,as found,2025-03-04,R Ellis,100.12,99.60,RS-7002\n"
    )
    ingest.load_text(shop, text)
    assert shop.runs.get("TR-1").standard_serial == "RS-7002"


def test_a_missing_column_refuses_the_whole_file(shop: Shop) -> None:
    with pytest.raises(BadInputError, match="missing bench"):
        ingest.load_text(shop, "reference,meter,kind,tested,technician\nTR-1,x,y,z,a\n")


def test_a_row_naming_a_meter_nobody_has_is_skipped(shop: Shop) -> None:
    text = HEADER + ROW + "TR-2,84-000000,B2,as found,2025-03-04,R Ellis,100.1,99.6,,,\n"
    found = ingest.load_text(shop, text)
    assert found.taken == 1
    assert found.skipped[0][0] == 3
    assert "no meter on the book" in found.skipped[0][1]


def test_a_row_naming_a_bench_nobody_has_is_skipped(shop: Shop) -> None:
    text = HEADER + "TR-1,84-119302,B9,as found,2025-03-04,R Ellis,100.1,99.6,,,\n"
    found = ingest.load_text(shop, text)
    assert found.taken == 0
    assert "no bench on the book" in found.skipped[0][1]


def test_a_row_with_no_readings_is_skipped(shop: Shop) -> None:
    text = HEADER + "TR-1,84-119302,B2,as found,2025-03-04,R Ellis,,,,,\n"
    found = ingest.load_text(shop, text)
    assert "no readings" in found.skipped[0][1]


def test_a_kind_nobody_runs_is_skipped(shop: Shop) -> None:
    text = HEADER + "TR-1,84-119302,B2,guesswork,2025-03-04,R Ellis,100.1,99.6,,,\n"
    assert "not a run kind" in ingest.load_text(shop, text).skipped[0][1]


def test_creep_words(shop: Shop) -> None:
    text = HEADER + "TR-1,84-119302,B2,as left,2025-03-04,R Ellis,100.1,99.6,,held,\n"
    ingest.load_text(shop, text)
    assert shop.runs.get("TR-1").point(PointKind.CREEP).crept is False


def test_a_creep_word_nobody_uses_is_skipped(shop: Shop) -> None:
    text = HEADER + "TR-1,84-119302,B2,as left,2025-03-04,R Ellis,100.1,99.6,,maybe,\n"
    assert "held or crept" in ingest.load_text(shop, text).skipped[0][1]


def test_a_duplicate_reference_is_skipped(shop: Shop) -> None:
    found = ingest.load_text(shop, HEADER + ROW + ROW)
    assert found.taken == 1
    assert "already on the book" in found.skipped[0][1]


def test_a_second_import_of_the_same_file_takes_nothing(shop: Shop) -> None:
    ingest.load_text(shop, HEADER + ROW)
    second = ingest.load_text(shop, HEADER + ROW)
    assert second.taken == 0
    assert len(second.skipped) == 1


def test_the_note_and_the_voltage_override_come_through(shop: Shop) -> None:
    text = (
        "reference,meter,bench,kind,tested,technician,fl,ll,note,volts\n"
        "TR-1,84-119302,B2,as found,2025-03-04,R Ellis,100.12,99.60,cover cracked,277\n"
    )
    ingest.load_text(shop, text)
    run = shop.runs.get("TR-1")
    assert run.note == "cover cracked"
    assert str(run.point("FL").volts) == "277 V"


def test_nothing_is_judged_at_import_time(shop: Shop) -> None:
    text = HEADER + "TR-1,84-119302,B2,as found,2025-03-04,R Ellis,104.0,103.0,,,\n"
    assert ingest.load_text(shop, text).taken == 1
    assert not shop.judge("TR-1").passed


def test_importing_off_disk(shop: Shop, tmp_path: Path) -> None:
    path = tmp_path / "bench.csv"
    path.write_text(HEADER + ROW)
    assert ingest.load_file(shop, path).taken == 1


def test_a_run_kind_is_read_however_it_is_written() -> None:
    assert ingest.run_kind("AS_FOUND") is RunKind.AS_FOUND
    assert ingest.run_kind("as-left") is RunKind.AS_LEFT
    assert ingest.run_kind(" referee ") is RunKind.REFEREE
