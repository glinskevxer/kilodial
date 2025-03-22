from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest
from click.testing import CliRunner, Result

from kilodial.cli.main import cli

Invoke = Callable[..., Result]


@pytest.fixture
def book(tmp_path: Path) -> Path:
    return tmp_path / "shop.sqlite3"


@pytest.fixture
def invoke(book: Path) -> Invoke:
    runner = CliRunner()

    def call(*args: str, expect: int = 0) -> Result:
        result = runner.invoke(cli, ["--book", str(book), *args])
        if result.exit_code != expect:
            raise AssertionError(
                f"kilodial {' '.join(args)} exited {result.exit_code}, "
                f"expected {expect}\n{result.output}\n{result.exception}"
            )
        return result

    return call


@pytest.fixture
def started(invoke: Invoke) -> Invoke:
    invoke("init")
    return invoke
