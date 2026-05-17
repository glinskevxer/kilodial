from __future__ import annotations

import json
from pathlib import Path

import pytest

from kilodial.tools import coverage_gate as gate


def report_file(tmp_path: Path, total: float, files: dict[str, float]) -> Path:
    path = tmp_path / "coverage.json"
    path.write_text(
        json.dumps(
            {
                "totals": {"percent_covered": total},
                "files": {
                    name: {
                        "summary": {
                            "percent_covered": percent,
                            "missing_lines": 3,
                            "covered_lines": 10,
                        }
                    }
                    for name, percent in files.items()
                },
            }
        )
    )
    return path


def test_reading_a_report(tmp_path: Path) -> None:
    path = report_file(tmp_path, 95.5, {"src/kilodial/a.py": 91.0})
    report = gate.read(path)
    assert report.total == 95.5
    assert report.files[0].path == "src/kilodial/a.py"
    assert report.files[0].missing == 3
    assert str(report.files[0]).startswith("src/kilodial/a.py 91.0%")


def test_a_report_that_is_not_there(tmp_path: Path) -> None:
    with pytest.raises(SystemExit, match="no coverage report"):
        gate.read(tmp_path / "nowhere.json")


def test_a_clean_report_passes(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = report_file(tmp_path, 95.5, {"src/kilodial/a.py": 91.0})
    assert gate.main(["--report", str(path)]) == 0
    printed = capsys.readouterr().out
    assert "coverage 95.50%" in printed
    assert "lowest" in printed


def test_the_total_floor_bites(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = report_file(tmp_path, 80.0, {"src/kilodial/a.py": 91.0})
    assert gate.main(["--report", str(path)]) == 1
    assert "total coverage is 80.00%" in capsys.readouterr().out


def test_the_per_file_floor_bites_on_a_good_total(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = report_file(tmp_path, 95.5, {"src/kilodial/a.py": 40.0})
    assert gate.main(["--report", str(path)]) == 1
    printed = capsys.readouterr().out
    assert "per file floor" in printed
    assert "total coverage" not in printed


def test_the_floors_can_be_moved(tmp_path: Path) -> None:
    path = report_file(tmp_path, 80.0, {"src/kilodial/a.py": 40.0})
    assert gate.main(["--report", str(path), "--floor", "75", "--file-floor", "30"]) == 0


def test_an_excused_file_is_not_a_failure(tmp_path: Path) -> None:
    excused = next(iter(gate.EXCUSED))
    path = report_file(tmp_path, 95.5, {excused: 10.0})
    assert gate.main(["--report", str(path)]) == 0


def test_the_excuse_list_is_always_printed(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = report_file(tmp_path, 95.5, {"src/kilodial/a.py": 91.0})
    gate.main(["--report", str(path)])
    assert "excused:" in capsys.readouterr().out


def test_the_worst_files_come_back_worst_first(tmp_path: Path) -> None:
    path = report_file(tmp_path, 95.5, {"src/a.py": 91.0, "src/b.py": 55.0, "src/c.py": 72.0})
    report = gate.read(path)
    assert [f.path for f in report.worst(2)] == ["src/b.py", "src/c.py"]
    assert [f.path for f in report.under(80.0)] == ["src/b.py", "src/c.py"]


def test_faults_reports_the_total_first(tmp_path: Path) -> None:
    path = report_file(tmp_path, 50.0, {"src/a.py": 10.0})
    problems = gate.faults(gate.read(path), floor=90.0, file_floor=70.0)
    assert "total coverage" in problems[0]
    assert len(problems) == 2


def report_with(tmp_path: Path, files: dict[str, tuple[float, int, int]]) -> Path:
    path = tmp_path / "coverage.json"
    path.write_text(
        json.dumps(
            {
                "totals": {"percent_covered": 99.0},
                "files": {
                    name: {
                        "summary": {
                            "percent_covered": percent,
                            "missing_lines": missing,
                            "covered_lines": covered,
                        }
                    }
                    for name, (percent, missing, covered) in files.items()
                },
            }
        )
    )
    return path


def test_a_package_is_weighted_by_lines(tmp_path: Path) -> None:
    path = report_with(
        tmp_path,
        {
            "src/kilodial/units/a.py": (100.0, 0, 2),
            "src/kilodial/units/b.py": (60.0, 120, 180),
        },
    )
    report = gate.read(path)
    assert report.package("src/kilodial/units") < 62.0


def test_a_package_with_no_files_is_whole(tmp_path: Path) -> None:
    path = report_with(tmp_path, {"src/kilodial/store/a.py": (100.0, 0, 10)})
    assert gate.read(path).package("src/kilodial/units") == 100.0


def test_a_package_with_no_lines_is_whole(tmp_path: Path) -> None:
    path = report_with(tmp_path, {"src/kilodial/units/a.py": (100.0, 0, 0)})
    assert gate.read(path).package("src/kilodial/units") == 100.0


def test_a_package_below_its_own_floor_is_caught(tmp_path: Path) -> None:
    path = report_with(
        tmp_path,
        {"src/kilodial/units/a.py": (80.0, 20, 80), "src/kilodial/store/b.py": (99.0, 1, 99)},
    )
    problems = gate.faults(gate.read(path), floor=90.0, file_floor=70.0)
    assert any("src/kilodial/units is at 80.00%" in p for p in problems)


def test_the_package_floors_cover_the_domain() -> None:
    assert "src/kilodial/units" in gate.PACKAGE_FLOORS
    assert "src/kilodial/model" in gate.PACKAGE_FLOORS
    assert all(floor >= 95.0 for floor in gate.PACKAGE_FLOORS.values())


def test_the_run_prints_each_package(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = report_with(tmp_path, {"src/kilodial/units/a.py": (100.0, 0, 10)})
    assert gate.main(["--report", str(path)]) == 0
    printed = capsys.readouterr().out
    assert "src/kilodial/units 100.00%" in printed
