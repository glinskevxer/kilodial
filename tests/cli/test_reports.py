from __future__ import annotations

import json
from pathlib import Path

import pytest

from kilodial.store.shop import open_shop
from kilodial.tools.smoke import stand_up
from tests.cli.conftest import Invoke


@pytest.fixture
def stocked(invoke: Invoke, book: Path) -> Invoke:
    invoke("init")
    with open_shop(book) as shop:
        stand_up(shop)
    return invoke


def test_the_shop_report_as_text(stocked: Invoke) -> None:
    result = stocked("report", "shop", "--on", "2025-06-30")
    assert "Meter shop report as at 2025-06-30" in result.output
    assert "Fleet" in result.output
    assert "Periodic programme" in result.output


def test_the_shop_report_as_json(stocked: Invoke) -> None:
    payload = json.loads(stocked("report", "shop", "--on", "2025-06-30", "--format", "json").output)
    assert payload["title"].startswith("Meter shop report")
    assert payload["sections"][0]["title"] == "Overview"


def test_the_shop_report_as_csv(stocked: Invoke) -> None:
    result = stocked("report", "shop", "--on", "2025-06-30", "--format", "csv")
    assert result.output.startswith("state,meters")


def test_a_format_nobody_writes(stocked: Invoke) -> None:
    result = stocked("report", "shop", "--on", "2025-06-30", "--format", "pdf", expect=2)
    assert "not one of" in result.output


def test_writing_a_report_to_a_file(stocked: Invoke, tmp_path: Path) -> None:
    out = tmp_path / "deep" / "shop.txt"
    result = stocked("report", "shop", "--on", "2025-06-30", "--out", str(out))
    assert out.exists()
    assert "Meter shop report" in out.read_text()
    assert "wrote" in result.output


def test_the_commission_report(stocked: Invoke) -> None:
    result = stocked("report", "commission", "--from", "2025-01-01", "--to", "2025-12-31")
    assert "Commission meter test report" in result.output
    assert "Groups" in result.output
    assert "Customer requested tests" in result.output


def test_the_commission_report_as_csv(stocked: Invoke) -> None:
    result = stocked(
        "report",
        "commission",
        "--from",
        "2025-01-01",
        "--to",
        "2025-12-31",
        "--format",
        "csv",
    )
    assert result.output.startswith("group,name,in service")


def test_the_register(stocked: Invoke) -> None:
    result = stocked("report", "register", "--on", "2025-07-15")
    assert "Adjustment register as at 2025-07-15" in result.output
    assert "Passed over" in result.output
    assert "Tariff" in result.output


def test_the_register_prices_a_fast_meter(stocked: Invoke) -> None:
    stocked(
        "run",
        "record",
        "TR-1",
        "--meter",
        "84-119302",
        "--bench",
        "B2",
        "--on",
        "2025-06-30",
        "--by",
        "R Ellis",
        "--fl",
        "103.20",
        "--ll",
        "102.40",
    )
    result = stocked("report", "register", "--on", "2025-07-15")
    assert "refund" in result.output
    assert "$600.00" in result.output


def test_a_report_on_a_book_that_is_not_there(invoke: Invoke) -> None:
    result = invoke("report", "shop", "--on", "2025-06-30", expect=2)
    assert "run 'kilodial init' first" in result.output


def test_the_formats_command(stocked: Invoke) -> None:
    result = stocked("report", "formats")
    assert "text" in result.output
    assert "csv" in result.output


def test_the_certificate_report(stocked: Invoke) -> None:
    result = stocked("report", "certificates", "--on", "2025-06-30")
    assert "Certification report as at 2025-06-30" in result.output
    assert "standard" in result.output
    assert "Transformer policy" in result.output


def test_the_certificate_report_warning_window(stocked: Invoke) -> None:
    narrow = stocked("report", "certificates", "--on", "2034-11-01").output
    wide = stocked("report", "certificates", "--on", "2034-11-01", "--warning", "120").output
    assert narrow.count("due") <= wide.count("due")


def test_the_certificate_report_as_csv(stocked: Invoke) -> None:
    result = stocked("report", "certificates", "--on", "2025-06-30", "--format", "csv")
    assert result.output.startswith("kind,reference,detail")


def test_the_fault_report(stocked: Invoke) -> None:
    result = stocked("report", "faults", "--from", "2025-01-01", "--to", "2025-12-31")
    assert "Fault report" in result.output
    assert "By family" in result.output


def test_the_fault_report_as_csv(stocked: Invoke) -> None:
    result = stocked(
        "report",
        "faults",
        "--from",
        "2025-01-01",
        "--to",
        "2025-12-31",
        "--format",
        "csv",
    )
    assert result.output.startswith("type,meters,repairs")


def test_the_bench_report(stocked: Invoke) -> None:
    result = stocked("report", "bench", "--from", "2025-01-01", "--to", "2025-12-31")
    assert "Bench report" in result.output
    assert "By run kind" in result.output


def test_the_report_list(stocked: Invoke) -> None:
    result = stocked("report", "list")
    assert "commission" in result.output
    assert "answers" in result.output
    assert "take --from and --to" in result.output
