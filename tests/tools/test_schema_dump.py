from __future__ import annotations

from pathlib import Path

import pytest

from kilodial.tools import schema_dump as gate


def test_the_dump_on_disk_matches_the_migrations() -> None:
    assert gate.differences() == []


def test_the_check_passes(capsys: pytest.CaptureFixture[str]) -> None:
    assert gate.main(["--check"]) == 0
    assert "matches the migrations" in capsys.readouterr().out


def test_the_built_schema_names_every_table() -> None:
    text = gate.build()
    for table in ("device_type", "meter", "bench_run", "billed_month", "complaint_request"):
        assert f"CREATE TABLE {table}" in text
    assert "Do not edit by hand" in text


def test_tables_come_before_indexes() -> None:
    text = gate.build()
    assert text.index("CREATE TABLE") < text.index("CREATE INDEX")


def test_writing_and_reading_back(tmp_path: Path) -> None:
    path = tmp_path / "deep" / "schema.sql"
    gate.write(path)
    assert path.exists()
    assert gate.differences(path) == []


def test_a_missing_dump_is_a_difference(tmp_path: Path) -> None:
    problems = gate.differences(tmp_path / "nowhere.sql")
    assert "there is no schema dump" in problems[0]


def test_a_stale_dump_is_caught(tmp_path: Path) -> None:
    path = tmp_path / "schema.sql"
    gate.write(path)
    path.write_text(path.read_text().replace("device_type", "device_types", 1))
    problems = gate.differences(path)
    assert any("should be" in p for p in problems)


def test_the_check_fails_on_a_stale_dump(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "schema.sql"
    path.write_text("nothing like it\n")
    assert gate.main(["--check", "--path", str(path)]) == 1
    assert "bring it up to date" in capsys.readouterr().out


def test_writing_from_the_command_line(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = tmp_path / "schema.sql"
    assert gate.main(["--path", str(path)]) == 0
    assert "wrote" in capsys.readouterr().out
    assert path.exists()
