"""Run the command lines out of the CI workflow, here, against a temp book.

CI has a job that stands a shop up through the installed console script. It is
the only thing that proves the wheel works, and it is also the only thing in the
repository that nobody runs before pushing, so it breaks on the branch and gets
noticed on the pull request.

This reads the same lines out of the workflow file and runs them through click's
test runner. It does not prove the wheel works, which is still CI's job, but it
does prove the twenty odd command lines in there are still command lines this
package accepts, which is what actually breaks.

Reading them out of the workflow rather than copying them is the point. A copy
would drift, and a drifted copy of a test is worse than no copy at all.
"""

from __future__ import annotations

import re
import shlex
from pathlib import Path

import click
import pytest
from click.testing import CliRunner

from kilodial.cli.main import cli

WORKFLOW = Path(".github/workflows/ci.yml")
LINE = re.compile(r'kilodial --book "\$book" (.*)')


def walk_lines() -> list[str]:
    """The command lines the workflow's walk job runs, joined across backslashes."""
    text = WORKFLOW.read_text().replace("\\\n", " ")
    return [" ".join(m.group(1).split()) for m in LINE.finditer(text)]


LINES = walk_lines()


def test_the_workflow_still_has_a_walk() -> None:
    assert len(LINES) > 15
    assert any(line.startswith("init") for line in LINES)
    assert any(line.startswith("book audit") for line in LINES)


@pytest.mark.parametrize("line", LINES, ids=[line.split()[0] for line in LINES])
def test_every_line_is_a_command_this_package_knows(line: str) -> None:
    parts = shlex.split(line)
    node: click.Command = cli
    for part in parts:
        if part.startswith("-"):
            break
        if not isinstance(node, click.Group) or part not in node.commands:
            break
        node = node.commands[part]
    assert node is not cli, f"{line} names no command"


def test_the_whole_walk_runs(tmp_path: Path) -> None:
    book = tmp_path / "walk.sqlite3"
    runner = CliRunner()
    for line in LINES:
        args = ["--book", str(book), *shlex.split(line)]
        result = runner.invoke(cli, args)
        assert result.exit_code == 0, (
            f"kilodial {line} exited {result.exit_code}\n{result.output}\n{result.exception}"
        )


def test_the_walk_leaves_a_book_that_audits_clean(tmp_path: Path) -> None:
    from kilodial.store.shop import open_shop

    book = tmp_path / "walk.sqlite3"
    runner = CliRunner()
    for line in LINES:
        runner.invoke(cli, ["--book", str(book), *shlex.split(line)])
    with open_shop(book) as shop:
        assert shop.audit() == []
        assert shop.book.check() == []
        assert shop.summary()["meters"] == 1
        assert shop.summary()["runs"] == 1


def test_the_walk_covers_the_shape_of_the_package(tmp_path: Path) -> None:
    groups = {line.split()[0] for line in LINES}
    for wanted in ("device", "meter", "standard", "bench", "point", "run", "report"):
        assert wanted in groups
