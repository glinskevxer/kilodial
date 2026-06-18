"""Drive every command's help and every group's listing, once each.

A hundred and sixteen commands is more than anybody checks by hand, and the
failure this catches is a cheap one that looks expensive: a decorator that
refers to a parameter the function does not take, an option whose type cannot be
constructed, a group that was never wired into the tree. All of those raise the
first time click builds the command, which is when somebody asks for its help,
and every other test in this suite gets there by calling the command instead.

So this asks for the help of every command in the tree and asserts it renders.
It is a shallow test on purpose: depth belongs in the tests that drive the
commands, and this is the one that says the surface exists.
"""

from __future__ import annotations

import click
import pytest
from click.testing import CliRunner

from kilodial.cli.main import cli
from kilodial.tools.build_docs import walk

PATHS = [path for path, _ in walk(cli, [])]
GROUPS = sorted({path[0] for path in PATHS if len(path) > 1})


def run(*args: str) -> str:
    result = CliRunner().invoke(cli, list(args))
    assert result.exit_code == 0, f"{' '.join(args)} exited {result.exit_code}"
    return result.output


@pytest.mark.parametrize("path", PATHS, ids=[" ".join(p) for p in PATHS])
def test_every_command_renders_its_help(path: list[str]) -> None:
    output = run(*path, "--help")
    assert "Usage:" in output
    assert path[-1] in output


@pytest.mark.parametrize("group", GROUPS)
def test_every_group_lists_its_commands(group: str) -> None:
    output = run(group, "--help")
    tree = cli.commands[group]
    assert isinstance(tree, click.Group)
    for name in tree.commands:
        assert name in output


def test_the_root_lists_every_group() -> None:
    output = run("--help")
    for group in GROUPS:
        assert group in output


def test_the_tree_is_as_wide_as_it_looks() -> None:
    assert len(PATHS) > 100
    assert len(GROUPS) > 15
    assert len(set(PATHS[0])) > 0


def test_every_command_is_reachable_from_the_root() -> None:
    for path in PATHS:
        node: click.Command = cli
        for part in path:
            assert isinstance(node, click.Group)
            assert part in node.commands
            node = node.commands[part]
        assert not isinstance(node, click.Group)


def test_the_short_help_flag_works_too() -> None:
    assert "Usage:" in run("-h")
    assert "Usage:" in run("run", "-h")


@pytest.mark.parametrize("path", PATHS, ids=[" ".join(p) for p in PATHS])
def test_every_command_names_its_required_options_in_the_help(path: list[str]) -> None:
    output = run(*path, "--help")
    node: click.Command = cli
    for part in path:
        assert isinstance(node, click.Group)
        node = node.commands[part]
    for param in node.params:
        if isinstance(param, click.Option) and param.required:
            assert param.opts[0] in output


def test_no_two_commands_share_a_path() -> None:
    joined = [" ".join(path) for path in PATHS]
    assert len(set(joined)) == len(joined)


def test_the_version_flag_answers_off_the_root() -> None:
    output = run("--version")
    assert "kilodial" in output
