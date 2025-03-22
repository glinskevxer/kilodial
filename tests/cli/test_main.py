from __future__ import annotations

from pathlib import Path

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
