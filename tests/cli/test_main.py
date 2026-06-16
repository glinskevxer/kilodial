from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner

from kilodial import __version__
from kilodial.cli.main import cli
from tests.cli.conftest import Invoke


def test_version() -> None:
    result = CliRunner().invoke(cli, ["--version"])
    assert result.exit_code == 0
    assert __version__ in result.output


def test_help_lists_the_groups() -> None:
    result = CliRunner().invoke(cli, ["--help"])
    assert "book" in result.output
    assert "init" in result.output


def test_init_creates_the_book(invoke: Invoke, book: Path) -> None:
    result = invoke("init")
    assert book.exists()
    assert "ran migration 1 through" in result.output


def test_init_twice_says_so(invoke: Invoke) -> None:
    invoke("init")
    result = invoke("init")
    assert "already at migration" in result.output


def test_init_can_be_forced(invoke: Invoke) -> None:
    invoke("init")
    result = invoke("init", "--force")
    assert "already up to date" in result.output


def test_working_on_a_book_that_is_not_there(invoke: Invoke) -> None:
    result = invoke("book", "check", expect=2)
    assert "run 'kilodial init' first" in result.output


def test_book_check_on_a_fresh_book(started: Invoke) -> None:
    result = started("book", "check")
    assert "checks out" in result.output


def test_book_summary(started: Invoke) -> None:
    result = started("book", "summary")
    assert "meters" in result.output
    assert "0" in result.output


def test_book_audit_on_a_fresh_book(started: Invoke) -> None:
    result = started("book", "audit")
    assert "points at anything missing" in result.output


def test_quiet_says_nothing(invoke: Invoke) -> None:
    result = invoke("--quiet", "init")
    assert result.output == ""


def test_the_book_can_come_from_the_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    book = tmp_path / "fromenv.sqlite3"
    monkeypatch.setenv("KILODIAL_BOOK", str(book))
    result = CliRunner().invoke(cli, ["init"])
    assert result.exit_code == 0
    assert book.exists()


def test_the_flag_beats_the_environment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KILODIAL_BOOK", str(tmp_path / "env.sqlite3"))
    named = tmp_path / "named.sqlite3"
    result = CliRunner().invoke(cli, ["--book", str(named), "init"])
    assert result.exit_code == 0
    assert named.exists()
    assert not (tmp_path / "env.sqlite3").exists()


def test_the_size_command(started: Invoke) -> None:
    result = started("book", "size")
    assert "pages" in result.output
    assert "page size" in result.output


def test_the_compact_command(started: Invoke) -> None:
    result = started("book", "compact", "--yes")
    assert "bytes to" in result.output


def test_compacting_without_confirming(started: Invoke) -> None:
    started("book", "compact", expect=1)


def test_the_about_command(started: Invoke) -> None:
    result = started("about")
    assert __version__ in result.output
    assert "docs/commands.md" in result.output
    assert "book exists" in result.output
    assert "yes" in result.output


def test_about_on_a_book_that_is_not_there(invoke: Invoke) -> None:
    result = invoke("about")
    assert "book exists" in result.output
    assert "no" in result.output


def test_about_names_the_actor(started: Invoke) -> None:
    assert "shop" in started("about").output


def test_about_counts_what_there_is(started: Invoke) -> None:
    from kilodial.report.catalogue import CATALOGUE
    from kilodial.store.schema import latest_number

    result = started("about").output
    assert f"reports            {len(CATALOGUE)}" in result
    assert f"migrations         {latest_number()}" in result


def test_an_error_prints_one_line_by_default(invoke: Invoke) -> None:
    result = invoke("book", "check", expect=2)
    assert "run 'kilodial init' first" in result.output
    assert "Traceback" not in result.output


def test_the_traceback_escape_lets_it_through(
    invoke: Invoke, monkeypatch: pytest.MonkeyPatch
) -> None:
    from kilodial.cli.main import TRACEBACK
    from kilodial.errors import ConfigError

    monkeypatch.setenv(TRACEBACK, "1")
    runner = CliRunner()
    result = runner.invoke(cli, ["--book", "nowhere.sqlite3", "book", "check"])
    assert isinstance(result.exception, ConfigError)
