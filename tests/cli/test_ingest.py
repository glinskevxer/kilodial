from __future__ import annotations

from pathlib import Path

import pytest

from tests.cli.conftest import Invoke

HEADER = "reference,meter,bench,kind,tested,technician,fl,ll,pf,creep,note\n"
ROW = "TR-1,84-119302,B2,as found,2025-03-04,R Ellis,100.12,99.60,,,\n"
BAD = "TR-2,84-000000,B2,as found,2025-03-04,R Ellis,100.12,99.60,,,\n"


@pytest.fixture
def wired(started: Invoke) -> Invoke:
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
    started("meter", "receive", "84-119302", "--type", "Halvern/R4S", "--acquired", "2015-01-01")
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
        "2015-01-01",
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
    started(
        "point",
        "add",
        "SP-1042",
        "--account",
        "44-9021",
        "--address",
        "18 Fenwick Row",
        "--service",
        "1P3W",
        "--volts",
        "240",
        "--rate",
        "R1",
        "--energised",
        "2011-06-14",
    )
    return started


def write(tmp_path: Path, name: str, text: str) -> str:
    path = tmp_path / name
    path.write_text(text)
    return str(path)


def test_importing_runs(wired: Invoke, tmp_path: Path) -> None:
    path = write(tmp_path, "bench.csv", HEADER + ROW)
    result = wired("import", "runs", path)
    assert "1 rows taken, 0 left" in result.output
    assert "TR-1" in wired("run", "list").output


def test_a_partial_import_exits_non_zero(wired: Invoke, tmp_path: Path) -> None:
    path = write(tmp_path, "bench.csv", HEADER + ROW + BAD)
    result = wired("import", "runs", path, expect=1)
    assert "1 rows taken, 1 left" in result.output
    assert "no meter on the book" in result.output
    assert "TR-1" in wired("run", "list").output


def test_a_dry_run_writes_nothing(wired: Invoke, tmp_path: Path) -> None:
    path = write(tmp_path, "bench.csv", HEADER + ROW)
    result = wired("import", "runs", path, "--dry-run")
    assert "nothing written" in result.output
    assert "TR-1" not in wired("run", "list").output


def test_a_dry_run_reports_what_would_fail(wired: Invoke, tmp_path: Path) -> None:
    path = write(tmp_path, "bench.csv", HEADER + ROW + BAD)
    result = wired("import", "runs", path, "--dry-run", expect=1)
    assert "no meter on the book" in result.output


def test_a_file_missing_a_column(wired: Invoke, tmp_path: Path) -> None:
    path = write(tmp_path, "bench.csv", "reference,meter\nTR-1,84-119302\n")
    result = wired("import", "runs", path, expect=2)
    assert "the file is missing" in result.output


def test_a_file_that_is_not_there(wired: Invoke, tmp_path: Path) -> None:
    result = wired("import", "runs", str(tmp_path / "nowhere.csv"), expect=2)
    assert "does not exist" in result.output


def test_importing_bills(wired: Invoke, tmp_path: Path) -> None:
    path = write(
        tmp_path,
        "bills.csv",
        "point,from,to,amount,kwh\nSP-1042,2025-01-01,2025-01-31,104.22,912.4\n",
    )
    result = wired("import", "bills", path)
    assert "1 rows taken" in result.output
    assert "$104.22" in wired("bill", "list", "SP-1042").output


def test_a_bill_row_for_a_point_nobody_has(wired: Invoke, tmp_path: Path) -> None:
    path = write(
        tmp_path,
        "bills.csv",
        "point,from,to,amount\nSP-9999,2025-01-01,2025-01-31,104.22\n",
    )
    result = wired("import", "bills", path, expect=1)
    assert "not on the book" in result.output


def test_the_columns_command(wired: Invoke) -> None:
    result = wired("import", "columns")
    assert "reference, meter, bench" in result.output
    assert "point, from, to, amount" in result.output
    assert "creep" in result.output
