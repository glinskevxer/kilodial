"""Check a coverage report against a total floor and a per file floor.

A single total is easy to satisfy and easy to hide behind. A package can sit at
ninety five percent overall with one module at forty, and that module is always
the interesting one, because a module nobody tested is usually a module nobody
was sure about.

So there are two floors. The total says the suite is broadly doing its job, and
the per file floor says no single module has been left out of it. The per file
floor is deliberately lower than the total: a small module with one defensive
branch should not fail a build over a line that cannot be reached honestly.

Files can be excused by name, and the excuse list is printed on every run
whether it fired or not, because a silent exemption grows.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

from kilodial.tools import FAILED, OK

DEFAULT_REPORT = Path("coverage.json")
DEFAULT_FLOOR = 90.0
DEFAULT_FILE_FLOOR = 70.0

# Modules that are allowed to sit under the per file floor, with the reason.
EXCUSED: dict[str, str] = {
    "src/kilodial/cli/main.py": "the console script entry point is exercised by CI, not by pytest",
}


@dataclass(frozen=True)
class FileCoverage:
    """One file's line coverage as the report gives it."""

    path: str
    percent: float
    missing: int

    def __str__(self) -> str:
        return f"{self.path} {self.percent:.1f}% ({self.missing} lines uncovered)"


@dataclass(frozen=True)
class Report:
    """A parsed coverage report."""

    total: float
    files: tuple[FileCoverage, ...]

    def under(self, floor: float) -> list[FileCoverage]:
        """Files below a floor that are not excused, worst first."""
        found = [f for f in self.files if f.percent < floor and f.path not in EXCUSED]
        return sorted(found, key=lambda f: f.percent)

    def worst(self, count: int = 5) -> list[FileCoverage]:
        """The least covered files, for the run's own output."""
        return sorted(self.files, key=lambda f: f.percent)[:count]


def read(path: Path = DEFAULT_REPORT) -> Report:
    """Parse a coverage json report off disk."""
    if not path.exists():
        raise SystemExit(f"there is no coverage report at {path}")
    data = json.loads(path.read_text())
    files = tuple(
        FileCoverage(
            path=name.replace("\\", "/"),
            percent=float(entry["summary"]["percent_covered"]),
            missing=int(entry["summary"]["missing_lines"]),
        )
        for name, entry in sorted(data.get("files", {}).items())
    )
    return Report(total=float(data["totals"]["percent_covered"]), files=files)


def faults(report: Report, *, floor: float, file_floor: float) -> list[str]:
    """Everything below a floor, total first."""
    found: list[str] = []
    if report.total < floor:
        found.append(f"total coverage is {report.total:.2f}% against a floor of {floor}%")
    for file in report.under(file_floor):
        found.append(f"{file} is under the {file_floor}% per file floor")
    return found


def main(argv: list[str] | None = None) -> int:
    """Read the report, apply both floors, and say so in the exit code."""
    parser = argparse.ArgumentParser(description="check a coverage report")
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--floor", type=float, default=DEFAULT_FLOOR)
    parser.add_argument("--file-floor", type=float, default=DEFAULT_FILE_FLOOR)
    args = parser.parse_args(argv)
    report = read(args.report)
    for path, why in sorted(EXCUSED.items()):
        print(f"excused: {path} ({why})")
    problems = faults(report, floor=args.floor, file_floor=args.file_floor)
    for problem in problems:
        print(problem)
    if problems:
        return FAILED
    print(f"coverage {report.total:.2f}% over {len(report.files)} files")
    for file in report.worst():
        print(f"  lowest: {file}")
    return OK


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())


__all__ = [
    "DEFAULT_FILE_FLOOR",
    "DEFAULT_FLOOR",
    "DEFAULT_REPORT",
    "EXCUSED",
    "FileCoverage",
    "Report",
    "faults",
    "main",
    "read",
]
