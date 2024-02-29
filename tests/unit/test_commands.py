# Copyright 2023 Canonical Limited
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from argparse import ArgumentParser
from unittest.mock import patch

import pytest

from cou import commands
from cou.commands import CONTROL_PLANE, DATA_PLANE, HYPERVISORS, CLIargs


@pytest.mark.parametrize("auto_approve, expected_result", [(True, False), (False, True)])
def test_CLIargs_prompt(auto_approve, expected_result):
    args = CLIargs(command="foo", auto_approve=auto_approve)
    assert args.prompt is expected_result


@pytest.mark.parametrize(
    "upgrade_group, expected_result",
    [(CONTROL_PLANE, True), (DATA_PLANE, False), (None, False), (HYPERVISORS, False)],
)
def test_CLIargs_is_control_plane_command(upgrade_group, expected_result):
    args = CLIargs(command="foo", upgrade_group=upgrade_group)
    assert args.is_control_plane_command is expected_result


@pytest.mark.parametrize(
    "upgrade_group, expected_result",
    [(CONTROL_PLANE, False), (DATA_PLANE, False), (HYPERVISORS, True), ("foo", False)],
)
def test_CLIargs_is_hypervisors_command(upgrade_group, expected_result):
    args = CLIargs(command="foo", upgrade_group=upgrade_group)
    assert args.is_hypervisors_command is expected_result


@pytest.mark.parametrize(
    "upgrade_group, expected_result",
    [(CONTROL_PLANE, False), (DATA_PLANE, False), (HYPERVISORS, False), (None, True)],
)
def test_CLIargs_is_generic_command(upgrade_group, expected_result):
    args = CLIargs(command="foo", upgrade_group=upgrade_group)
    assert args.is_generic_command is expected_result


@pytest.mark.parametrize(
    "upgrade_group, expected_result",
    [(CONTROL_PLANE, False), (DATA_PLANE, True), (HYPERVISORS, True), ("foo", False)],
)
def test_CLIargs_is_data_plane_command(upgrade_group, expected_result):
    args = CLIargs(command="foo", upgrade_group=upgrade_group)
    assert args.is_data_plane_command is expected_result


@pytest.mark.parametrize(
    "args",
    [
        [],
        ["-h"],
        ["--help"],
        ["help"],
        ["help", "plan"],
        ["help", "upgrade"],
        ["plan", "-h"],
        ["upgrade", "-h"],
        ["plan", "control-plane", "-h"],
        ["plan", "data-plane", "-h"],
        ["plan", "hypervisors", "-h"],
        ["upgrade", "control-plane", "-h"],
        ["upgrade", "data-plane", "-h"],
        ["upgrade", "hypervisors", "-h"],
    ],
)
def test_parse_args_help(args):
    """Test printing help messages."""
    with patch(
        "cou.commands.argparse.ArgumentParser.print_help"
    ) as mock_print_help, pytest.raises(SystemExit, match="0"):
        commands.parse_args(args)
        mock_print_help.assert_called_once()


@pytest.mark.parametrize(
    "args",
    [
        ["--quiet", "--verbose"],
        ["--quiet", "-v"],
        ["--quiet", "-vvv"],
    ],
)
def test_parse_args_quiet_verbose_exclusive(args):
    """Test that quiet and verbose options are mutually exclusive."""
    with pytest.raises(SystemExit, match="2"):
        commands.parse_args(args)


@pytest.mark.parametrize(
    "args, expected_CLIargs",
    [
        (
            ["plan"],
            CLIargs(
                command="plan",
                model_name=None,
                verbosity=0,
                quiet=False,
                backup=True,
                force=False,
                **{"upgrade_group": None}
            ),
        ),
        (
            ["plan", "--no-backup"],
            CLIargs(
                command="plan",
                model_name=None,
                verbosity=0,
                quiet=False,
                backup=False,
                force=False,
                **{"upgrade_group": None}
            ),
        ),
        (
            ["plan", "--no-backup", "--quiet"],
            CLIargs(
                command="plan",
                model_name=None,
                verbosity=0,
                quiet=True,
                backup=False,
                force=False,
                **{"upgrade_group": None}
            ),
        ),
        (
            ["plan", "--no-backup", "--quiet", "--force"],
            CLIargs(
                command="plan",
                model_name=None,
                verbosity=0,
                quiet=True,
                backup=False,
                force=True,
                **{"upgrade_group": None}
            ),
        ),
        (
            ["plan", "--model=model_name"],
            CLIargs(
                command="plan",
                model_name="model_name",
                verbosity=0,
                quiet=False,
                backup=True,
                force=False,
                **{"upgrade_group": None}
            ),
        ),
        (
            ["plan", "control-plane"],
            CLIargs(
                command="plan",
                model_name=None,
                verbosity=0,
                quiet=False,
                backup=True,
                force=False,
                **{"upgrade_group": "control-plane"}
            ),
        ),
        (
            ["plan", "data-plane"],
            CLIargs(
                command="plan",
                model_name=None,
                verbosity=0,
                quiet=False,
                backup=True,
                force=False,
                machines=None,
                availability_zones=None,
                **{"upgrade_group": "data-plane"}
            ),
        ),
        (
            ["plan", "hypervisors"],
            CLIargs(
                command="plan",
                model_name=None,
                verbosity=0,
                quiet=False,
                backup=True,
                force=False,
                machines=None,
                availability_zones=None,
                **{"upgrade_group": "hypervisors"}
            ),
        ),
        (
            ["plan", "data-plane", "--force"],
            CLIargs(
                command="plan",
                model_name=None,
                verbosity=0,
                quiet=False,
                backup=True,
                force=True,
                machines=None,
                availability_zones=None,
                **{"upgrade_group": "data-plane"}
            ),
        ),
        (
            ["plan", "hypervisors", "--force"],
            CLIargs(
                command="plan",
                model_name=None,
                verbosity=0,
                quiet=False,
                backup=True,
                force=True,
                machines=None,
                availability_zones=None,
                **{"upgrade_group": "hypervisors"}
            ),
        ),
        (
            ["plan", "control-plane", "--verbose"],
            CLIargs(
                command="plan",
                model_name=None,
                verbosity=1,
                quiet=False,
                backup=True,
                force=False,
                **{"upgrade_group": "control-plane"}
            ),
        ),
        (
            ["plan", "hypervisors", "--machine=1", "-m=2,3"],
            CLIargs(
                command="plan",
                model_name=None,
                verbosity=0,
                quiet=False,
                backup=True,
                force=False,
                machines={"1", "2", "3"},
                availability_zones=None,
                **{"upgrade_group": "hypervisors"}
            ),
        ),
        (
            ["plan", "hypervisors", "--machine=1", "-m=2,3", "--force"],
            CLIargs(
                command="plan",
                model_name=None,
                verbosity=0,
                quiet=False,
                backup=True,
                force=True,
                machines={"1", "2", "3"},
                availability_zones=None,
                **{"upgrade_group": "hypervisors"}
            ),
        ),
        (
            ["plan", "hypervisors", "--quiet", "--availability-zone=1", "--az=2,3"],
            CLIargs(
                command="plan",
                model_name=None,
                verbosity=0,
                quiet=True,
                backup=True,
                force=False,
                machines=None,
                availability_zones={"1", "2", "3"},
                **{"upgrade_group": "hypervisors"}
            ),
        ),
        (
            ["plan", "hypervisors", "--force", "--quiet", "--availability-zone=1", "--az=2,3"],
            CLIargs(
                command="plan",
                model_name=None,
                verbosity=0,
                quiet=True,
                backup=True,
                force=True,
                machines=None,
                availability_zones={"1", "2", "3"},
                **{"upgrade_group": "hypervisors"}
            ),
        ),
        (
            # repetitive machine 3
            ["plan", "hypervisors", "--machine=1,2,3", "--force", "-m=3,4"],
            CLIargs(
                command="plan",
                model_name=None,
                verbosity=0,
                quiet=False,
                backup=True,
                force=True,
                machines={"1", "2", "3", "4"},
                availability_zones=None,
                **{"upgrade_group": "hypervisors"}
            ),
        ),
    ],
)
def test_parse_args_plan(args, expected_CLIargs):
    """Test parsing 'plan' subcommand and its arguments/options."""
    parsed_args = commands.parse_args(args)

    assert parsed_args == expected_CLIargs


@pytest.mark.parametrize(
    "args, expected_CLIargs",
    [
        (
            ["upgrade"],
            CLIargs(
                command="upgrade",
                model_name=None,
                verbosity=0,
                quiet=False,
                auto_approve=False,
                backup=True,
                force=False,
                **{"upgrade_group": None}
            ),
        ),
        (
            ["upgrade", "--no-backup"],
            CLIargs(
                command="upgrade",
                model_name=None,
                verbosity=0,
                quiet=False,
                auto_approve=False,
                backup=False,
                force=False,
                **{"upgrade_group": None}
            ),
        ),
        (
            ["upgrade", "--no-backup", "--quiet"],
            CLIargs(
                command="upgrade",
                model_name=None,
                verbosity=0,
                quiet=True,
                auto_approve=False,
                backup=False,
                force=False,
                **{"upgrade_group": None}
            ),
        ),
        (
            ["upgrade", "--force", "--no-backup", "--quiet"],
            CLIargs(
                command="upgrade",
                model_name=None,
                verbosity=0,
                quiet=True,
                auto_approve=False,
                backup=False,
                force=True,
                **{"upgrade_group": None}
            ),
        ),
        (
            ["upgrade", "--model=model_name"],
            CLIargs(
                command="upgrade",
                model_name="model_name",
                verbosity=0,
                quiet=False,
                auto_approve=False,
                backup=True,
                force=False,
                **{"upgrade_group": None}
            ),
        ),
        (
            ["upgrade", "control-plane"],
            CLIargs(
                command="upgrade",
                model_name=None,
                verbosity=0,
                quiet=False,
                auto_approve=False,
                backup=True,
                force=False,
                **{"upgrade_group": "control-plane"}
            ),
        ),
        (
            ["upgrade", "control-plane", "--force"],
            CLIargs(
                command="upgrade",
                model_name=None,
                verbosity=0,
                quiet=False,
                auto_approve=False,
                backup=True,
                force=True,
                **{"upgrade_group": "control-plane"}
            ),
        ),
        (
            ["upgrade", "data-plane"],
            CLIargs(
                command="upgrade",
                model_name=None,
                verbosity=0,
                quiet=False,
                auto_approve=False,
                backup=True,
                force=False,
                machines=None,
                availability_zones=None,
                **{"upgrade_group": "data-plane"}
            ),
        ),
        # NOTE(gabrielcocenza) Without the argparse.SUPPRESS, this sequence
        # wouldn't be possible.
        (
            ["upgrade", "--force", "data-plane"],
            CLIargs(
                command="upgrade",
                model_name=None,
                verbosity=0,
                quiet=False,
                auto_approve=False,
                backup=True,
                force=True,
                machines=None,
                availability_zones=None,
                **{"upgrade_group": "data-plane"}
            ),
        ),
        (
            ["upgrade", "--no-backup", "data-plane"],
            CLIargs(
                command="upgrade",
                model_name=None,
                verbosity=0,
                quiet=False,
                auto_approve=False,
                backup=False,
                force=False,
                machines=None,
                availability_zones=None,
                **{"upgrade_group": "data-plane"}
            ),
        ),
        (
            ["upgrade", "--model", "my_model", "data-plane"],
            CLIargs(
                command="upgrade",
                model_name="my_model",
                verbosity=0,
                quiet=False,
                auto_approve=False,
                backup=True,
                force=False,
                machines=None,
                availability_zones=None,
                **{"upgrade_group": "data-plane"}
            ),
        ),
        (
            ["upgrade", "control-plane", "--verbose"],
            CLIargs(
                command="upgrade",
                model_name=None,
                verbosity=1,
                quiet=False,
                auto_approve=False,
                backup=True,
                force=False,
                **{"upgrade_group": "control-plane"}
            ),
        ),
        (
            ["upgrade", "--verbose", "control-plane"],
            CLIargs(
                command="upgrade",
                model_name=None,
                verbosity=1,
                quiet=False,
                auto_approve=False,
                backup=True,
                force=False,
                **{"upgrade_group": "control-plane"}
            ),
        ),
        (
            ["upgrade", "hypervisors", "--machine=1", "-m=2,3"],
            CLIargs(
                command="upgrade",
                model_name=None,
                verbosity=0,
                quiet=False,
                auto_approve=False,
                backup=True,
                force=False,
                machines={"1", "2", "3"},
                availability_zones=None,
                **{"upgrade_group": "hypervisors"}
            ),
        ),
        (
            ["upgrade", "hypervisors", "--machine=1", "-m=2,3", "--force"],
            CLIargs(
                command="upgrade",
                model_name=None,
                verbosity=0,
                quiet=False,
                auto_approve=False,
                backup=True,
                force=True,
                machines={"1", "2", "3"},
                availability_zones=None,
                **{"upgrade_group": "hypervisors"}
            ),
        ),
        (
            ["upgrade", "hypervisors", "--quiet", "--availability-zone=1", "--az=2,3"],
            CLIargs(
                command="upgrade",
                model_name=None,
                verbosity=0,
                quiet=True,
                auto_approve=False,
                backup=True,
                force=False,
                machines=None,
                availability_zones={"1", "2", "3"},
                **{"upgrade_group": "hypervisors"}
            ),
        ),
        (
            ["upgrade", "--quiet", "hypervisors", "--availability-zone=1", "--az=2,3"],
            CLIargs(
                command="upgrade",
                model_name=None,
                verbosity=0,
                quiet=True,
                auto_approve=False,
                backup=True,
                force=False,
                machines=None,
                availability_zones={"1", "2", "3"},
                **{"upgrade_group": "hypervisors"}
            ),
        ),
        (
            ["upgrade", "hypervisors", "--force", "--quiet", "--availability-zone=1", "--az=2,3"],
            CLIargs(
                command="upgrade",
                model_name=None,
                verbosity=0,
                quiet=True,
                auto_approve=False,
                backup=True,
                force=True,
                machines=None,
                availability_zones={"1", "2", "3"},
                **{"upgrade_group": "hypervisors"}
            ),
        ),
        (
            # repetitive machine 3
            [
                "upgrade",
                "hypervisors",
                "--auto-approve",
                "--force",
                "--machine=1, 2, 3",
                "-m=3, 4",
            ],
            CLIargs(
                command="upgrade",
                model_name=None,
                verbosity=0,
                quiet=False,
                auto_approve=True,
                backup=True,
                force=True,
                machines={"1", "2", "3", "4"},
                availability_zones=None,
                **{"upgrade_group": "hypervisors"}
            ),
        ),
    ],
)
def test_parse_args_upgrade(args, expected_CLIargs):
    """Test parsing 'run' subcommand and its arguments/options."""
    parsed_args = commands.parse_args(args)

    assert parsed_args == expected_CLIargs


@pytest.mark.parametrize(
    "args",
    [
        ["upgrade", "hypervisors", "--machine 1", "--az 2"],
        ["upgrade", "hypervisors", "--az 1", "-m 2"],
    ],
)
def test_parse_args_hypervisors_exclusive_options(args):
    """Test parsing mutually exclusive hypervisors specific options."""
    with pytest.raises(SystemExit, match="2"):
        commands.parse_args(args)


@pytest.mark.parametrize(
    "args",
    [
        ["foo"],
        ["--bar"],
        ["plan", "data-plane", "--machine 1"],
        ["plan", "data-plane", "--availability-zone zone-1"],
        ["upgrade", "data-plane", "--machine 1"],
        ["upgrade", "data-plane", "--availability-zone zone-1"],
    ],
)
def test_parse_args_raise_exception(args):
    """Test parsing unknown arguments."""
    with pytest.raises(SystemExit, match="2"):
        commands.parse_args(args)


def test_capitalize_usage_prefix():
    """Test add usage with capitalized prefix."""
    parser = ArgumentParser(formatter_class=commands.CapitalizeHelpFormatter)
    usage = parser.format_usage()

    assert usage.startswith("Usage: ")


def test_capitalize_section_title():
    """Test capitalizing option's section title."""
    parser = ArgumentParser(formatter_class=commands.CapitalizeHelpFormatter)
    help_text = parser.format_help()
    section_title = ""
    for line in help_text.splitlines():
        if line.lower().startswith("options"):
            section_title = line
            break

    assert section_title.startswith("Options")


def test_capitalize_help_message():
    """Test capitalizing help message."""
    parser = ArgumentParser(formatter_class=commands.CapitalizeHelpFormatter)
    help_message = parser.format_help()

    assert "Show this help message and exit." in help_message
